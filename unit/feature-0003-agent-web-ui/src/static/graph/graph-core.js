// ITEM-09 batch3 — graph.js L1028~L3191 pure move: 그래프 코어: init·load·G6 build/apply·LOD·anim·검색.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { adminState, apiFetch } from "../admin.js?v=dev";
import { _META_AGG_ZOOM, _META_COL_LOD_MIN, _META_COL_LOD_ZOOM, _META_CULL_MARGIN, _META_CULL_MIN, _META_DIM_OPACITY, _META_EDGE_LOD_MIN, _META_EDGE_LOD_ZOOM, _META_MIN_READ_ZOOM, _META_TERMS_COMBO, _METLAY, _METZ, _METtype, _metaComboName, _metaGraph, _metaNatSort, _metaSchemaComboOf } from "./graph-state.js?v=dev";
import { _META_ROLE, _metaColStyle, _metaComboEdgesRestore, _metaComboMemberIds, _metaComboStyleFor, _metaCtlStyle, _metaDragZBoost, _metaDragZRestore, _metaEdgeStyleFor, _metaFocusAdjacency, _metaFocusKeyFor, _metaGraphBindLegendTabs, _metaGraphZAssert, _metaRoleLegendTips, _metaRoleOf, _metaRoutineEdgeStyle, _metaRoutineStyle, _metaSchemaCardStyle, _metaSchemaCtlStyle, _metaSchemaRefEdgeStyle, _metaTableStyle, _metaTermStyle } from "./graph-roleviz.js?v=dev";
import { _metaCacheSig, _metaStateSig } from "./graph-util.js?v=dev";
import { _metaRelAdjacency, _metaRelOrderAll, _metaRelSchemaOrder } from "./graph-rellayout.js?v=dev";
import { _META_GROUP_TINTS, _metaCatAssign, _metaSimGroups, _metaStableSeq } from "./graph-simgroups.js?v=dev";
import { _metaColParent, _metaCtx, _metaCtxPoint, _metaGraphColCmp, _metaGraphCollapse, _metaGraphCollapseSchema, _metaGraphCtxForCanvas, _metaGraphCtxForCombo, _metaGraphCtxForEdge, _metaGraphCtxForNode, _metaGraphCtxForSchema, _metaGraphCtxHide, _metaGraphExpand, _metaGraphExpandSchema, _metaGraphFocusChip, _metaGraphHistoryGo, _metaGraphHistoryReset, _metaGraphIngest, _metaGraphInitResizer, _metaGraphRenderDetailEmpty, _metaGraphSearch, _metaGraphSetSelected, _metaGraphShowCategoryDetail, _metaGraphShowClusterDetailById, _metaGraphShowClusterDetailLocal, _metaGraphShowDetail, _metaGraphSyncAnalysisMarkers, _metaGraphToggleColumns, _metaTableHasCols } from "./graph-ctxmenu.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)
// feature-0016 §78: PixiJS v8 렌더러 어댑터(SceneAdapter, G6.Graph 인터페이스 호환). 배선 seam.
import { PixiGraphAdapter } from "./graph-renderer-pixi.js?v=dev";
// 렌더러 선택: 'pixi'(기본, window.PIXI 존재 시) | 'g6'(폴백). window.__META_RENDERER 로 강제 override 가능(회귀 시 즉시 롤백).
function _metaRendererKind() {
  const forced = (typeof window !== "undefined" && window.__META_RENDERER) || null;
  if (forced === "g6" || forced === "pixi") return forced;
  return (typeof window !== "undefined" && window.PIXI && typeof PixiGraphAdapter === "function") ? "pixi" : "g6";
}

// ── graph-layoutmemo(§73): 순수 배치-정렬 함수 메모이즈용 위상 서명 ──
//   실측(win-browser, PB-0008): _metaG6Build 의 ~99% 는 _metaRelOrderAll(barycenter 4-sweep)+
//   _metaSimGroups(affix 유사그룹)이 지배하고, 둘 다 **전체 모델**을 처리(뷰포트·줌 무관)해 극단 줌인·
//   비밀집 상태에서도 rebuild 마다 68~145ms 를 태운다("줌인해도 느림"의 근본원인). 두 함수는 순수 —
//   결과는 (로드된 테이블/루틴 = nodes + 정렬이 읽는 객체 속성, REFERENCES 관계 = edges, 역할 = roles,
//   펼친 스키마 = schemaExpanded, mode)에만 의존하고 **컬럼(colsByTable)·freeplace(clusterOffset/nodePos/
//   groupOffset)·선택·뷰포트와 무관**. → 서명 무변경이면(팬·줌·선택·마커·컬럼토글·드래그) 정렬 재사용 →
//   rebuild 를 방출 비용만 남긴다. 컬럼은 nodes(Map) 아닌 colsByTable 거주라 서명서 자연 제외 = 컬럼토글도 적중.
//   ⚠ 적대리뷰(§73) F1/F2 반영: simGroups/relOrder 는 노드 **키**뿐 아니라 **객체 속성**(name·fqn·cluster_id·
//   cluster_label — affix·be:클러스터·정렬)과 **roles**(Phase-3 역할 폴백 _metaRoleOf)도 읽으므로 서명에 포함.
//   키만 해시하면 AI 분석 완료(roles 변경·nodes 무변경) 또는 재-ingest(속성 변경·키 무변경)에서 stale 캐시 발생.
function _metaTopoSig() {
  const hs = (str, h) => { for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0; return h; };
  let nh = 0; _metaGraph.nodes.forEach((v, k) => {
    nh = hs(k + "|" + (v.name || "") + "|" + (v.fqn || "") + "|" + (v.cluster_id != null ? v.cluster_id : "") + "|" + (v.cluster_label || ""), nh);
  });
  let rh = 0, rn = 0; _metaGraph.roles.forEach((role, k) => { rn++; rh = hs(k + "=" + String(role), rh); });   // F1: 역할 폴백 그룹핑
  let eh = 0, en = 0;
  _metaGraph.edges.forEach((e) => {
    if (e.type !== "REFERENCES") return;   // relAdj 는 REFERENCES 만 소비 — 서명도 동일 범위(다른 엣지 변화는 정렬 무영향)
    en++; eh = hs((e.source || "") + ">" + (e.target || "") + ":" + (e.status || ""), eh);
  });
  return _metaGraph.nodes.size + "|" + en + "|" + rn + "|" + nh + "|" + eh + "|" + rh + "|"
    + [..._metaGraph.schemaExpanded].sort().join(",") + "|" + _metaGraph.mode;
}

function _metaG6Build() {
  // graph-product-cat(§43): 제품 카테고리 개요는 전용 경로(Product→Datasource 2-열, combo 미사용) —
  //   기존 스키마 masonry 무간섭·저위험(ADR-014). mode 가 "products" 일 때만 발동.
  if (_metaGraph.mode === "products") return _metaG6BuildProducts();
  // §57.5(사용자 버그 리포트): 상대 하이라이트 인접 집합은 **빌드 시점 재산출** — 선택 시점 스냅샷은
  //   클릭 직후 ShowDetail/컬럼 펼침의 늦은 ingest(이웃 적재)를 반영 못 해 빈/구식 인접으로 굳고,
  //   이후 모든 rebuild 가 그 스냅샷을 bake 해 "다른 노드를 클릭해도 하이라이트가 안 바뀌는" 증상이
  //   된다. 여기서 재산출하면 어떤 경로의 rebuild 든 현재 selected 기준으로 자가 치유된다.
  // §57.5(사용자 버그 리포트) + reltrace-colnav: 기준 키를 _metaFocusKeyFor 로 해소 — 모델 밖 컬럼
  //   선택 시 소속 테이블로 폴백(미펼침 컬럼 하이라이트). 부모가 Table 아니거나 없으면 null:
  //   §57.5 F2(테이블 접기·검색 prune 로 사라진 선택 정리 — 앵커 없는 전역 흐림 방지)를 그대로 보존.
  const _faKey = _metaFocusKeyFor(_metaGraph.selected);
  _metaGraph.focusAdj = _faKey ? _metaFocusAdjacency(_faKey) : null;
  _metaGraph.tableDeps = new Map();   // graph-drag(REQ ②): 전체 재구성마다 종속 UI 맵 리셋(Table key -> 종속 노드 id[]).
  _metaGraph.groupMembers = new Map();   // group-interact(§50): 매 build 그룹→멤버 인덱스 재구성(펼친 그룹만 emission 에서 채움).
  _metaGraph.groupOf = new Map();        // group-interact(§50): 매 build 테이블→groupKey 역인덱스 재구성.
  const groups = new Map();   // comboId -> {isTerms, tables:[], terms:[], colsByTable:Map(tKey->[cols])}
  const ensureG = (id) => { if (!groups.has(id)) groups.set(id, { isTerms: id === _META_TERMS_COMBO, tables: [], terms: [], colsByTable: new Map() }); return groups.get(id); };
  const tableByKey = new Map();
  _metaGraph.nodes.forEach((n) => { if (n.label === "Table") tableByKey.set(n.key, n); });
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Schema") { ensureG(n.key); return; }
    if (n.label === "Table") { ensureG(_metaSchemaComboOf(n)).tables.push(n); return; }
    if (n.label === "Routine") {
      // graph-navfilter(§54②): kind 필터 — 빌드 입력에서 제외(masonry/simgroups 가 자리 자동 회수).
      //   분류식은 _metaRoutineIcon 과 동일(빈값·미상 = procedure/⚙).
      const rk = (n.routine_type === "function") ? "function" : "procedure";
      if (_metaGraph.hiddenKinds.has(rk)) return;
      // graph-funcproc(ADR-016): 함수·프로시저는 테이블과 나란히 소속 스키마 클러스터 열에 선다.
      const sc = _metaSchemaComboOf(n);
      if (sc !== _META_TERMS_COMBO) { ensureG(sc).tables.push(n); return; }
      ensureG(_META_TERMS_COMBO).terms.push(n); return;
    }
    if (n.label === "Column") {
      const tk = _metaColParent(n.key, n.fqn);
      const g = ensureG(_metaSchemaComboOf(n));
      if (tk && tableByKey.has(tk)) { if (!g.colsByTable.has(tk)) g.colsByTable.set(tk, []); g.colsByTable.get(tk).push(n); }
      return;
    }
    ensureG(_META_TERMS_COMBO).terms.push(n);   // GlossaryTerm/Datasource/Product/기타
  });
  // graph-layoutmemo(§73): 위상 서명이 바뀌면 순수 정렬 캐시(relOrder/simGroups) 무효화. 무변경이면
  //   아래 _metaRelOrderAll·_metaSimGroups 호출이 캐시를 재사용해 rebuild 의 지배 비용(68~145ms)을 제거.
  //   서명 계산 자체는 ~1-2ms(nodes/edges 1-pass) — 적중 시 순이득 크다.
  const _topoSig = _metaTopoSig();
  if (_metaGraph._layoutSig !== _topoSig) {
    _metaGraph._layoutSig = _topoSig;
    _metaGraph._relOrderCache = null;
    _metaGraph._simCache = new Map();
  }
  // 클러스터 순서: 관계 seriation(graph-rel-layout, 무관계 시 자연정렬 유지), terms 클러스터는 항상 마지막.
  const relAdj = _metaRelAdjacency(tableByKey);
  const relSchemaOf = (tk) => { const n = tableByKey.get(tk); return n ? _metaSchemaComboOf(n) : null; };
  const ids = _metaRelSchemaOrder([...groups.keys()].filter((k) => k !== _META_TERMS_COMBO).sort(_metaNatSort), relAdj, relSchemaOf);
  if (groups.has(_META_TERMS_COMBO)) ids.push(_META_TERMS_COMBO);
  // feature-0016 §49(요구②): 클러스터 순서 안정화 — 이웃확장/펼침 rebuild 의 re-seriation 으로 클러스터가 그리드를
  //   점프하지 않도록 직전 순서(clusterOrder)를 보존하고 신규 클러스터만 seriated 순서로 append. terms combo 는 항상
  //   마지막. fresh load(resetModel) 시 clusterOrder=[] 라 순수 seriation(첫 배치 동일). 드래그와 직교(원점은 shelf-pack).
  {
    const _hasTerms = ids.length && ids[ids.length - 1] === _META_TERMS_COMBO;
    const _core = _metaStableSeq(_hasTerms ? ids.slice(0, -1) : ids.slice(), _metaGraph.clusterOrder, (x) => x);
    _metaGraph.clusterOrder = _core.slice();
    ids.length = 0; _core.forEach((id) => ids.push(id)); if (_hasTerms) ids.push(_META_TERMS_COMBO);
  }
  // graph-category(§55 A): 제품 카테고리 배정 + ids 를 카테고리 순으로 재배열(카테고리 내부는 위
  //   안정화 순서 유지, terms 는 항상 마지막). 매핑 전무(enabled=false)면 완전 무개입 — 기존 배치.
  const catInfo = _metaCatAssign(ids);
  if (catInfo.enabled) {
    const _hasTerms2 = ids.length && ids[ids.length - 1] === _META_TERMS_COMBO;
    ids.length = 0; catInfo.ids.forEach((id) => ids.push(id)); if (_hasTerms2) ids.push(_META_TERMS_COMBO);
  }
  const schemaIdx = new Map(ids.map((s, i) => [s, i]));   // 테이블 순서의 외부-관계 앵커(이웃 스키마 방향) 조회용
  // graph-layoutmemo(§73): barycenter 정렬(build 지배 비용 ~55%)은 위상 무변경이면 재사용. 아래 안정화
  //   루프(_metaStableSeq)가 relOrder Map 을 in-place 갱신하지만 멱등(이미 안정화된 배열 재안정화=동일)이라
  //   캐시 재사용이 안전. ids 순서도 위상 파생(clusterOrder 안정화)이라 서명 무변경이면 동일.
  const relOrder = _metaGraph._relOrderCache
    || (_metaGraph._relOrderCache = _metaRelOrderAll(groups, ids, relAdj, schemaIdx, relSchemaOf));   // 스키마별 테이블 순서(군집 + barycenter 4-sweep)
  // feature-0016 §49(요구②): 클러스터 내 테이블 순서 안정화(flat masonry 경로) — 신규 테이블/루틴만 append → 기존
  //   테이블이 masonry 열/슬롯을 유지(이웃확장 시 형제 점프 제거). simgroups(구조화 스키마) 경로는 _metaSimGroups
  //   내부에서 그룹 순서·그룹내 테이블 순서를 동일 방식으로 안정화(적대리뷰 R1 반영). 잔여(R2): innerCols 임계
  //   (7/15/28) 교차 시 열 수가 바뀌어 해당 클러스터만 재열 — 반응형 레이아웃 고유 트레이드오프(비파괴, '공간 확보').
  ids.forEach((id) => {
    if (id === _META_TERMS_COMBO) return;
    const _fresh = relOrder.get(id); if (!_fresh) return;
    const _stable = _metaStableSeq(_fresh, _metaGraph.tableOrder.get(id), (t) => t.key);
    relOrder.set(id, _stable);
    _metaGraph.tableOrder.set(id, _stable.map((t) => t.key));
  });

  // ── 클러스터 내 다열 masonry(높이 균형) + 가변폭 클러스터 shelf-packing ──
  //   구버전(단일 세로열 + 고정 3열 grid)은 테이블 많은 스키마가 끝없이 길어지고 36클러스터가 세로로 쌓여
  //   fit-all 시 전부 극소로 축소됐다. 다열 masonry 로 클러스터를 넓고 낮게, shelf-pack 으로 가로 활용을 극대화한다.
  const COLW = 224;                 // 클러스터 내부 열 폭(테이블 칩 190 + 펼친 컬럼 라벨 168 여유; review MINOR: 214→224 로 최대길이 컬럼명이 인접열 칩에 겹치지 않게)
  const TXOFF = 95;                 // 열 좌측 기준 테이블 중심 x
  const CDROP = 6;                  // 테이블↔첫 컬럼 간격
  // graph-vpack(§60): 클러스터 내부 열 수·전역 shelf 폭을 **콘텐츠 실높이 기반**으로 산정해 landscape
  //   종횡비(≈1.6)를 겨냥한다 — 고정 캡(구 innerColsFor 최대 4열 + 고정 MAXROWW 2400)이 스키마 펼침 시
  //   세로로만 자라 얇은 세로 띠가 되던 근본원인 해소(사용자 리포트). 겹침 불변식은 유지: 열은 COLW 간격,
  //   항목은 realH push-down, 클러스터 (w,h)=실 bbox → shelf-pack 이 클러스터를 분리한다.
  const MAXICOL = 10;               // 클러스터 내부 열 상한(단일 스키마가 과도히 넓어지지 않게)
  const ASPECT_K = 100;             // 열 수 종횡비 상수(클러스터 aspect≈COLW/K≈2.2 → 넓고 낮은 landscape;
                                    //   작을수록 열↑·낮아짐. n≤4 는 1열 유지, 대형·펼친 스키마는 열이 늘어 낮아짐)
  //   실높이 총합 기반 열 수: 펼친 컬럼을 반영해 큰/펼친 스키마는 넓고 낮게, 작은 스키마는 기존과 동일 열 수.
  //   arr.length 캡: 항목보다 많은 열은 오른쪽에 빈 열만 만들어 클러스터 폭만 부풀림(shelf-pack 이 이웃을
  //   불필요하게 밀어 공백 — 겹침은 아님, 코스메틱). 항목 1개(예: 컬럼만 펼친 단일 테이블)는 항상 1열.
  const colsForHeights = (arr, hOf, cap) => {
    let tot = 0; for (const t of arr) tot += hOf(t);
    return Math.max(1, Math.min(cap || MAXICOL, arr.length, Math.round(Math.sqrt(tot / ASPECT_K))));
  };
  // ── graph-vpack(§60, ADR-004 ② 재선회): 열 "배정"을 **실높이(realH) 최단 열**로 balance 한다 — 펼친
  //   테이블이 있는 열은 자연히 형제를 덜 받아 클러스터가 넓고 낮아진다(구: 배정을 collapsed 로 고정 →
  //   형제 열-점프 0 이지만 펼친 열만 홀로 세로 폭주). **주의(churn 실측)**: 이 재선회는 base 의 펼침-불변
  //   최적화(setData diff·in-place 안정)를 되돌린다 — 단일 테이블 펼침이 형제의 상당수(80T 스키마에서 ~43%,
  //   ic 전이 경계 n=5/14/27/45/66/… 에서는 전량)를 re-column 시킨다. 사용자 명시 요청("컬럼 재분배 포함 +
  //   세로 폭주 해소")으로 compactness 를 택하고 이 reflow 를 수용한다(대형 스키마 펼침 perf 는 PB-0008
  //   라이브 실측 — T60.5). 겹침 불변식은 그대로:
  //   shelf-packer·클러스터 h 는 **실제 높이 h 를 소비**(절대 collapsed 로 얼리지 말 것 — 얼리면 콤보 카드·
  //   컬럼원 auto-grow 가 아래 shelf 로 넘쳐 겹침, ADR-004 ②/⑤).
  const realH = (g, t) => {         // 펼친 컬럼 포함 실제 높이(자기 열 push-down + 클러스터 h + 열 배정 공통)
    const cols = g.colsByTable.get(t.key);
    let sub = (cols && cols.length) ? cols.length * _METLAY.CROW + CDROP : 0;
    // graph-navfilter(§54⑤): Routine 파라미터 펼침도 실높이에 반영(컬럼과 동형).
    //   masonry(열 수·배정·top)·packGroup·GB bbox·shelf-pack 이 모두 이 단일 실높이 클로저를 소비.
    if (!sub && t.label === "Routine" && _metaGraph.routineExpanded.has(t.key)) {
      const pn = _metaRoutineParamList(t).length;
      if (pn) sub = pn * _METLAY.CROW + CDROP;
    }
    return _METLAY.TROW + sub + _METLAY.TGAP;
  };
  // ── graph-simgroups: 그룹 블록 기하 상수 + 그룹 내부 2-pass masonry ──
  const GHH = 26;                   // 그룹 헤더 행 높이(헤더 칩 + 상단 여백)
  const GPX = 12;                   // 그룹 블록 내부 좌우 pad
  const GPB = 10;                   // 그룹 블록 하단 pad
  const GGX = 14, GGY = 16;         // 그룹 블록 간 가로/세로 간격
  const TRW = 4 * COLW + 3 * GGX;   // 클러스터 내부 그룹 행 목표 폭(≈기존 4열 masonry 폭 유지)
  // graph-vpack(§60): 그룹 내부 masonry 도 실높이 balance(플랫 경로와 동형). 그룹 블록 상한 6열
  //   (§60.2: 4→6 — 멤버 많은 그룹이 세로로 길어지는 것 완화; 작은 그룹은 sqrt 규칙상 열 수 불변).
  const packGroup = (g, arr) => {
    const gic = colsForHeights(arr, (t) => realH(g, t), 6);
    const colTop = new Array(gic).fill(0);
    const inner = arr.map((it) => {
      let c = 0; for (let k = 1; k < gic; k++) if (colTop[k] < colTop[c]) c = k;   // 실높이 최단 열(균형)
      const top = colTop[c];
      colTop[c] += realH(g, it);
      return { it, col: c, top };
    });
    return { gic, inner,
      w: GPX * 2 + gic * COLW,
      h: GHH + Math.max(0, ...colTop) + GPB };   // 실 높이(펼친 컬럼 포함) — 행 y push-down 이 소비
  };
  // col-lod(§61): 노드-레벨 LOD 게이트 — 개요 줌 + 대형(펼친 컬럼 多) 모델에서만 발동. 순수 함수
  //   (getZoom + 전체 펼친 컬럼 수)라 emission 전에 1회 산정한다. realH 등 geometry 는 이 플래그와
  //   무관하게 불변(공간 예약 유지 = band-invariant 좌표). 억제는 방출 단계에서만 일어난다.
  let _colLodZoom = 1;
  try { if (_metaGraph.graph) _colLodZoom = _metaGraph.graph.getZoom() || 1; } catch (_) {}
  // **렌더될** 컬럼만 카운트 — 접힌 스키마(schemaExpanded 아님)의 로드된 컬럼은 방출 안 되므로 게이트에서
  //   제외한다. 전역 합이면 접힌 스키마 컬럼이 임계(_META_COL_LOD_MIN)를 부풀려, 화면의 소량 컬럼을 불필요
  //   억제할 수 있다(리뷰 MINOR). colsByTable 은 펼친 테이블만 담아 순회는 저렴.
  let _expandedColTotal = 0;
  _metaGraph.colsByTable.forEach((c, tkey) => {
    const tn = _metaGraph.nodes.get(tkey);
    const combo = tn ? _metaSchemaComboOf(tn) : null;
    if (combo && _metaGraph.schemaExpanded.has(combo)) _expandedColTotal += (c || 0);
  });
  const colLodActive = _colLodZoom < _META_COL_LOD_ZOOM && _expandedColTotal > _META_COL_LOD_MIN;
  _metaGraph._colLodActive = colLodActive;   // 상태줄 마커(밴드 훅)가 참조
  // agg-lod(§63): 극단 줌아웃 + 대형 모델이면 확장 클러스터를 집계 카드로 강등(아래 emission 분기가 소비).
  // §67(사용자 피드백): 클러스터→단일 카드 집계(§63/§65)는 **규모·구조 파악을 어렵게** 해 폐기한다 —
  //   스키마 클러스터는 펼친 상태를 유지하고, 규모는 상위 **제품 카테고리 밴드 헤더의 요소 개수**로 명시한다.
  //   aggActive 를 상시 false 로 두어 _aggCard(집계 카드 강등)·supernode 스케일 경로를 비활성화(코드는 보존).
  const aggActive = false;
  _metaGraph._aggActive = aggActive;
  // viewport-cull(§65): 화면(+마진) 밖 판정용 model-space 가시 rect 를 1회 산정. 집계 중이 아니고 대형 모델일 때만.
  //   getCanvasByViewport(screen→model) 로 좌상/우하 model 좌표를 얻어 마진 확장. API 부재/개요면 비활성.
  let _cullActive = false, _vx0 = 0, _vy0 = 0, _vx1 = 0, _vy1 = 0;
  // feature-0016 §78: pixi 렌더러는 GPU 상주라 §65/§67 뷰포트 컬링(Canvas per-frame CPU-raster 완화 목적)이
  //   불필요하다. pixi 에서 컬링을 켜면 (a) _built 가 부분집합이 되어 미니맵이 뷰포트만 표시(적대리뷰 M3),
  //   (b) 팬 aftertransform 이 rebuild 를 rAF 마다 걸어 GC churn(M4) — 둘 다 컬링 비활성으로 근본 해소.
  //   전량 방출해도 GPU 팬은 vsync-perfect(882 등가 실측). 컬럼-LOD(§61)/집계(§63)는 방출 수 자체를 줄이므로 유지.
  const _pixiMode = _metaRendererKind() === "pixi";
  if (!aggActive && !_pixiMode && _metaGraph.nodes.size > _META_CULL_MIN) {
    try {
      const _gg = _metaGraph.graph;
      if (_gg && typeof _gg.getCanvasByViewport === "function" && typeof _gg.getSize === "function") {
        const _sz = _gg.getSize();
        const _a = _gg.getCanvasByViewport([0, 0]), _b = _gg.getCanvasByViewport([_sz[0], _sz[1]]);
        if (_a && _b && isFinite(_a[0]) && isFinite(_b[0]) && isFinite(_a[1]) && isFinite(_b[1])) {
          const _mx = Math.abs(_b[0] - _a[0]) * _META_CULL_MARGIN, _my = Math.abs(_b[1] - _a[1]) * _META_CULL_MARGIN;
          _vx0 = Math.min(_a[0], _b[0]) - _mx; _vx1 = Math.max(_a[0], _b[0]) + _mx;
          _vy0 = Math.min(_a[1], _b[1]) - _my; _vy1 = Math.max(_a[1], _b[1]) + _my;
          _cullActive = true;
        }
      }
    } catch (_) { _cullActive = false; }
  }
  _metaGraph._cullActive = _cullActive;   // 상태(디버그/후속). 테이블 bbox 가 가시 rect 와 안 겹치면 off-view.
  // graph-minimap-fullview(§77, 사용자 리포트): 이 build 가 뷰포트 컬링으로 방출을 실제 누락했는지 추적.
  //   _cullActive(컬링 판정 활성)와 별개 — 개요 fit 처럼 전부 가시면 컬링 활성이어도 방출은 완전집합(false).
  //   미니맵 재사용 게이트(_metaPatchMinimapReuse)가 이 플래그로 "부분방출 build 재복제 금지"를 판정한다.
  _metaGraph._cullPartial = false;
  // viewport-cull(§65): 이 build 가 커버한 뷰포트 중심·반경(마진 제외 실 뷰포트) — 팬 후 재-emit 판정용(aftertransform).
  _metaGraph._cullVp = _cullActive
    ? { cx: (_vx0 + _vx1) / 2, cy: (_vy0 + _vy1) / 2, hw: (_vx1 - _vx0) / 2, hh: (_vy1 - _vy0) / 2 }
    : null;
  // graph-minimap-fullview(§77 — 시딩 build): fit 이 판독 하한(_META_MIN_READ_ZOOM)으로 클램프되는 대형
  //   모델은 "전체"에서도 콘텐츠가 화면 밖에 남아 **무컬링 build 가 자연 발생하지 않는다**(라이브 실측:
  //   1,249 노드 fit 에서 방출 153·_cullPartial=true). 이러면 미니맵 전체 이미지가 영영 시딩 안 돼 폴백
  //   (부분 재복제)이 지속 — _metaG6ApplyOnce 가 스코프당 1회 예약하는 컬링-유예 build 로 전체 이미지를
  //   시딩한다. 이 build 는 전량 방출(비용 = pre-§65 빌드 1프레임, 1회 한정) → 미니맵이 전체를 복제·마킹.
  if (_metaGraph._cullSuspendOnce) {
    _metaGraph._cullSuspendOnce = false;   // 1회 소비 — _miniSeedRun 해제는 미니맵 전체 렌더 마킹 시(래퍼)
    if (_cullActive) { _cullActive = false; _metaGraph._cullActive = false; _metaGraph._cullVp = null; }
  }
  const _offView = (x0, y0, x1, y1) => _cullActive && (x1 < _vx0 || x0 > _vx1 || y1 < _vy0 || y0 > _vy1);
  // graph-cull-refkeep(§76, 사용자 피드백): 컬링은 draw(방출)만 줄여야 하고 **참조(엣지)·상호작용(상세 네비)** 은
  //   보존해야 한다. 선택 노드의 관계 상대(focusAdj = 상세 패널이 보여주는 관계)는 화면 밖이어도 방출 예외 —
  //   그래야 (a) renderEndpoint 가 끝점을 찾아 관계선이 렌더되고 (b) _metaRenderedIdFor 가 찾아 관계행 클릭 팬이
  //   동작한다. 무선택(fa 없음)이면 예외 0 = 컬링 전량 유지(성능 무손실). 예외 범위는 선택 노드 degree 로 유계.
  const _faCull = _metaGraph.focusAdj;
  const _faKeep = (k) => !!(_faCull && k && (_faCull.self.has(k) || _faCull.nodes.has(k)));
  const _clusterHasFocus = (g) => !!(_faCull && g && !g.isTerms && g.tables && g.tables.some((t) => _faKeep(t.key)));
  // 각 클러스터 레이아웃 선산정(폭·높이 + 항목 절대 오프셋 배치).
  //   place 항목은 {it, lx(열 좌측 x — 클러스터 상대), top(항목 상단 y — 클러스터 상대)} 로 정규화 —
  //   평면/그룹 두 경로가 같은 렌더 루프를 공유한다.
  const layouts = ids.map((id) => {
    const g = groups.get(id);
    // graph-initview: 스키마 카드 게이팅(모드-독립 단일소스 schemaExpanded) — 접힌 스키마는 카드로만.
    //   검색/이웃 흐름은 결과 스키마를 schemaExpanded 에 자동 추가하므로 응답 노드는 항상 보인다.
    const gatedTables = (!g.isTerms && !_metaGraph.schemaExpanded.has(id)) ? [] : g.tables;
    if (!g.isTerms && !gatedTables.length && !g.terms.length) {
      return { id, g, kind: "card", w: _METLAY.CARDW, h: _METLAY.CARDH, x0: 0, y0: 0 };
    }
    // graph-simgroups: 유사 속성 그룹 분할 — 2개 이상일 때만 그룹 블록 렌더(1개면 기존 평면 masonry 유지).
    // graph-layoutmemo(§73): affix 유사그룹(build 지배 비용 ~45%)은 순수·위상파생 — 스키마별 캐시(_simCache,
    //   서명 무변경 시 재사용). 결과는 하류에서 읽기 전용(packGroup·groupOf 채움 모두 read)이라 공유 안전.
    let simGroups = null;
    if (!g.isTerms && gatedTables.length) {
      if (_metaGraph._simCache.has(id)) simGroups = _metaGraph._simCache.get(id);
      else { simGroups = _metaSimGroups(id, gatedTables, relAdj); _metaGraph._simCache.set(id, simGroups); }
    }
    if (simGroups && simGroups.length >= 2) {
      // 그룹 블록 shelf-pack: 행 배정은 블록 폭(펼침-불변)만 소비, 행 y 는 실 높이 누적(push-down —
      //   펼친 컬럼이 자기 블록 높이를 키우면 아래 "행"만 밀리고 좌우 이웃 블록 x 는 불변).
      // group-interact(§50): 접힌 그룹은 헤더만(HDONLY) 높이로 블록 축소 → shelf-pack 자동 reflow.
      //   검색 매칭 멤버가 있는 그룹은 접힘 상태여도 강제 펼침(결과 가시 — schemaExpanded 자동추가와 동형).
      const HDONLY = GHH + GPB;
      const smt = (_metaGraph.mode === "search") ? _metaGraph.searchMatchTables : null;
      const isCollapsed = (sg) => _metaGraph.groupCollapsed.has(sg.key)
        && !(smt && sg.tables.some((t) => smt.has(t.key)));
      const blocks = simGroups.map((sg, gi) => {
        const p = packGroup(g, sg.tables);
        const collapsed = isCollapsed(sg);
        return Object.assign({ sg, gi, collapsed, hEff: collapsed ? HDONLY : p.h }, p);
      });
      // graph-vpack(§60.2, PB-0008 라이브 실측): 그룹 블록 행 목표 폭도 **총 블록 면적 기반**으로 적응한다.
      //   고정 TRW(4열 상당 ≈938)는 그룹이 많은 스키마(관계 있는 제품 스키마 다수)에서 그룹 행이 세로로
      //   쌓여 클러스터가 세로 폭주(라이브 cc_* 557T = 822×10272, aspect 0.08). floor=TRW(소수 그룹 현행
      //   배치 보존), landscape(×2.0) 타깃 — flat 경로 MAXROWW 와 동일 철학의 클러스터-내부판.
      let _gTotArea = 0; blocks.forEach((b) => { _gTotArea += Math.max(1, b.w) * Math.max(1, b.hEff); });
      const TRW_ADAPT = Math.max(TRW, Math.round(Math.sqrt(_gTotArea * 2.0)));
      const rows = [];
      { let cur = { blocks: [], w: 0 };
        blocks.forEach((b) => {
          if (cur.blocks.length && cur.w + b.w > TRW_ADAPT) { rows.push(cur); cur = { blocks: [], w: 0 }; }
          b.bxRel = _METLAY.PADX + cur.w; cur.blocks.push(b); cur.w += b.w + GGX;
        });
        if (cur.blocks.length) rows.push(cur); }
      let byy = _METLAY.PADT + 6, contentW = 0;
      rows.forEach((row) => {
        const rowH = Math.max(...row.blocks.map((b) => b.hEff));   // 접힌 블록은 헤더만 소비(펼친 이웃 높이에 얹힘)
        row.blocks.forEach((b) => { b.byRel = byy; });
        contentW = Math.max(contentW, row.w - GGX);
        byy += rowH + GGY;
      });
      const place = [];
      const groupsMeta = [];
      blocks.forEach((b) => {
        // group-interact(§50): sim-group 자유 배치 offset(드래그 누적) — 박스·헤더·멤버 place 공통 가산
        //   (cluster L.x0/L.y0 위, node nodePos 아래 — 3계층). GB 박스 실제 기하는 emission 이 멤버 bbox 로 파생.
        const goff = _metaGraph.groupOffset.get(b.sg.key);
        const gdx = goff ? goff.dx : 0, gdy = goff ? goff.dy : 0;
        // group-interact(§50, REV-wiring MAJOR fix): groupMembers/groupOf 는 **전체 멤버**(접힘 포함)로 채운다.
        //   emission pre-pass 는 방출된(펼친) 멤버만 알아 접힌 그룹이 인덱스에서 누락 → 접힌 그룹 드래그 시 그
        //   멤버 nodePos 시프트가 스킵돼(펼치면 nodePos 멤버만 옛 좌표에 남아 분리). 여기서 b.sg.tables 로 전량 등록.
        b.sg.tables.forEach((t) => {
          _metaGraph.groupOf.set(t.key, b.sg.key);
          let mm = _metaGraph.groupMembers.get(b.sg.key); if (!mm) { mm = []; _metaGraph.groupMembers.set(b.sg.key, mm); } mm.push(t.key);
        });
        groupsMeta.push({ key: b.sg.key, label: b.sg.label, n: b.sg.n,
          x: b.bxRel + gdx, y: b.byRel + gdy, w: b.w, h: b.collapsed ? HDONLY : b.h,
          collapsed: b.collapsed, tint: _META_GROUP_TINTS[b.gi % _META_GROUP_TINTS.length] });
        if (b.collapsed) return;   // 접힌 그룹은 멤버 미방출(헤더 칩만 — 개수로 내용 인지)
        b.inner.forEach(({ it, col, top }) => {
          place.push({ it, group: b.sg.key,
            lx: b.bxRel + gdx + GPX + col * COLW, top: b.byRel + gdy + GHH + top });
        });
      });
      const w = _METLAY.PADX * 2 + contentW;
      const h = byy - GGY + 16;   // 마지막 행 실 높이 포함(펼친 컬럼 auto-grow 겹침 방지 — collapsed 로 얼리지 말 것)
      return { id, g, place, groupsMeta, w, h, x0: 0, y0: 0 };
    }
    // ── 평면 masonry(기존 경로): terms 클러스터 · 그룹 <2 스키마 — place 를 {it,lx,top} 로 정규화 ──
    // graph-rel-layout: 테이블 순서는 _metaRelOrderAll 사전 산정분(관계-군집+barycenter, 무관계 시 자연정렬과
    //   동일)을 그대로 소비 — 여기서 재정렬하면 같은 배열의 중복 nat-sort(§18.8 패널 MINOR). terms 만 즉석 정렬.
    const items = g.isTerms
      ? g.terms.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key))
      : (relOrder.get(id) || gatedTables.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key)));
    // graph-vpack(§60): 실높이 balance 단일 패스 — 열 수는 실높이 총합 기반(펼침 반영: 큰/펼친 스키마는
    //   넓고 낮게), 배정은 실높이 최단 열(펼친 테이블 열은 형제를 덜 받아 클러스터 세로 폭주 억제). 겹침
    //   방지: COLW 열 간격 + realH push-down + w/h=실 bbox(shelf-packer 소비). terms 는 realH 무의미 →
    //   TROW 고정 높이로 계산.
    const hOf = (it) => g.isTerms ? _METLAY.TROW : realH(g, it);
    const ic = colsForHeights(items, hOf, MAXICOL);
    const colTop = new Array(ic).fill(_METLAY.PADT);
    const place = items.map((it) => {
      let c = 0; for (let k = 1; k < ic; k++) if (colTop[k] < colTop[c]) c = k;   // 실높이 최단 열(균형 재분배)
      const top = colTop[c];
      colTop[c] += hOf(it);
      return { it, lx: _METLAY.PADX + c * COLW, top };
    });
    const w = _METLAY.PADX * 2 + ic * COLW;
    const h = Math.max(_METLAY.PADT, ...colTop) + 16;   // 실제 높이 — shelf-packer 가 소비(겹침 방지, 절대 collapsed 로 얼리지 말 것)
    return { id, g, place, w, h, x0: 0, y0: 0 };
  });
  // graph-vpack(§60): 전역 shelf 목표 폭을 **총 콘텐츠 면적 기반**으로 산정 → 패킹이 landscape 종횡비를
  //   겨냥(많이 펼칠수록 가로로 퍼져 높이 억제). 구 고정 2400 은 스키마 여러 개 펼침 시 폭이 고정된 채
  //   행만 세로로 쌓여 세로 폭주(얇은 세로 띠)의 지배적 원인이었다. floor: 2400(현행 소량 펼침 배치 보존)
  //   및 _vpMaxW(가장 넓은 클러스터는 항상 자기 행에 놓이게 — 클러스터 간 겹침·꺾임 방지).
  //   계수 2.0: 넓은 클러스터가 행당 더 많이 담기도록(1.6 은 낮은 이산 패킹으로 세로형 잔존 — 12스키마
  //   케이스 aspect 0.69). 2.0 은 세로형 케이스를 landscape(≈1.6)로 교정하면서 과도한 가로 확장은 피한다.
  let _vpTotArea = 0, _vpMaxW = 0;
  layouts.forEach((L) => { _vpTotArea += Math.max(1, L.w) * Math.max(1, L.h); if (L.w > _vpMaxW) _vpMaxW = L.w; });
  const MAXROWW = Math.max(2400, _vpMaxW, Math.round(Math.sqrt(_vpTotArea * 2.0)));
  // shelf-packing: 가변폭 클러스터를 좌→우로 채우고, 폭 초과 시 다음 행으로.
  // graph-category(§55 A): 카테고리 활성 시 **카테고리 밴드별로** 분할 패킹 — 각 카테고리가 자기 행들을
  //   좌→우로 채우고, 밴드는 세로로 스택된다(헤더 CATHH 확보). 접힌 카테고리는 멤버를 방출하지 않고
  //   (catHidden) 헤더 밴드만 남긴다. 비활성(enabled=false)이면 기존 단일 흐름 그대로.
  const CATHH = 36;   // 카테고리 헤더 밴드 높이(칩 + 상단 여백)
  if (!catInfo.enabled) {
    let cx = 0, cyy = 0, shelfH = 0;
    layouts.forEach((L) => {
      if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; cyy += shelfH + _METLAY.GAPY; shelfH = 0; }
      L.x0 = cx; L.y0 = cyy; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
    });
  } else {
    const layById = new Map(layouts.map((L) => [L.id, L]));
    let cyy = 0;
    catInfo.cats.forEach((cat) => {
      cat.bandY = cyy;
      const catLays = cat.members.map((id) => layById.get(id)).filter(Boolean);
      if (cat.collapsed) {
        catLays.forEach((L) => { L.catHidden = true; });
        cyy += CATHH + _METLAY.GAPY;   // 헤더 밴드만 차지
        return;
      }
      let cx = 0, rowY = cyy + CATHH, shelfH = 0;
      catLays.forEach((L) => {
        if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; rowY += shelfH + _METLAY.GAPY; shelfH = 0; }
        L.x0 = cx; L.y0 = rowY; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
      });
      cyy = rowY + shelfH + _METLAY.GAPY + 22;   // 밴드 간 여유(+22 — 밴드 하단 패딩 시각 분리)
    });
    // 카테고리 무소속(terms 클러스터 등)은 마지막 밴드 아래 단일 흐름으로.
    { let cx = 0, rowY = cyy, shelfH = 0;
      layouts.forEach((L) => {
        if (catInfo.inCat.has(L.id)) return;
        if (cx > 0 && cx + L.w > MAXROWW) { cx = 0; rowY += shelfH + _METLAY.GAPY; shelfH = 0; }
        L.x0 = cx; L.y0 = rowY; cx += L.w + _METLAY.GAPX; shelfH = Math.max(shelfH, L.h);
      }); }
  }
  // graph-freeplace: 사용자 드래그 클러스터 offset 을 packing 결과에 가산(렌더 위치만 — 폭 누적/행 배정엔 미개입).
  //   L.x0/L.y0 가 카드·테이블·컬럼·장식·combo 의 공통 기준이라, 여기서 가산하면 클러스터 전체가 coherent 하게
  //   이동하고 펼침/접기 rebuild 후에도 유지된다(자유 배치 persistence — ADR-004 결정론 배치 회귀 복원).
  layouts.forEach((L) => {
    const off = _metaGraph.clusterOffset.get(L.id);
    if (off) { L.x0 += off.dx; L.y0 += off.dy; }
  });
  // graph-cull-refkeep(§76, 사용자 요구): 전체 노드 위치 맵(nodePosAll — 컬링돼도 포함, 커스텀 미니맵·엣지 앵커
  //   공용) + **뷰포트 내 노드 엣지 컬링무효**. layouts 의 place(최종 배치 위치)로 1-pass 산정: 각 테이블/루틴 center 를
  //   nodePosAll 에 적재 + in-view(뷰포트+마진 내 = 미컬링) 집합을 만든 뒤, in-view 노드에 연결된 엣지의 상대 끝점
  //   테이블을 _edgeExempt 에 넣어 컬 예외 → 관계선이 화면 밖 상대까지 이어진다("뷰포트 내 노드들 연결선 컬링무효").
  _metaGraph.nodePosAll = new Map();
  const _inView = new Set();
  const _edgeExempt = new Set();
  const _foldTbl = (k) => { const n = _metaGraph.nodes.get(k); if (n && n.label !== "Column") return k; return _metaColParent(k, n && n.fqn) || k; };
  layouts.forEach((L) => {
    if (L.catHidden) return;
    const lg = L.g;
    if (L.kind === "card") { _metaGraph.nodePosAll.set("SC:" + L.id, { x: L.x0 + _METLAY.CARDW / 2, y: L.y0 + _METLAY.CARDH / 2, w: _METLAY.CARDW, h: _METLAY.CARDH, card: true }); return; }
    (L.place || []).forEach(({ it, lx, top }) => {
      let colLeftX = L.x0 + lx, ty = L.y0 + top + _METLAY.TROW / 2;
      const _fp = _metaGraph.nodePos.get(it.key);
      if (_fp && isFinite(_fp[0]) && isFinite(_fp[1])) { const ddx = _fp[0] - (colLeftX + TXOFF), ddy = _fp[1] - ty; colLeftX += ddx; ty += ddy; }
      const _rh = realH(lg, it);
      _metaGraph.nodePosAll.set(it.key, { x: colLeftX + TXOFF, y: ty, w: COLW, h: _rh });
      if (_cullActive && !_offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + _rh)) _inView.add(it.key);
    });
  });
  if (_cullActive && _inView.size) {
    _metaGraph.edges.forEach((e) => {
      if (e.type !== "REFERENCES" && e.type !== "ROUTINE_USES") return;   // 관계선(참조·사용) 대상 — containment(HAS_*)·용어는 제외
      const a = _foldTbl(e.source), b = _foldTbl(e.target);
      if (a && b && a !== b && (_inView.has(a) || _inView.has(b))) { _edgeExempt.add(a); _edgeExempt.add(b); }
    });
  }
  _metaGraph._edgeExempt = _edgeExempt;   // (디버그/테스트 노출)
  // graph-minimap-fullview(§77): **전체-기하 서명**(컬링 무관) — nodePosAll(컬링돼도 전 노드 포함, §76)로
  //   산정. 미니맵이 보유한 전체 이미지가 '현재 전체 기하' 와 일치하는지 판정하는 기준 — 접힘 카드 단계의
  //   full 이미지를 펼침 후에도 현재로 오인해 시딩까지 억제하던 결함(라이브 실측)의 근본 해소.
  //   0.25px 양자화·FNV-1a(§74 동형). 엣지 수 포함(관계 큐레이션류 엣지-only 변경 감지 보조).
  {
    let fh = 0x811c9dc5 >>> 0;
    const fmix = (s) => { s = String(s); for (let i = 0; i < s.length; i++) { fh ^= s.charCodeAt(i); fh = Math.imul(fh, 0x01000193) >>> 0; } fh ^= 0x2c; fh = Math.imul(fh, 0x01000193) >>> 0; };
    _metaGraph.nodePosAll.forEach((p, k) => { fmix(k); fmix(Math.round(p.x * 4)); fmix(Math.round(p.y * 4)); fmix(Math.round((p.h || 0) * 4)); });
    _metaGraph._miniFullSig = _metaGraph.nodePosAll.size + ":" + _metaGraph.edges.size + ":" + (fh >>> 0);
  }
  // §76: 컬 예외 통합 판정 — focus(선택 노드 관계) OR edge(뷰포트 내 노드 연결 상대). 테이블·클러스터 컬 지점 공용.
  const _keepFromCull = (k) => _faKeep(k) || _edgeExempt.has(k);
  const _clusterKeep = (g) => _clusterHasFocus(g) || !!(g && !g.isTerms && g.tables && g.tables.some((t) => _edgeExempt.has(t.key)));
  const combos = [], nodes = [], edges = [];
  _metaGraph.firstElementId = null;
  // graph-category(§55 A): 카테고리 밴드(CAT: 배경 + CATH: 헤더 칩 + CATX: 접기) 방출 — 박스 기하는
  //   멤버 클러스터의 **최종 배치(clusterOffset 반영) bbox + 패딩** 파생(sim-group GB bbox 동형 —
  //   클러스터 이동에 반응형). 접힌 카테고리는 헤더 밴드만. zIndex: 배경 CAT_BG(-1, combo 아래) /
  //   헤더 GROUP_HD / 컨트롤 CTL. 헤더 드래그 = 카테고리 리지드 이동(멤버 clusterOffset 일괄 누적).
  if (catInfo.enabled) {
    const layById2 = new Map(layouts.map((L) => [L.id, L]));
    catInfo.cats.forEach((cat, ci) => {
      const vis = cat.members.map((id) => layById2.get(id)).filter((L) => L && !L.catHidden);
      let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
      vis.forEach((L) => {
        left = Math.min(left, L.x0); top = Math.min(top, L.y0);
        right = Math.max(right, L.x0 + L.w); bottom = Math.max(bottom, L.y0 + L.h);
      });
      const PADX2 = 22, PADB2 = 18;
      let bl, bt, bw, bh;
      if (vis.length && isFinite(left)) {
        bl = left - PADX2; bt = top - CATHH; bw = (right + PADX2) - bl; bh = (bottom + PADB2) - bt;
      } else {   // 접힘(또는 전 멤버 미방출) — 헤더 밴드만
        bl = -PADX2; bt = cat.bandY || 0; bw = 720; bh = CATHH;
      }
      const tint = _META_GROUP_TINTS[ci % _META_GROUP_TINTS.length];
      nodes.push({ id: "CAT:" + cat.key, type: _METtype,
        data: { kind: "cat-bg", cat: cat.key },
        style: { x: bl + bw / 2, y: bt + bh / 2, size: [bw, bh], radius: 14,
          fill: tint.bg, fillOpacity: 0.38, stroke: tint.bd, lineWidth: 1.6, lineDash: [7, 4],
          zIndex: _METZ.CAT_BG, cursor: "move" } });
      // §67(사용자 피드백): 카테고리 밴드 헤더에 **규모(요소 개수)를 명시** — 스키마(DB) 수 + 총 테이블 수.
      //   테이블 수는 schemaTotals(스키마→전체 테이블 수, 카드 badge 와 동일 소스)를 멤버 합산. 대형은 천단위 구분.
      const _catTbl = cat.members.reduce((s, m) => s + ((_metaGraph.schemaTotals && _metaGraph.schemaTotals.get(m)) || 0), 0);
      const hdText = `🗂 ${cat.label} · ${cat.members.length} DB` + (_catTbl > 0 ? ` · ${_catTbl.toLocaleString()} 테이블` : "");
      const hdW = Math.min(Math.max(80, Math.round(hdText.length * 8.2) + 22), Math.max(120, bw - 46));
      nodes.push({ id: "CATH:" + cat.key, type: _METtype,
        data: { kind: "cat-hd", cat: cat.key, label: cat.label },
        style: { x: bl + 12 + hdW / 2, y: bt + 16, size: [hdW, 22], radius: 11,
          fill: tint.hd, stroke: tint.bd, lineWidth: 1.2, zIndex: _METZ.GROUP_HD, cursor: "move",
          labelText: hdText, labelFill: "#1d2635", labelFontSize: 12, labelFontWeight: 700,
          // 리뷰 NIT: '· M 테이블' 추가로 라벨이 길어져 좁은 밴드에서 넘칠 수 있어 labelMaxWidth 로 ellipsis 흡수
          //   (한글 실폭 > hdText.length*8.2 추정이라 hdW 캡만으론 부족).
          labelMaxWidth: hdW - 8, labelPlacement: "center" } });
      nodes.push({ id: "CATX:" + cat.key, type: _METtype,
        data: { label: cat.collapsed ? "+" : "−", kind: "cat-ctl", cat: cat.key },
        style: Object.assign(_metaCtlStyle(bl + bw - 16, bt + 16), { size: [18, 18],
          labelText: cat.collapsed ? "+" : "−", labelFontSize: 15 }) });
    });
  }
  layouts.forEach((L) => {
    const { id, g } = L;
    if (L.catHidden) return;   // graph-category(§55 A): 접힌 카테고리 멤버 — 클러스터 전체 미방출
    // agg-lod(§63): 극단 줌아웃에서 확장 클러스터도 집계 카드로 강등 — 카드 경로 재사용. 슬롯(L.x0/L.y0)은
    //   유지하고 카드를 슬롯 좌상단에 두므로 reflow 0. combos/tables/columns 전체 방출을 카드 1개로 대체.
    const _aggCard = aggActive && !g.isTerms && _metaGraph.schemaExpanded.has(id);
    const _asCard = (L.kind === "card") || _aggCard;
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = _asCard ? ("SC:" + id) : id;
    if (_asCard) {
      // id 는 "SC:" 네임스페이스 — 같은 스키마 key 가 펼침 시 combo id 로 쓰이므로, 동일 id 의
      // 노드↔combo 타입 전환을 G6 setData diff 가 처리하지 못하는 문제(자식 유실)를 원천 차단.
      const cn = _metaGraph.nodes.get(id);
      const cnt = (cn && typeof cn.table_count === "number") ? cn.table_count : null;
      const nmc = _metaComboName(id);
      // graph-initview UI: 라벨은 스키마명만(전체 폭 확보) + 개수는 우상단 **badge**(작은 pill).
      //   검색 없음 → [전체 테이블 개수]. 검색 필터 → [매칭 테이블 개수 / 전체 테이블 개수](사용자 요청).
      //   badge 는 이름과 폭 경쟁 없이 개수를 노출(집계 실패 cnt=null 은 badge 없음 = 배지없는 카드 강등 정합).
      let badgeText = (cnt != null) ? String(cnt) : null;
      let badgeBg = _META_GRAPH_COLOR.Schema;
      if (_metaGraph.mode === "search" && _metaGraph.searchMatch && _metaGraph.searchMatch.has(id)) {
        const matched = _metaGraph.searchMatch.get(id).size;
        const plus = _metaGraph.searchCapped ? "+" : "";   // review MAJOR: cap 도달 시 부분 카운트 표기(≥)
        badgeText = (cnt != null) ? `${matched}${plus}/${cnt}` : `${matched}${plus}`;
        badgeBg = "#0a5b66";   // 검색 필터 badge 는 teal 강조(전체 카운트 남색과 구분)
      }
      // agg-lod(§63) supernode: 집계 카드는 줌아웃으로 작아져 읽기 힘든 문제(사용자 피드백) 해소 —
      //   화면 목표폭(~120px)을 유지하도록 ≈1/zoom 스케일업 + 슬롯 중앙 배치 + 슬롯 안으로 클램프(겹침 억제) +
      //   라벨/배지 폰트 동반 확대. 비-집계(접힌 roots) 카드는 기존 그대로(스케일 1).
      let _cardCx = L.x0 + _METLAY.CARDW / 2, _cardCy = L.y0 + _METLAY.CARDH / 2;
      let _cardW = _METLAY.CARDW, _cardH = _METLAY.CARDH, _cardLF = 13, _cardBF = 10;
      if (_aggCard) {
        const _sc = Math.max(1.6, Math.min(8, 120 / Math.max(0.04, _colLodZoom) / _METLAY.CARDW));   // 상한 8(깊은 줌 카드 크기 확장, 리뷰 NIT)
        _cardW = Math.min(Math.round(_METLAY.CARDW * _sc), Math.max(_METLAY.CARDW, Math.round(L.w * 0.94)));
        _cardH = Math.min(Math.round(_METLAY.CARDH * _sc), Math.max(_METLAY.CARDH, Math.round(L.h * 0.7)));
        _cardCx = L.x0 + L.w / 2; _cardCy = L.y0 + L.h / 2;
        // 폰트도 카드 스케일을 따라가되 카드 높이 안에 맞게 클램프(리뷰 NIT — 이전 3.2/2.6 은 깊은 줌서 화면 폰트 과소).
        _cardLF = Math.min(Math.round(13 * Math.min(_sc, 4.5)), Math.round(_cardH * 0.5));
        _cardBF = Math.min(Math.round(10 * Math.min(_sc, 3.5)), Math.round(_cardH * 0.34));
      }
      const cardStyle = Object.assign(_metaSchemaCardStyle(_cardCx, _cardCy), {
        size: [_cardW, _cardH], labelText: nmc, labelFontSize: _cardLF, labelMaxWidth: _cardW - 16,
        // review MINOR: offset 은 per-item 에 둬야 실제 transform 에 반영(node-level badgeOffsetX/Y 는 무시됨).
        badges: badgeText != null ? [{ text: badgeText, placement: "right-top", offsetX: -2, offsetY: 2 }] : [],
        badgeFontSize: _cardBF, badgeFill: "#ffffff", badgeBackgroundFill: badgeBg, badgePadding: [1, 5],
      });
      nodes.push({ id: "SC:" + id, type: _METtype, states: _metaStateSig(id),
        data: { label: nmc, kind: "schema-card", schema: id, fqn: (cn && cn.fqn) || nmc, table_count: cnt },
        style: cardStyle });
      return;
    }
    // viewport-cull(§67): 클러스터 전체 bbox 가 화면(+마진) 밖이면 combo·테이블·장식 전부 미방출(줌인 시 화면
    //   밖 클러스터 draw 비용 0 — 가장 큰 절감). 부분 가시 클러스터는 combo 방출 + 가시 테이블만(per-table 컬링),
    //   combo 는 가시분에 auto-fit. 카테고리 밴드 bbox 는 별도 선산정이라 컬링과 무관(규모 밴드 유지).
    //   리뷰 MINOR: L.w/L.h 는 free-place(nodePos·groupOffset) 드래그 변위 미반영(pre-offset masonry)이라 드래그로
    //   bbox 밖에 나간 가시 멤버를 오컬링할 수 있다 → free-place 존재 시 전체-클러스터 컬링을 건너뛰고 per-table
    //   컬링(nodePos 반영 좌표)에만 맡긴다(정확·안전, free-place 는 드문 경로).
    const _freePlaced = _metaGraph.nodePos.size > 0 || _metaGraph.groupOffset.size > 0;
    // §76: 클러스터가 선택 노드의 관계 상대를 하나라도 품으면 통째 컬링 금지 → combo + 그 관계 테이블이 방출돼
    //   관계선·상호작용이 보존된다(per-table 컬링이 나머지 화면 밖 테이블은 계속 억제).
    if (_cullActive && !g.isTerms && !_freePlaced && !_clusterKeep(g) && _offView(L.x0, L.y0, L.x0 + L.w, L.y0 + L.h)) { _metaGraph._cullPartial = true; return; }   // graph-minimap-fullview(§77): 부분방출 표시
    combos.push({ id, type: _METtype, data: { label: _metaComboName(id), kind: "schema" }, style: Object.assign({ labelText: _metaComboName(id) }, _metaComboStyleFor(g.isTerms)) });
    if (!g.isTerms && _metaGraph.schemaExpanded.has(id)) {
      // graph-initview: "−" 접기 컨트롤(combo 우상단) — 카드로 복귀.
      nodes.push({ id: "XS:" + id, type: _METtype, combo: id, data: { label: "−", kind: "schema-ctl", schema: id },
        style: _metaSchemaCtlStyle(L.x0 + L.w - 20, L.y0 + _METLAY.PADT - 26) });
    }
    // graph-simgroups + group-interact(§50): 그룹 배경 박스 + 헤더 칩 + 접기 컨트롤(GX).
    //   #3 반응형: 펼친 그룹의 GB 박스 기하는 **멤버(테이블+펼친 컬럼)의 최종 place bbox + 패딩**에서 파생 —
    //   개별 노드 이동(nodePos)·그룹 이동(groupOffset) 양쪽에 박스가 자동으로 맞춰진다. 접힌 그룹은 헤더 기하.
    //   pre-pass 는 방출된(펼친) 멤버 place 를 1회 훑어 groupBox(절대 경계)를 계산한다(groupMembers/groupOf 는
    //   layout 분기에서 전체 멤버로 이미 채움 — 접힌 그룹 포함, REV-wiring MAJOR fix).
    if (L.groupsMeta) {
      const grpBox = new Map();
      L.place.forEach(({ it, lx, top, group }) => {
        if (!group) return;
        let colLeftX = L.x0 + lx;
        let ty = L.y0 + top + _METLAY.TROW / 2;
        const _fp = _metaGraph.nodePos.get(it.key);   // 개별 드래그 위치(place-loop 과 동일 수학)
        if (_fp && isFinite(_fp[0]) && isFinite(_fp[1])) { colLeftX += _fp[0] - (colLeftX + TXOFF); ty = _fp[1]; }
        const topAbs = ty - _METLAY.TROW / 2, memBottom = topAbs + realH(g, it);
        let bx = grpBox.get(group);
        if (!bx) { bx = { minL: Infinity, minT: Infinity, maxR: -Infinity, maxB: -Infinity }; grpBox.set(group, bx); }
        bx.minL = Math.min(bx.minL, colLeftX); bx.maxR = Math.max(bx.maxR, colLeftX + COLW);
        bx.minT = Math.min(bx.minT, topAbs);   bx.maxB = Math.max(bx.maxB, memBottom);
      });
      L.groupsMeta.forEach((gm) => {
        // 펼침: 멤버 bbox 파생(무멤버 방어 시 패킹 폴백) · 접힘: 패킹 헤더 기하.
        const bx = (!gm.collapsed) ? grpBox.get(gm.key) : null;
        let left, top, right, bottom;
        if (bx && isFinite(bx.minL)) { left = bx.minL - GPX; top = bx.minT - GHH; right = bx.maxR + GPX; bottom = bx.maxB + GPB; }
        else { left = L.x0 + gm.x; top = L.y0 + gm.y; right = left + gm.w; bottom = top + gm.h; }
        const bw = right - left, bh = bottom - top;
        nodes.push({ id: "GB:" + gm.key, type: _METtype, combo: id,
          data: { kind: "group-bg", group: gm.key, schema: id },
          style: { x: left + bw / 2, y: top + bh / 2, size: [bw, bh], radius: 10,
            // graph-zorder(§52): GROUP_BG(1) — 예전 -2 는 combo 배경(z0) **아래**라 @antv/g hit-test 에서 combo 에
            //   삼켜져 §50 그룹 상호작용(배경 드래그=그룹 이동·클릭·우클릭)이 dead 였고, 그룹 배경을 잡으면
            //   클러스터 전체가 이동했다(의미 불일치). combo 위·엣지(2)/칩(4) 아래로 정렬해 의미·hit-test 정합.
            // 패널 ux MAJOR: GB 는 이제 그룹 드래그 핸들로 실동작 — cursor:move 로 어포던스 표시
            //   (클러스터 이동은 combo 여백·라벨·접힌 카드 경로 — 범례에 안내).
            fill: gm.tint.bg, fillOpacity: 0.75, stroke: gm.tint.bd, lineWidth: 1.2, zIndex: _METZ.GROUP_BG, cursor: "move" } });
        const hdText = `${gm.label} · ${gm.n}`;
        const hdW = Math.min(Math.max(46, Math.round(hdText.length * 7.2) + 18), bw - 36);   // GX 컨트롤 자리(우측 ~20px) 확보
        // group-interact(§50 hotfix, PB-0008) + graph-zorder(§52): GH 헤더 = GROUP_HD(5) — 칩(4) 위 드래그
        //   핸들. 음수면 combo 배경(z0) 뒤에 렌더돼 @antv/g hit-test 에서 combo 에 가려, 헤더 드래그가
        //   node:dragstart 대신 combo:dragstart(클러스터 이동)로 발화된다(라이브 실측 결함 — 헤드리스는
        //   zIndex hit-test 미모델). 헤더 스트립엔 멤버가 없어 시각 회귀 0, cursor:move 로 핸들임을 표시.
        nodes.push({ id: "GH:" + gm.key, type: _METtype, combo: id,
          data: { kind: "group-hd", group: gm.key, schema: id, label: gm.label },
          style: { x: left + 8 + hdW / 2, y: top + 13, size: [hdW, 18], radius: 9,
            fill: gm.tint.hd, stroke: gm.tint.bd, lineWidth: 1, zIndex: _METZ.GROUP_HD, cursor: "move",
            labelText: hdText, labelFill: "#273449", labelFontSize: 10.5, labelFontWeight: 600,
            labelPlacement: "center" } });
        // group-interact(§50): 접기/펼치기 토글 컨트롤(그룹 헤더 우측) — 클릭 전용(드래그 불가).
        nodes.push({ id: "GX:" + gm.key, type: _METtype, combo: id,
          data: { label: gm.collapsed ? "+" : "−", kind: "group-ctl", group: gm.key, schema: id },
          style: Object.assign(_metaCtlStyle(right - 13, top + 13), { size: [16, 16], labelText: gm.collapsed ? "+" : "−", labelFontSize: 14 }) });   // graph-zorder(§52): zIndex 는 _metaCtlStyle 의 CTL(6) — GH(5) 위, 항상 클릭 가능
      });
    }
    L.place.forEach(({ it, lx, top }) => {
      let colLeftX = L.x0 + lx;
      let tx = colLeftX + TXOFF;
      let ty = L.y0 + top + _METLAY.TROW / 2;   // 항목(테이블/용어) 중심 y
      // graph-freeplace: 개별 노드 사용자 드래그 위치 유지(테이블은 종속 컬럼·"X:" ctl 과 함께 델타 시프트,
      //   용어는 자기 위치). colLeftX/ty 를 옮기면 아래 컬럼(colLeftX 기반 x·ty 기반 cyCol)이 자동 동반된다.
      //   clusterOffset(클러스터 전체) 위에 얹히는 개별 이동 — combo 는 자식에 맞춰 auto-fit(반응형 리사이즈 #3).
      const _fp = _metaGraph.nodePos.get(it.key);
      if (_fp && isFinite(_fp[0]) && isFinite(_fp[1])) {
        const ddx = _fp[0] - tx, ddy = _fp[1] - ty;
        colLeftX += ddx; tx += ddx; ty += ddy;
      }
      if (it.label === "Routine") {
        // viewport-cull(§67): 화면 밖 루틴 칩도 미방출(테이블과 동형). §76: 단 선택 노드의 관계 상대는 예외(엣지·상호작용 보존).
        if (!_keepFromCull(it.key) && _offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + realH(g, it))) { _metaGraph._cullPartial = true; return; }   // graph-minimap-fullview(§77): 부분방출 표시
        // graph-funcproc(ADR-016): 함수(ƒ)/프로시저(⚙) 칩 — 검색 매칭 강조는 테이블과 동일 룰.
        //   §18.8 패널(NIT): isTerms 분기보다 먼저 — 스키마 세그먼트 없는 flat-scope Routine 이
        //   terms 클러스터로 강등돼도 용어 칩이 아닌 ƒ/⚙ 보라 칩으로 렌더된다.
        //   freeplace(_fp)·simgroups 배치(lx/top)는 위 공통 시프트가 이미 반영 — Routine 도 자유 배치 유지.
        const rrel = (_metaGraph.mode === "search" && _metaGraph.searchMatchTables && _metaGraph.searchMatchTables.has(it.key))
          ? Math.max(typeof it.rel === "number" ? it.rel : 0, 0.9) : it.rel;
        const rLabel = _metaRoutineIcon(it.routine_type) + " " + (it.name || it.key);
        nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaStateSig(it.key),
          data: { label: it.name || it.key, kind: "routine", fqn: it.fqn, routine_type: it.routine_type || "" },
          style: Object.assign(_metaRoutineStyle(tx, ty, rrel), { labelText: rLabel }) });
        // graph-navfilter(§54⑤): 파라미터 수직 배치 — 컬럼(ERD ordinal)과 동형의 서브노드 방출.
        //   params 는 이미 모델에 로드돼 있어(schema_tables/이웃확장 응답) fetch 없는 동기 토글.
        //   순서는 백엔드 ORDINAL_POSITION 정렬 그대로. XR:/RP: 는 합성 id(모델 노드 아님).
        //   패널 MINOR: terms 클러스터(flat-scope 루틴)는 레이아웃 높이 진행이 TROW 고정이라 파라미터
        //   방출 시 아래 항목과 겹침 — terms 에서는 펼침 미지원(상세 패널 세로 목록으로 열람).
        const plist = (!g.isTerms && _metaGraph.routineExpanded.has(it.key)) ? _metaRoutineParamList(it) : [];
        const _rtOff = plist.length ? _offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + realH(g, it)) : false;   // viewport-cull(§65)
        if (_rtOff) _metaGraph._cullPartial = true;   // graph-minimap-fullview(§77): 뷰포트 사유 파라미터 억제도 부분방출
        if (plist.length && !colLodActive && !_rtOff) {   // col-lod(개요) 또는 viewport-cull(줌인 화면 밖) 시 파라미터 억제(realH 로 높이는 예약됨)
          // routine 칩 폭은 rel-가변(_metaRoutineStyle 과 동일식) — ctl 을 TW/2 고정으로 두면 넓은 칩과 겹침.
          const rw = Math.min(190, _METLAY.TW + (typeof rrel === "number" ? Math.round(rrel * 40) : 0));
          const depIds = ["XR:" + it.key];
          nodes.push({ id: "XR:" + it.key, type: _METtype, combo: id, data: { label: "−", kind: "rctl", routine: it.key },
            style: Object.assign(_metaCtlStyle(tx + Math.round(rw / 2) + 14, ty), { zIndex: _METZ.NODE }) });
          let cyP = ty + _METLAY.TROW / 2 + CDROP + _METLAY.CROW / 2;   // 첫 파라미터 중심 y(컬럼과 동형)
          plist.forEach((ps, i) => {
            const pid = "RP:" + it.key + ":" + i;
            nodes.push({ id: pid, type: "circle", combo: id, states: [], data: { label: ps, kind: "routine-param", routine: it.key },
              style: Object.assign(_metaColStyle(colLeftX + _METLAY.PADX + _METLAY.CIND, cyP), { labelText: ps, fill: _META_GRAPH_COLOR.Routine }) });
            depIds.push(pid);
            cyP += _METLAY.CROW;
          });
          _metaGraph.tableDeps.set(it.key, depIds);   // 드래그 리지드 이동(테이블 종속과 동일 소비처)
        }
        return;
      }
      if (g.isTerms) {
        nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaStateSig(it.key), data: { label: it.name || it.key, kind: "term", fqn: it.fqn }, style: Object.assign(_metaTermStyle(tx, ty, it.rel), { labelText: it.name || it.key }) });
        return;
      }
      // feature-0016 §45: 검색 매칭 강조는 노드 'match' 상태 soft glow(_metaNodeStates)로 이관 — 폭 부스트(trel) 제거.
      // node-role-viz: 분석 완료 테이블 역할 표식 — 칩 색 = 역할색(Okabe-Ito) + 라벨 앞 역할 아이콘(색약·흑백 중복 인코딩).
      const role = _metaRoleOf(it.key);
      const cols = g.colsByTable.get(it.key);
      // viewport-cull(§67): 화면(+마진) 밖 테이블은 **테이블 칩 자체를 미방출**(줌인 대형모델 draw 급감 — 병목
      //   =setData/draw 방출 요소 수). 화면 밖이라 시각 손실 0. 엣지 끝점은 renderEndpoint 가 승격/드롭. combo 는
      //   가시 테이블에 auto-fit. 전체가 화면 밖인 클러스터는 상위에서 통째 컬링(combo 포함). §65 컬럼→테이블 확장.
      if (!_keepFromCull(it.key) && _offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + realH(g, it))) { _metaGraph._cullPartial = true; return; }   // 화면 밖 테이블 컬링(§76: 선택 관계 상대는 예외 — 엣지·상호작용 보존) + §77 부분방출 표시
      const _colSuppressed = colLodActive && cols && cols.length;   // (in-view 테이블) 개요 col-lod 컬럼 억제만
      // col-lod: 억제 시 '▤N' 컬럼수 배지를 라벨 **앞**에 둔다 — _metaTableStyle labelMaxWidth(140) 후미
      //   ellipsis 로 긴 테이블명(예: cc_user_subscription)이 잘려도 배지가 살아남아 '컬럼 억제됨'
      //   affordance 를 보존(리뷰 MINOR — 후미 append 는 배지가 먼저 잘림). realH 예약 gap 도 '펼침' 신호.
      const tLabel = (_colSuppressed ? "▤" + cols.length + " " : "")
        + (role ? _META_ROLE[role].icon + " " : "") + (it.name || it.key);
      nodes.push({ id: it.key, type: _METtype, combo: id, states: _metaStateSig(it.key), data: { label: it.name || it.key, kind: "table", fqn: it.fqn, role: role || null }, style: Object.assign(_metaTableStyle(tx, ty, it.rel, role), { labelText: tLabel }) });
      if (cols && cols.length && !_colSuppressed) {
        const depIds = ["X:" + it.key];   // graph-drag(REQ ②): 종속 UI = 접기 ctl + 컬럼 노드들
        nodes.push({ id: "X:" + it.key, type: _METtype, combo: id, data: { label: "−", kind: "ctl", table: it.key },
          // graph-zorder(§52, 패널 ux MINOR): 흐름 내 per-table ctl 은 NODE 밴드 — CTL(6) 전역 최상층이면
          //   타 칩을 그 위로 자유배치했을 때 "−" 가 뚫고 나와 허위 소속(원거리 접기)으로 오독된다.
          //   자기 칩과는 비겹침(+14px 우측) + 같은 밴드 삽입순이라 클릭성 손실 없음. GX/XS(코너 앵커)는 CTL 유지.
          style: Object.assign(_metaCtlStyle(tx + Math.round(_METLAY.TW / 2) + 14, ty), { zIndex: _METZ.NODE }) });
        let cyCol = ty + _METLAY.TROW / 2 + CDROP + _METLAY.CROW / 2;   // 첫 컬럼 중심 y
        cols.slice().sort(_metaGraphColCmp).forEach((c) => {
          nodes.push({ id: c.key, type: "circle", combo: id, states: _metaStateSig(c.key), data: { label: c.name || c.key, kind: "column", fqn: c.fqn }, style: Object.assign(_metaColStyle(colLeftX + _METLAY.PADX + _METLAY.CIND, cyCol), { labelText: c.name || c.key }) });
          depIds.push(c.key);
          cyCol += _METLAY.CROW;
        });
        _metaGraph.tableDeps.set(it.key, depIds);   // graph-drag(REQ ②): 테이블 → 종속 노드 id 맵
      }
    });
  });
  // 엣지 조립 — HAS_TABLE/HAS_COLUMN 은 containment 라 제외.
  //   graph-reltrace ①: REFERENCES(Column→Column) 끝점을 **렌더된 id 로 해소**한다 — 컬럼이
  //   렌더돼 있으면 컬럼-레벨, 아니면 소속 테이블 노드로 승격. 두 테이블이 접힌 상태에서도 테이블
  //   간 관계 엣지가 보이도록(사용자 요청: "테이블 더블클릭 전까지 관계 미표시" 해소). 같은 두
  //   렌더 끝점으로 승격된 다수 컬럼-쌍은 하나의 집계 엣지로 dedupe 하고, 상태는 최강(trusted>
  //   candidate)을 채택하며 하위 컬럼-쌍을 pairs 로 실어 추적/툴팁에 쓴다.
  const present = new Set(nodes.map((n) => n.id));
  const renderEndpoint = (nodeKey) => {   // 컬럼 미렌더 시 소속 테이블 → 접힌 스키마 카드(SC:) 순 승격
    if (present.has(nodeKey)) return nodeKey;
    // 컬럼 노드가 모델에 없어도(접힌 스키마 = 테이블만 로드) REFERENCES 끝점은 항상 컬럼 키이므로
    // 키 문자열에서 소속 테이블 키를 직접 도출한다(_metaColParent 는 fqn 없으면 key 로 파싱).
    const gn = _metaGraph.nodes.get(nodeKey);
    const pk = _metaColParent(nodeKey, gn && gn.fqn);
    if (pk && present.has(pk)) return pk;
    // §57(사용자 요구 ①): 테이블도 미렌더(소속 스키마 접힘) → 스키마 카드로 승격 — 혼합 상태
    //   (한쪽 펼침·한쪽 카드)에서도 관계선이 카드까지 이어진다. 카드 자체 미렌더면 기존대로 드롭.
    //   스키마 세그먼트는 **원본 키**에서 도출(2-세그먼트 테이블 키는 colParent 가 dot 를 잃음).
    const sk = _metaCatParent(nodeKey, gn && gn.fqn);
    return (sk && present.has("SC:" + sk)) ? ("SC:" + sk) : null;
  };
  // §57.5(사용자 피드백 "흐림 기준 체감 무작위"): 엣지 흐림(dim)은 단일 규칙 — **양끝이 모두 밝으면
  //   선도 밝다**(밝은 부분그래프 = 선택+1-hop 인접의 폐포). 예전 '선택에 직접 닿는 선만 선명'은
  //   밝은 이웃 노드 사이의 선이 흐려져 사람 눈에 무작위로 읽혔다. 무선택(fa=null)이면 false —
  //   dim 은 fa 존재 시에만 발동(의미 분리).
  // lod-hl-declutter(사용자 결정 2026-07-10): dim(lit, 유도 부분그래프 전체)과 LOD-keep(litSelf,
  //   선택 노드 직접선만)을 **분리**한다. 예전엔 lit() 을 LOD 축약 예외에도 재사용해, 허브 노드를
  //   선택하면 이웃↔이웃 간 엣지까지 전부 예외가 돼 줌아웃 간소화가 통째로 무력화됐다(사용자 실측).
  //   이제 줌아웃 축약 예외는 **선택 노드에 직접 닿는 선(양끝 중 하나가 self)** 만 — 이웃 클러터는
  //   하이라이트 상태에서도 정상 간소화되고, 선택 노드의 관계는 계속 보존된다. dim(밝기)은 불변.
  const fa = _metaGraph.focusAdj;
  const lit = (rid) => {
    if (!fa) return false;
    const r = String(rid || "");
    const mk = r.startsWith("SC:") ? r.slice(3) : r;
    if (fa.self.has(mk) || fa.nodes.has(mk)) return true;
    // 컬럼-레벨 끝점(모델 밖 키 포함)은 소속 테이블로 접어 판정.
    const gn = _metaGraph.nodes.get(mk);
    if (!gn || gn.label === "Column") {
      const pk = _metaColParent(mk, gn && gn.fqn);
      if (pk && (fa.self.has(pk) || fa.nodes.has(pk))) return true;
    }
    return false;
  };
  const selTouch = lit;   // 호출부 명칭 호환(의미: 밝은 부분그래프 소속 여부 — dim 용)
  // lod-hl-declutter(§64): 끝점이 **선택 노드 자체**(self, 테이블이면 자기 컬럼 포함)인지 — LOD 축약 예외 전용.
  //   lit 과 달리 1-hop 이웃(fa.nodes)은 제외한다. SC: 접두·컬럼→소속테이블 접기는 lit 과 동일 규칙.
  const litSelf = (rid) => {
    if (!fa) return false;
    const r = String(rid || "");
    const mk = r.startsWith("SC:") ? r.slice(3) : r;
    if (fa.self.has(mk)) return true;
    const gn = _metaGraph.nodes.get(mk);
    if (!gn || gn.label === "Column") {
      const pk = _metaColParent(mk, gn && gn.fqn);
      if (pk && fa.self.has(pk)) return true;
    }
    return false;
  };
  // LOD 축약 예외: 선택 노드에 직접 닿는 선(양끝 중 하나가 self)만 보존.
  const keepLodFor = (a, b) => litSelf(a) || litSelf(b);
  // §67 이후: focus 밖 엣지는 아래 hlHide 로 build 에서 제거되므로 dimIf 의 dim 분기(fa && !hl)는
  //   엣지 경로에서 정상적으로 도달하지 않는다. dimIf 는 방어적 안전망으로 남겨둔다 — 향후 hlHide
  //   가드 없이 push site 가 추가되면 최소한 dim(전량 원색 노출 방지)으로 fail-soft 한다.
  const dimIf = (st, hl) => {
    if (fa && !hl) {
      // §57.6(사용자 실측 "화살표 첨단만 밝음"): strokeOpacity 는 path 선만 흐리고 화살촉(마커
      //   fill)은 원색 잔존 — 전체 opacity 로 화살촉·라벨까지 일괄 침강.
      st.opacity = Math.min(st.opacity || 1, 0.12);
      st.strokeOpacity = Math.min(st.strokeOpacity || 1, 0.12);
      // 패널 MINOR: count 라벨/배경은 dim 시 라벨 키 자체 제거.
      if (st.labelText !== undefined) { delete st.labelText; delete st.labelBackground; delete st.labelBackgroundFill; delete st.labelBackgroundOpacity; }
    }
    return st;
  };
  // §67(hl-edge-hide, 사용자 리포트): 상대 하이라이트 활성(fa) 시 focus 부분그래프 밖 엣지는
  //   dim(0.12)이 아니라 **build 에서 제거**한다. dim(0.12) 유지의 폐해 두 가지 — (a) 거의 비가시인데
  //   non-focus 엣지가 전량 살아 있어 G6 가 path 지오메트리·hit-test·매 페인트를 계속 수행(대형 스코프
  //   수백~수천 엣지에서 순수 낭비) (b) G6 v5 기본 dirty-rectangle 렌더가 opacity 1→0.12 dim 전환 시
  //   이전 원색 엣지 픽셀을 캔버스에 잔류시켜 "커서 이동에 따라 깜빡이는 유령 관계선"(사용자 관측)을
  //   만든다. non-focus 엣지를 아예 방출하지 않으면 둘 다 원천 해소되고, 노드 dim(0.38,
  //   _metaBakeBaseOpacity)은 그대로라 focus 부분그래프 강조 효과는 유지된다. 집계 엣지는 같은 (rs,rt)로
  //   승격된 모든 컬럼-쌍이 동일 keep 이므로 keep 판정 지점에서 걸러 colLevel·agg 누적을 함께 차단한다.
  //   무선택(fa=null)이면 항상 false(제거 안 함) → 기존 전체 표시 동작 보존. lodDropped 는 줌아웃 축약
  //   전용 지표라 여기선 증가시키지 않는다(‘줌아웃 축약’ 오안내 방지). LOD-drop 과 동일 계열의 build 제외.
  const hlHide = (hl) => !!(fa && !hl);
  // §57(사용자 검토 ①·declutter): 중간 줌 LOD — 임계 미만 줌 + 대형 모델에서 무상태(FK)·비크로스
  //   단건 선을 축약하고 의미 신호(trusted/candidate/교차DB/집계/SCHEMA_REF/선택 노드 직접선)만 남긴다.
  //   우선순위: 사용자 명시 숨김(hiddenKinds) > 선택 노드 직접선 보존(keepLodFor) > LOD 축약.
  //   (lod-hl-declutter: 예전 '하이라이트 인접 보존'은 이웃 부분그래프 전체를 예외로 둬 간소화를 무력화 → self-직접선만.)
  let zoomNow = 1;
  try { if (_metaGraph.graph) zoomNow = _metaGraph.graph.getZoom() || 1; } catch (_) {}
  const lodActive = zoomNow < _META_EDGE_LOD_ZOOM && _metaGraph.edges.size > _META_EDGE_LOD_MIN;
  let lodDropped = 0;
  const aggMap = new Map();   // "src::tgt[::RU]" → 집계 엣지(승격분 — REFERENCES/ROUTINE_USES 분리 집계)
  _metaGraph.edges.forEach((e) => {
    // graph-navfilter(§54②): 관계선 토글 — 방출만 차단(모델 유지: _metaRelAdjacency 가 모델을 읽어
    //   배치 순서 불변 = 엣지 토글로 테이블이 점프하지 않음. 모델 삭제 금지 — 재토글 복원·접기 관례).
    if (_metaGraph.hiddenKinds.has("edges")) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_ROUTINE") return;
    // §57: 스키마-쌍 집계 엣지(백엔드 scope_schemas 동봉) — 양쪽 모두 접힌 카드일 때만 카드간 렌더
    //   (한쪽이라도 펼침이면 상세/승격 엣지가 대체 — 이중 표현 방지).
    if (e.type === "SCHEMA_REF") {
      const a = present.has("SC:" + e.source) ? ("SC:" + e.source) : null;
      const b = present.has("SC:" + e.target) ? ("SC:" + e.target) : null;
      if (!a || !b) return;
      const keep = selTouch(a) && selTouch(b);
      if (hlHide(keep)) return;   // §67: 하이라이트 시 focus 밖 카드간 관계선 제거(dim 대신)
      edges.push({ id: e.id, source: a, target: b,
        data: { label: "SCHEMA_REF", count: e.count || 1, ref_count: e.ref_count, use_count: e.use_count },
        style: dimIf(_metaSchemaRefEdgeStyle(e.count), keep) });
      return;
    }
    if (e.type !== "REFERENCES") {
      // §57: ROUTINE_USES 도 승격 경로 참여(접힌 카드로의 사용선) — 그 외(DESCRIBES/RELATED_TERM 등)는
      //   기존대로 양끝 직접 렌더 시에만.
      if (e.type === "ROUTINE_USES") {
        const srcN = _metaGraph.nodes.get(e.source), tgtN = _metaGraph.nodes.get(e.target);
        // §18.8 패널 MINOR: kind 필터로 숨긴 루틴의 사용선이 카드 승격으로 누출되지 않게 —
        //   빌드 입력 제외(§54②)와 동일 분류식(빈값·미상 = procedure).
        if (srcN && srcN.label === "Routine") {
          const rk0 = (srcN.routine_type === "function") ? "function" : "procedure";
          if (_metaGraph.hiddenKinds.has(rk0)) return;
        }
        const rs = renderEndpoint(e.source), rt = renderEndpoint(e.target);
        if (!rs || !rt || rs === rt) return;
        if (String(rs).startsWith("SC:") && String(rt).startsWith("SC:")) return;   // 패널 MAJOR: SCHEMA_REF 소유
        // §57(요구 ②): 교차DB 판별 — AGE 속성(cross_ds, §57 투영) 우선 + 키 스키마-세그먼트 비교 폴백
        //   (배포 직후 기존 엣지 속성 부재 창 커버). 세그먼트 null(스키마 미상)은 교차로 오판하지 않음.
        const ss = _metaCatParent(e.source, srcN && srcN.fqn), ts = _metaCatParent(e.target, tgtN && tgtN.fqn);
        const xr = !!e.cross_ds || (!!ss && !!ts && ss !== ts);
        const keep = selTouch(rs) && selTouch(rt);
        const keepLod = keepLodFor(rs, rt);   // lod-hl-declutter(§64): 축약 예외는 self-직접선만
        if (hlHide(keep)) return;   // §67: 하이라이트 시 focus 밖 루틴 사용선 제거(colLevel·agg 공통 — LOD 도달 전)
        if (rs === e.source && rt === e.target) {
          if (lodActive && !keepLod && !xr) { lodDropped += 1; return; }
          edges.push({ id: e.id, source: rs, target: rt,
            data: { label: e.type, status: e.status, cross_ds: xr ? 1 : 0, relation_type: e.relation_type },
            style: dimIf(_metaRoutineEdgeStyle(e.relation_type, xr), keep) });
          return;
        }
        const ak = rs + "::" + rt + "::RU";
        let agg = aggMap.get(ak);
        if (!agg) { agg = { id: "agg:" + ak, kind: "ROUTINE_USES", source: rs, target: rt, status: "", count: 0, pairs: [], crossDs: false, keep: false, keepLod: false }; aggMap.set(ak, agg); }
        agg.count += 1;
        agg.crossDs = agg.crossDs || xr;
        agg.keep = agg.keep || keep;
        agg.keepLod = agg.keepLod || keepLod;   // lod-hl-declutter
        if (agg.pairs.length < 8) agg.pairs.push({ s: e.source, t: e.target, status: e.relation_type || "read" });
        return;
      }
      if (present.has(e.source) && present.has(e.target)) {
        const keep = selTouch(e.source) && selTouch(e.target);
        if (hlHide(keep)) return;   // §67: 하이라이트 시 focus 밖 기타 관계선(DESCRIBES/RELATED_TERM 등) 제거(LOD 도달 전)
        if (lodActive && !keepLodFor(e.source, e.target)) { lodDropped += 1; return; }   // lod-hl-declutter(§64): 축약 예외는 self-직접선만
        edges.push({ id: e.id, source: e.source, target: e.target, data: { label: e.type, status: e.status },
          style: dimIf(_metaEdgeStyleFor(e.status), keep) });
      }
      return;
    }
    const rs = renderEndpoint(e.source), rt = renderEndpoint(e.target);
    if (!rs || !rt || rs === rt) return;   // 미렌더 끝점 or 동일 테이블 내부(intra-table) 제외
    // §18.8 패널 MAJOR: 양끝 모두 카드로 승격되면 SCHEMA_REF(백엔드 스키마-쌍 집계)가 카드간
    //   표현을 소유 — 펼쳤다 접은 스키마의 모델 잔존 엣지가 이중(SC:↔SC: 승격 + SCHEMA_REF)으로
    //   그려지는 것을 차단한다.
    if (String(rs).startsWith("SC:") && String(rt).startsWith("SC:")) return;
    const keep = selTouch(rs) && selTouch(rt);
    const keepLod = keepLodFor(rs, rt);   // lod-hl-declutter(§64): 축약 예외는 self-직접선만
    if (hlHide(keep)) return;   // §67: 하이라이트 시 focus 밖 REFERENCES(컬럼-레벨·카드 승격 agg) 제거(LOD 도달 전)
    const colLevel = (rs === e.source && rt === e.target);
    if (colLevel) {
      // 양끝 컬럼 렌더 — 정밀 컬럼-레벨 엣지(기존 동작 유지). crossds-rel: cross_ds 면 마젠타 점선.
      if (lodActive && !keepLod && !e.cross_ds && e.status !== "trusted" && e.status !== "candidate") { lodDropped += 1; return; }
      edges.push({ id: e.id, source: rs, target: rt, data: { label: e.type, status: e.status, colEdge: true, cross_ds: e.cross_ds || 0 }, style: dimIf(_metaEdgeStyleFor(e.status, e.cross_ds), keep) });
      return;
    }
    // 한쪽 이상이 테이블/카드로 승격 — 집계 엣지에 병합(dedupe + 상태 승급 + pairs 누적).
    const ak = rs + "::" + rt;
    let agg = aggMap.get(ak);
    if (!agg) { agg = { id: "agg:" + ak, kind: "REFERENCES", source: rs, target: rt, status: e.status || "", count: 0, pairs: [], crossDs: false, keep: false, keepLod: false }; aggMap.set(ak, agg); }
    agg.count += 1;
    agg.crossDs = agg.crossDs || !!e.cross_ds;   // crossds-rel: 집계 쌍 중 하나라도 교차DB 면 교차DB 로 표식
    agg.keep = agg.keep || keep;
    agg.keepLod = agg.keepLod || keepLod;   // lod-hl-declutter
    if (agg.pairs.length < 8) agg.pairs.push({ s: e.source, t: e.target, status: e.status });
    if (e.status === "trusted" || (e.status === "candidate" && agg.status !== "trusted")) agg.status = e.status;   // 최강 상태 채택
  });
  aggMap.forEach((agg) => {
    if (lodActive && !agg.keepLod && !agg.crossDs && agg.count <= 1 && agg.status !== "trusted" && agg.status !== "candidate") { lodDropped += 1; return; }
    // 집계 엣지는 여러 컬럼/루틴-쌍을 대표하므로 살짝 굵게(count>1) — style 미지원 키는 넣지 않음(G6 안전).
    const st = (agg.kind === "ROUTINE_USES")
      ? (() => { const s = _metaRoutineEdgeStyle("", agg.crossDs); delete s.startArrow; return s; })()
      : _metaEdgeStyleFor(agg.status, agg.crossDs);
    if (agg.count > 1) st.lineWidth = (st.lineWidth || 1.4) + 0.8;
    edges.push({ id: agg.id, source: agg.source, target: agg.target,
      data: { label: agg.kind, status: agg.status, aggregated: true, count: agg.count, pairs: agg.pairs, cross_ds: agg.crossDs ? 1 : 0 },
      style: dimIf(st, agg.keep) });
  });
  _metaGraph._lodDropped = lodDropped;   // §57: 상태줄 안내용(축약 규모)
  _metaBakeBaseOpacity(nodes);           // §57.9: dimmed 해제 시 opacity 복원(아래 함수 주석 참조)
  // graph-initview: 렌더된 요소 id 집합(노드+combo) — setElementState/focus 가 미렌더 요소를 건드리지 않게.
  _metaGraph.renderedIds = new Set(nodes.map((n) => n.id).concat(combos.map((c) => c.id)));
  return { combos, nodes, edges };
}

// §57.9(사용자 4차 실측 — "재선택 노드가 흐린 상태로 남음"): 모든 노드 base style 에 opacity 를
//   **명시**한다. dimmed 상태는 opacity 0.38 을 얹지만, selected/analyzed 등 다른 상태는 opacity 를
//   지정하지 않는다. G6 v5 는 어떤 상태가 제거될 때 그 상태가 세팅한 속성을 base 에 값이 없으면
//   되돌리지 못한다 — 그래서 dimmed→selected 전환 후에도 keyShape opacity 가 0.38 로 stale 하게
//   남았다(getElementState 는 ["analyzed","selected"] 인데 실제 렌더 opacity=0.38, 실측 확인). base 에
//   dimmed 여부를 **base opacity 에 직접 굽는다**(dim=0.38 / lit=1) — 상태 레이어의 apply/revert 동작에
//   전혀 의존하지 않아 dim↔lit 양방향 전환이 결정적이다. setData 가 매 build 이 값을 keyShape 에 직접
//   기입하므로, 과거 stale 하게 남던 0.38(선택인데 흐림) 도, 반대로 dimmed 미적용도 원천 차단.
//   dimmed G6 상태 config 는 제거했다(base 와 이중 적용 시 곱셈 과침강 위험) — setElementState 침강
//   경로는 없고(dim↔lit 은 항상 rebuild 동반), 침강은 이 base bake 가 전담한다.
function _metaBakeBaseOpacity(nodes) {
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    if (!n || !n.style) continue;
    const dim = Array.isArray(n.states) && n.states.indexOf("dimmed") >= 0;
    n.style.opacity = dim ? _META_DIM_OPACITY : 1;
  }
}

// graph-product-cat(§43): 제품 카테고리 개요 전용 빌드 — Product(좌열)·Datasource(우열) rect 노드 +
//   USES 엣지. combo 미사용(결정론 2-열 배치). 여러 제품이 공유하는 datasource 는 1개 노드로 dedup(백엔드가
//   이미 dedup)하고 각 제품→datasource 엣지를 그린다. 노드 클릭: Datasource → 그 데이터소스 그래프로 drill,
//   Product → 그 제품만 focus(단일 제품 개요).
function _metaG6BuildProducts() {
  _metaGraph.tableDeps = new Map();
  _metaGraph.firstElementId = null;
  _metaGraph._colLodActive = false;   // col-lod(§61): products 뷰는 컬럼/LOD 없음 — 스키마 빌드가 남긴 stale 플래그 소거(상태줄 거짓 마커 방지). _metaG6Build 는 products 모드에서 여기로 조기 return 하므로 스키마 빌드의 산정을 못 거친다.
  _metaGraph._aggActive = false;      // agg-lod(§63): products 뷰는 집계 없음 — stale 플래그 소거.
  _metaGraph._cullActive = false; _metaGraph._cullVp = null; _metaGraph._cullPartial = false; _metaGraph._miniSeedRun = false; _metaGraph._cullSuspendOnce = false; _metaGraph._miniFullSig = null; if (_metaGraph._miniSeedTimer) { try { clearTimeout(_metaGraph._miniSeedTimer); } catch (_) {} _metaGraph._miniSeedTimer = null; }   // viewport-cull(§65)+§77: products 뷰 stale 소거(시딩 가드·전체서명·타이머 포함).
  const prods = [], dss = [];
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Product") prods.push(n);
    else if (n.label === "Datasource") dss.push(n);
  });
  prods.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  dss.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const nodes = [], edges = [];
  const TOP = 40, ROWH = 66, RH = 46;
  const PW = 240, PX = 40, DW = 230, DX = 440;   // 제품 좌열 / 데이터소스 우열
  prods.forEach((p, i) => {
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = p.key;
    const cy = TOP + i * ROWH + RH / 2;
    const cnt = (typeof p.datasource_count === "number") ? p.datasource_count : null;
    nodes.push({ id: p.key, type: _METtype, states: _metaStateSig(p.key),
      data: { label: p.name || p.key, kind: "product" },
      style: { x: PX + PW / 2, y: cy, size: [PW, RH], radius: 10, zIndex: _METZ.NODE,
        fill: "#e7f4ec", stroke: _META_GRAPH_COLOR.Product, lineWidth: 1.6,
        labelText: "🗂 " + (p.name || p.key) + (cnt != null ? "  · " + cnt : ""),
        labelPlacement: "center", labelFill: "#1c5c39", labelFontSize: 12, labelFontWeight: 700,
        labelMaxWidth: PW - 18, cursor: "pointer" } });
  });
  dss.forEach((d, i) => {
    if (!_metaGraph.firstElementId) _metaGraph.firstElementId = d.key;
    const cy = TOP + i * ROWH + RH / 2;
    nodes.push({ id: d.key, type: _METtype, states: _metaStateSig(d.key),
      data: { label: d.name || d.key, kind: "datasource", scope: d.scope_key || "" },
      style: { x: DX + DW / 2, y: cy, size: [DW, RH], radius: 10, zIndex: _METZ.NODE,
        fill: "#eef6f1", stroke: _META_GRAPH_COLOR.Datasource, lineWidth: 1.4,
        labelText: "🔗 " + (d.name || d.key),
        labelPlacement: "center", labelFill: "#20603f", labelFontSize: 11.5, labelFontWeight: 600,
        labelMaxWidth: DW - 18, cursor: "pointer" } });
  });
  const present = new Set(nodes.map((n) => n.id));
  _metaGraph.edges.forEach((e) => {
    if (!e || e.type !== "USES") return;
    if (!present.has(e.source) || !present.has(e.target)) return;
    edges.push({ id: e.id, source: e.source, target: e.target, data: { label: "USES" },
      style: { stroke: "#8fbfa3", lineWidth: 1.5, endArrow: true, zIndex: _METZ.EDGE } });   // 실선(lineDash 생략 — G6 크래시 방지)
  });
  _metaBakeBaseOpacity(nodes);   // §57.9: 제품/데이터소스 뷰도 동일 base opacity 명시(일관성)
  _metaGraph.renderedIds = new Set(nodes.map((n) => n.id));
  return { combos: [], nodes, edges };
}

// graph-initview: 모델 key → 실제 렌더된 요소 id (접힌 스키마 카드는 "SC:"+key). 미렌더면 null.
function _metaRenderedIdFor(key) {
  const r = _metaGraph.renderedIds;
  if (!r || !key) return null;
  if (r.has(key)) return key;
  if (r.has("SC:" + key)) return "SC:" + key;
  return null;
}

// reltrace-colnav(2026-07-10): 대상 키가 직접 렌더돼 있지 않을 때 **화면에 있는 가장 가까운 조상**의
//   렌더 id 를 찾는다 — 컬럼(테이블 미펼침) → 소속 테이블 → 접힌 스키마 카드(SC:) 순 승격.
//   _metaG6Build 의 renderEndpoint 승격 규칙과 동형이되, 여기선 실제 렌더 집합(renderedIds) 기준으로
//   해소한다. 단일클릭 카메라 팬이 미렌더 컬럼에서 "화면에 없음"으로 죽지 않고 소속 테이블/카드로
//   시선을 옮기게 하는 것이 목적. 조상도 미렌더(스키마 미로드·§67 뷰포트 컬링 등)면 null.
function _metaRenderedAncestorFor(key) {
  if (!key) return null;
  const gn = _metaGraph.nodes.get(key);
  const pk = _metaColParent(key, gn && gn.fqn);   // 컬럼 → 소속 테이블 키
  if (pk) { const r = _metaRenderedIdFor(pk); if (r) return r; }
  const sk = _metaCatParent(key, gn && gn.fqn);    // → 소속 스키마 키(접힘 시 SC: 카드)
  if (sk) { const r = _metaRenderedIdFor(sk); if (r) return r; }
  return null;
}

// 모델 → 화면 반영(전체 재구성 setData + draw). fit=true 면 전체 맞춤.
//   ⚠ 의도적 설계(BLUEPRINT §2 대비 divergence): roots/search/neighbor 전 모드가 **결정론 grid(setData+draw)**.
//   blueprint 초안의 search/neighbor=render()+d3-force 는 채택 안 함 — force 는 ④(클러스터 뒤섞임)를 재유발하고
//   POC 가 검증한 무-shuffle 보장을 깬다. 교차 스키마 이웃도 자기 스키마 combo 의 grid 셀에 배치(force 아님).
//   이 주석은 후속 리뷰어가 render()+force 로 "되돌리는" 회귀를 막기 위함(review MINOR-2).
// §57.8(하이라이트 신뢰성 재설계): 모든 bake 는 이 직렬화 게이트를 지난다 — setData/draw 가 겹치면
//   늦게 끝난 쪽이 먼저 끝난 쪽의 화면(선택 점등·dim 재구성)을 되돌리고, 그 사이 명령형
//   setElementState 는 유실되는데 _stateCache 는 "적용됨"으로 남아 2.5s 폴도 영구 no-op — 사용자
//   실측 "무너진 상태 유지"의 기전. 진행 중이면 재실행 1회로 병합(re-run 은 최신 모델을 읽으므로
//   마지막 상태로 수렴), fit 은 OR 병합. 반환 promise 는 병합분 포함 전체 드레인 완료를 뜻한다.
// graph-minimap-reuse(사용자 요구: "화면 구성이 갱신되었을 경우, 한 번 draw 한 전체 이미지를 재사용"):
//   미니맵(G6 v5 minimap plugin)이 depiction 하는 **기하**만 해시한다 — 요소 id·부모combo·위치(x,y)·크기·엣지 끝점.
//   시각 상태(states[]·fill·opacity·역할 칩 색)는 **의도적으로 제외**한다:
//     ① 미니맵은 168×112px 에 수백~수천 노드를 그려 노드 하나가 sub-px~1px → 상태색이 시각적으로 무의미.
//     ② 이 앱은 선택·상대하이라이트·역할 도착(2.5s 폴)·busy 등 '상태-only' 변경으로도 _metaG6Apply(setData+draw)
//        를 20+ 지점에서 자주 돈다. 매 draw 의 AFTER_DRAW 가 minimap.renderMinimap() 을 발동 → 전 요소 key-shape 를
//        cloneNode 로 전량 재복제(수천 노드면 매번 큰 고정비). 기하가 동일하면 그 재복제는 순수 낭비.
//   본 서명이 직전 미니맵 렌더와 같으면 _metaPatchMinimapReuse 가 renderMinimap 을 skip → '한 번 draw 한 전체 이미지'
//   를 재사용한다. 기하가 바뀌는 경로(펼침/접기/드래그/LOD 밴드/스코프 재적재/검색 prune)는 서명이 바뀌어 정상 재복제.
//   위치는 0.25px 로 양자화(미소 부동소수 흔들림 무시). combo 위치는 자식 auto-fit(getContentBBox)이라 자식 노드
//   위치가 서명에 있으면 암묵 포함 — combo 는 id 존재만 해시(추가/삭제 감지). built 미정의 시 null → 항상 재복제(안전).
//   §77(graph-minimap-fullview): 서명은 방출된 _built 기준이라 뷰포트 컬링 build 에선 부분집합 서명이 된다 —
//   재복제 허용 여부는 _cullPartial(부분방출 플래그)로 별도 게이트(부분방출 build 는 전체 이미지 유지, 래퍼 참조).
function _metaMinimapGeomSig(built) {
  if (!built) return null;
  let h = 0x811c9dc5 >>> 0;   // FNV-1a 32bit offset basis
  const mix = (v) => {
    const s = (v == null) ? "" : String(v);
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    h ^= 0x2c; h = Math.imul(h, 0x01000193) >>> 0;   // 필드 구분자(comma) — 인접 필드 경계 모호성 제거
  };
  const q = (n) => mix((typeof n === "number" && isFinite(n)) ? Math.round(n * 4) : "");   // 0.25px 양자화
  const nodes = built.nodes || [];
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i], st = n.style || {};
    mix(n.id); mix(n.combo || "");
    q(st.x); q(st.y);
    const sz = st.size;
    if (Array.isArray(sz)) { q(sz[0]); q(sz[1]); } else q(sz);
  }
  const combos = built.combos || [];
  for (let i = 0; i < combos.length; i++) mix(combos[i].id);
  const edges = built.edges || [];
  for (let i = 0; i < edges.length; i++) { const e = edges[i]; mix(e.source); mix(e.target); }
  // 길이 프리픽스로 서로 다른 카디널리티가 같은 해시로 접히는 확률을 더 낮춘다.
  return nodes.length + ":" + combos.length + ":" + edges.length + ":" + (h >>> 0);
}

async function _metaG6Apply(fit) {
  _metaGraph._applyWantFit = !!(_metaGraph._applyWantFit || fit);
  if (_metaGraph._applyLoop) { _metaGraph._applyAgain = true; return _metaGraph._applyLoop; }
  _metaGraph._applyLoop = (async () => {
    try {
      do {
        _metaGraph._applyAgain = false;
        const fitNow = _metaGraph._applyWantFit;
        _metaGraph._applyWantFit = false;
        await _metaG6ApplyOnce(fitNow);
      } while (_metaGraph._applyAgain);
    } finally { _metaGraph._applyLoop = null; }
  })();
  return _metaGraph._applyLoop;
}
async function _metaG6ApplyOnce(fit) {
  const g = _metaGraph.graph;
  if (!g) return;
  // graph-ctxmenu(review): 재구성으로 노드가 이동하면 열린 메뉴 좌표가 스테일 — 재적용 시 메뉴 닫기.
  if (typeof _metaGraphCtxHide === "function") _metaGraphCtxHide();
  // §57.8: busy 는 build states 로 bake 되므로 rebuild 가 시각을 지우지 않는다 — 맵도 유지(소유 op 가
  //   해제). 안전망: 소유 op 가 죽어 남은 stale busy 는 TTL(30s)로 소거 — 과거 busy 게이트들이
  //   fail-closed 로 하이라이트 bake·폴 승격을 영구히 막던 원인을 구조적으로 제거.
  if (!_metaGraph._busyTs) _metaGraph._busyTs = new Map();
  {
    const now = Date.now();
    _metaGraph._busyKeys.forEach((v, k) => {
      const ts = _metaGraph._busyTs.get(k);
      if (ts == null) _metaGraph._busyTs.set(k, now);
      else if (now - ts > 30000) { _metaGraph._busyKeys.delete(k); _metaGraph._busyTs.delete(k); }
    });
  }
  try {
    const _built = _metaG6Build();
    // graph-minimap-reuse: setData 에 넘긴 바로 그 데이터로 미니맵 기하 서명을 산정해 _miniGeomSig 에 싣는다.
    //   패치된 minimap.renderMinimap 이 AFTER_DRAW(debounce) 창에서 이 값을 직전 렌더 서명과 비교 → 동일하면 재복제 skip.
    try { _metaGraph._miniGeomSig = _metaMinimapGeomSig(_built); } catch (_) { _metaGraph._miniGeomSig = null; }
    g.setData(_built);
    // graph-expand-perf fix(프리즈): setData 가 data.states(_metaG6Build 의 states:)로 모든 노드 상태를 이미 bake 한다.
    //   예전엔 _stateCache 를 clear 만 해서, 직후 _metaGraphRefreshStates(syncMarkers·2.5s 폴)가 cold 로 **전 노드
    //   setElementState** 를 돌렸다 — G6 v5 setElementState 는 건당 ~50ms 라 수백 노드면 수 초 메인스레드 프리즈
    //   (실측: 200노드 재적용 = 10초). 대신 캐시를 방금 bake 된 signature 로 채워 rebuild 직후 refresh 를 no-op 로
    //   만든다(진짜 변한 마커만 이후 소량 setElementState). §57.8: bake states=_metaStateSig(busy 포함)라 캐시 sig 와 일치.
    _metaGraph._stateCache.clear();
    _metaGraph.nodes.forEach((n) => { _metaGraph._stateCache.set(n.key, _metaCacheSig(n.key)); });   // node-role-viz: 역할 suffix 포함 — rebuild 가 역할 칩 색을 이미 bake 했으므로 직후 refresh 는 no-op
    await g.draw();
    // graph-minimap-reuse: 미니맵 재사용 패치는 **첫 draw 이후** 걸어야 한다 — G6 v5 Graph 는 생성자에서 context.plugin
    //   을 만들지 않고 initRuntime()(= 첫 draw 의 prepare() 가 lazy 실행)이 만든다. 따라서 init 시점 getPluginInstance("minimap")
    //   는 context.plugin 부재로 실패(→ 패치 no-op, 최적화 사멸). draw 완료 후엔 plugin 인스턴스가 존재하므로 여기서 건다.
    //   멱등(__reusePatched)이라 매 apply 호출돼도 첫 성공 래핑 1회만 유효(이후 즉시 return).
    _metaPatchMinimapReuse(g);
    // graph-minimap-fullview(§77 — 시딩 예약): 컬링 부분방출인데 미니맵 전체 이미지가 없거나(대형 모델
    //   fit-클램프로 무컬링 build 가 자연 발생 안 하는 케이스) **현재 전체 기하와 불일치**(줌인 중 펼침/필터
    //   등 구조 변경 — 접힘 카드 시점 이미지 오인 방지)면 컬링-유예 build 를 300ms idle 로 예약. 그 build 는
    //   전량 방출(비용 = pre-§65 빌드 1프레임)로 미니맵이 전체를 재복제·서명 갱신. _metaG6Apply 직렬화가
    //   진행 중 apply 와의 경합을 흡수하고, _miniSeedRun 가드(전체 렌더 마킹 시 해제)가 중복 예약을 차단한다.
    try {
      const _mm = g.getPluginInstance && g.getPluginInstance("minimap");
      if (_mm && _mm.__reusePatched && _metaGraph._cullPartial
          && (_mm.__fullImageSig == null || _mm.__fullImageSig !== _metaGraph._miniFullSig)) {
        _metaMinimapSeedKick();
      }
    } catch (_) { /* 시딩은 최적화 — 실패해도 정확성 무관(폴백 유지) */ }
    _metaGraphZAssert();   // graph-zorder h2: setData update 의 combo-hierarchy z 평탄화(comboZ+1) 를 canonical 로 재-assert
    _metaGraphMinimapAnchor();   // graph-minimap-fix: 플러그인 컨테이너 inline left/top → CSS 앵커 정규화(멱등)
    if (fit) { await _metaGraphFitClamped(true); }
  } catch (err) { _metaGraphStatus("그래프 렌더 오류: " + ((err && err.message) || err)); }
}

// graph-minimap-fix(REQ ②): G6 v5 minimap 플러그인은 컨테이너 생성 시점의 캔버스 크기로 inline
//   left/top(px)을 **1회 계산해 고정**한다 — 상세 패널 드래그 리사이즈/접기/창 리사이즈로 캔버스가
//   변해도 미니맵이 옛 좌표에 남는 원인(styles.css 의 right/bottom 앵커는 inline left/top 에 진다).
//   inline 좌표를 auto 로 지워 CSS 앵커(right:10px; bottom:10px)로 전환하면 이후 모든 리사이즈를
//   레이아웃이 자동 추종한다. 멱등(재호출 무해) — 플러그인 캔버스가 lazy 생성되므로 rebuild 마다 보정.
//   §18.8 패널(MAJOR): 플러그인 컨테이너는 AFTER_DRAW 후 **128ms trailing debounce** 로 lazy 생성되므로
//   post-draw 즉시 호출은 요소를 못 찾는다 — 미발견 시 200ms 간격 재시도(기본 4회)로 생성 창을 커버.
function _metaGraphMinimapAnchor(retries) {
  let el = null;
  try { el = document.querySelector(".admin-meta-graph-canvas .g6-minimap"); } catch (_) { return; }
  if (el) {
    if (el.style.left !== "auto") { el.style.left = "auto"; el.style.top = "auto"; }
    return;
  }
  const r = (retries == null) ? 4 : retries;
  if (r > 0) setTimeout(() => _metaGraphMinimapAnchor(r - 1), 200);
}

// graph-minimap-reuse: G6 v5 minimap plugin.renderMinimap() 은 매 발동마다 전 요소 key-shape 를 cloneNode 로
//   전량 재복제한다(setShapes). 이 앱의 잦은 상태-only rebuild(_metaG6Apply) 로 인해 기하가 동일한데도 반복
//   재복제되는 것을 막기 위해, 플러그인 인스턴스의 renderMinimap 을 1회 래핑해 기하 서명 게이트를 건다.
//   - 팬/줌은 원래도 AFTER_TRANSFORM → updateMask()+setCamera() 만(재복제 없음)이라 본 패치와 무간섭.
//   - renderMask()(뷰포트 표시)는 onRender 에서 renderMinimap() 다음에 별도로 항상 호출되므로, 재복제를 skip 해도
//     미니맵 뷰포트 사각형은 계속 갱신된다.
//   - 실패(번들 API 변동·인스턴스 미발견)하면 조용히 no-op → 원본 renderMinimap 이 그대로 동작(정확성 보존, 최적화만 포기).
//   호출 시점: **첫 draw 이후**(G6 v5 는 context.plugin 을 첫 draw 의 initRuntime() 에서 lazy 생성 — init 시점 호출은
//   getPluginInstance 실패로 no-op). _metaG6ApplyOnce 의 `await g.draw()` 직후 매 apply 호출되나 멱등(__reusePatched)이라
//   첫 성공 래핑 1회만 유효(이후 즉시 return).
// graph-minimap-fullview(§77 — 시딩 kick 공용 헬퍼): 컬링-유예 build 1회를 350ms 지연 예약.
//   가드 2중: _miniSeedTimer(타이머 진행 중 중복 예약 방지)와 _miniSeedRun(이전 시도의 마킹 대기 — 해제는
//   래퍼의 전체 렌더 마킹 성공 시). 시딩 build 직후 다른 컬링 build 가 debounce 창에 끼어 마킹이 무산되면
//   _miniSeedRun 이 latch 로 남으므로, stale-skip 재-kick(force=true)만 latch 를 뚫고 재예약한다.
function _metaMinimapSeedKick(force) {
  if (_metaGraph._miniSeedTimer) return;
  if (_metaGraph._miniSeedRun && !force) return;
  _metaGraph._miniSeedRun = true;
  _metaGraph._miniSeedTimer = setTimeout(() => {
    _metaGraph._miniSeedTimer = null;
    try { _metaGraph._cullSuspendOnce = true; _metaG6Apply(false); }
    catch (_) { _metaGraph._miniSeedRun = false; _metaGraph._cullSuspendOnce = false; }
  }, 350);
}

function _metaPatchMinimapReuse(graph) {
  let mm = null;
  try { mm = graph.getPluginInstance && graph.getPluginInstance("minimap"); } catch (_) { mm = null; }
  if (!mm || typeof mm.renderMinimap !== "function" || mm.__reusePatched) return;
  const orig = mm.renderMinimap.bind(mm);
  mm.renderMinimap = function () {
    try {
      const sig = _metaGraph._miniGeomSig;
      // 캔버스가 이미 생성돼 있고(첫 렌더 완료) 기하 서명이 직전 렌더와 동일하면 '한 번 draw 한 전체 이미지' 재사용.
      if (sig != null && sig === mm.__lastGeomSig && mm.canvas) return;
      // graph-minimap-fullview(§77, 사용자 리포트 "줌인 컬링이 미니맵 구성까지 바꾼다"): 뷰포트 컬링으로 방출이
      //   부분집합인 build(_cullPartial)에서 재복제하면 미니맵(전역 개요)이 컬링된 구성으로 바뀐다 — 전체 이미지를
      //   보유 중이면 재복제 skip(마지막 무컬링 이미지 유지, __lastGeomSig 도 그 전체-build 서명으로 보존).
      //   보유 이미지의 '현재성' 은 __fullImageSig(그 이미지를 복제한 build 의 전체-기하 서명 _miniFullSig)로
      //   판정 — stale(줌인 중 펼침/필터 등 구조 변경)이어도 부분 재복제는 안 한다(컬링 구성 노출 금지).
      //   교체는 컬링-유예 시딩 build(_metaMinimapSeedKick)가 수행 — 시딩 직후 다른 컬링 build 가 debounce
      //   창(128ms)에 끼면 clone 이 부분 상태를 보게 돼 마킹이 무산될 수 있으므로, 본 stale-skip 분기(디바운스
      //   발화 = 상호작용 소강 신호)가 재-kick 해 소강 시점에 수렴시킨다. 전체 이미지가 아예 없으면
      //   (초기 draw 부터 컬링 — 드묾) 부분이라도 원본 렌더 폴백(빈 미니맵 방지, full 마킹 안 함).
      if (_metaGraph._cullPartial && mm.__fullImageSig != null && mm.canvas) {
        if (mm.__fullImageSig !== _metaGraph._miniFullSig) _metaMinimapSeedKick(true);   // latch 관통 재-kick
        return;
      }
      mm.__lastGeomSig = sig;
      if (!_metaGraph._cullPartial) { mm.__fullImageSig = _metaGraph._miniFullSig; _metaGraph._miniSeedRun = false; }
    } catch (_) { /* 서명 비교 실패 → 아래 원본 렌더로 안전 폴백 */ }
    return orig();
  };
  // graph-minimap-fullview(§77 — 카메라 유지): 미니맵 플러그인은 AFTER_TRANSFORM(팬/줌, 32ms 스로틀)마다
  //   setCamera() 로 미니맵 카메라를 **메인 캔버스의 현재 요소 bounds**(getBounds("elements"))에 재적합한다.
  //   뷰포트 컬링 중엔 이 bounds 가 방출 부분집합(≈뷰포트+마진)이라, 재복제를 skip 해 전체 이미지를 지켜도
  //   카메라가 그 부분 영역으로 줌인돼 전역 개요가 깨진다(두 번째 기전). 부분방출 상태 + 전체 이미지 보유면
  //   setCamera 재적합을 skip — 마지막 무컬링(전체 bounds) 카메라를 유지한다. updateMask 는 이 카메라 매핑으로
  //   현재 뷰포트를 사상하므로 마스크는 전체 이미지 위 올바른 위치에 계속 표시된다. 무컬링/이미지 미보유면 원본 동작.
  if (typeof mm.setCamera === "function") {
    const origCam = mm.setCamera.bind(mm);
    mm.setCamera = function () {
      try { if (_metaGraph._cullPartial && mm.__fullImageSig != null) return; } catch (_) { /* 안전 폴백 → 원본 */ }
      return origCam();
    };
  }
  // graph-minimap-reuse(적대 리뷰 H2 수정 — 네이티브 드래그 stale): 노드/콤보 드래그는 _metaG6Apply(setData+draw)를
  //   거치지 않고 G6 가 요소를 직접 이동(`translateElementTo`→`element.draw({stage:"translate"})`, 콤보는 native
  //   drag-element)한다. 이 draw 도 AFTER_DRAW 를 발생(payload `stage:"translate"`)시켜 minimap onRender→renderMinimap 을
  //   부르는데, 이때 _miniGeomSig 는 **마지막 build 기준(stale)** 이라 게이트가 옛 배치로 skip → 미니맵이 드래그된 위치를
  //   반영 못 하고 얼어붙는다. AFTER_DRAW 의 stage 가 "translate" 면 서명을 무효화(null)해 다음 renderMinimap 이 재복제
  //   폴백하도록 한다. apply-driven data draw 는 `graph.draw()`→`element.draw()`(stage 미지정)라 서명 유지(게이트 정상).
  //   이벤트 상수명 'afterdraw' 는 번들 GraphEvent.AFTER_DRAW 값(minimap 플러그인과 동일 바인딩). 멱등 블록 내 1회 바인딩.
  try {
    graph.on("afterdraw", (e) => {
      if (e && e.data && e.data.stage === "translate") _metaGraph._miniGeomSig = null;
    });
  } catch (_) { /* on 미지원 시 최적화만 포기(정확성 무관) */ }
  mm.__reusePatched = true;
}

// graph-initview(A1): 전체-fit 하되 판독 하한 밑으로는 줌아웃하지 않는다 — 콘텐츠가 크면 "판독 가능한
// 첫 페이지"를 보여주고 나머지는 팬/줌/미니맵으로 탐색. focusFirst 는 초기 로드/검색처럼 "시작점"이
// 자연스러운 경우만 true — 리사이즈/패널토글 refit 은 사용자의 현재 위치를 버리지 않게 false.
async function _metaGraphFitClamped(focusFirst) {
  const g = _metaGraph.graph;
  if (!g) return;
  try {
    await g.fitView({ padding: 30 }, false);
    const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
    if (isFinite(z) && z < _META_MIN_READ_ZOOM) {
      await g.zoomTo(_META_MIN_READ_ZOOM, false);
      if (focusFirst && _metaGraph.firstElementId) { try { await g.focusElement(_metaGraph.firstElementId, false); } catch (_) {} }
    } else if (isFinite(z) && z > 1) {
      await g.zoomTo(1, false);   // 소규모 콘텐츠(스키마 카드 몇 장)를 fit 이 과확대하지 않게 100% 상한
    }
  } catch (_) {}
}

// graph-dblclick-cam2: 더블클릭 앵커 focus 를 부드러운 팬으로. 그래프 config `animation:false`(레이아웃 셔플 방지용)가
//   **per-call 카메라 애니(focusElement/zoomTo 의 animation 인자)까지 무효화**한다(실증: false=2ms 즉시 vs true=412ms).
//   전역 animation 을 켜면 setData 레이아웃 셔플이 재발하므로, G6 애니 시스템 대신 **manual rAF tween** 으로 앵커를 뷰포트
//   중앙까지 translateBy(누적 이징) — setData 미사용이라 셔플·전역상태 무관. seq 로 연타 중단, 미렌더/ API 실패는 즉시 focus 폴백.
// graph-dblclick-latency: 앵커-중심 팬을 **적응형 follow tween** 으로. 고정-duration(Dx/Dy 1회 캡처) 대신 매 프레임
//   앵커의 **현재** 뷰포트 위치를 재조회해 뷰포트 중앙까지 잔여 delta 의 일정 비율(K)만큼 translateBy(ease-out).
//   이 구조라 (a) fetch·rebuild 완료를 기다리지 않고 **더블클릭 즉시 fire-and-forget 으로 시작**해도(앵커는 이미 렌더됨)
//   반응 텀이 사라지고, (b) 재빌드로 앵커가 이동/재생성돼도 최종 위치로 매끄럽게 수렴한다. seq 로 후속 op 시 폐기,
//   재빌드 중 element 일시 미해소는 해당 프레임만 skip(프레임카운트 조기포기 없음 — 저사양 rAF 탈동조 대비). 종료는 수렴/seq/MAXMS.
//   카메라 transform 만(노드 재렌더 없음)이라 프리즈 무관. API 부재 번들은 focusElement 즉시 폴백.
// opts.abort(선택): true 반환 시 팬 루프를 즉시 종료(detail-hover-fx — hover-pan 세대 토큰으로 이전 팬을
//   선점 종료. _opSeq 를 bump 하지 않아 진행 중 fetch 를 폐기하지 않으면서도 연속 hover 팬끼리 충돌하지 않게 함).
async function _metaGraphAnimateFocus(key, seq, opts) {
  const g = _metaGraph.graph;
  if (!g || !key) return;
  // graph-rel-layout(§18.8 패널 MINOR): tween 생존 마커 — expand 가 rebuild 후 "tween 이 이미 죽었는지"를
  //   판정해 시야 보정 폴백을 결정한다(관계 재배치로 앵커가 원거리 이동 가능해져 필요해짐). seq 소유 기준.
  _metaGraph._focusLive = seq == null ? -1 : seq;
  try {
    await _metaGraphAnimateFocusRun(g, key, seq, opts);
  } finally {
    if (_metaGraph._focusLive === (seq == null ? -1 : seq)) _metaGraph._focusLive = null;
  }
}
async function _metaGraphAnimateFocusRun(g, key, seq, opts) {
  const abort = (opts && typeof opts.abort === "function") ? opts.abort : null;
  // API 부재 번들 폴백(getElementRenderBounds/getViewportByCanvas/translateBy 없으면 즉시 focus — 구 동작 보존).
  if (typeof g.getElementRenderBounds !== "function" || typeof g.getViewportByCanvas !== "function" || typeof g.translateBy !== "function") {
    try { const fel = _metaRenderedIdFor(key); if (fel && typeof g.focusElement === "function") await g.focusElement(fel, false); } catch (_) {}
    return;
  }
  try {   // 판독 하한 줌 clamp(즉시 — 팬보다 먼저)
    const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
    if (isFinite(z) && z < _META_MIN_READ_ZOOM) await g.zoomTo(_META_MIN_READ_ZOOM, false);
  } catch (_) {}
  const now = () => (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  const raf = () => new Promise((r) => { (typeof window !== "undefined" && window.requestAnimationFrame) ? window.requestAnimationFrame(() => r()) : setTimeout(r, 16); });
  const t0 = now(), MAXMS = 1200;   // **유일** 시간 상한 — av 미해소(재빌드 프리즈로 rAF 탈동조)여도 여기서 확정 종료.
  const K = 0.24;                    // 프레임당 잔여 delta 비율(ease-out follow — 빠른 시작·부드러운 안착)
  while (true) {
    if (abort && abort()) return;                            // detail-hover-fx: 새 hover-pan/leave 로 선점 종료(세대 토큰)
    if (seq != null && seq !== _metaGraph._opSeq) return;   // 후속 op 로 폐기
    if (now() - t0 > MAXMS) return;                          // 시간 상한(유일 안전망 — 프레임 카운트 기반 조기 포기 없음)
    let W, H;   // 매 프레임 재조회 — 팬 중 컨테이너/창 리사이즈 대응(중앙 목표 스테일 방지).
    try { const s = g.getSize(); W = s[0]; H = s[1]; } catch (_) { W = H = NaN; }
    let av = null;   // 앵커 현재 뷰포트 위치 재조회 — 재빌드로 이동·재생성돼도 최종 위치로 수렴.
    try {
      const fel = _metaRenderedIdFor(key);
      if (fel) {
        const b = g.getElementRenderBounds(fel);
        av = g.getViewportByCanvas([(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2]);
      }
    } catch (_) { av = null; }
    if (isFinite(W) && isFinite(H) && av && isFinite(av[0]) && isFinite(av[1])) {
      const rx = W / 2 - av[0], ry = H / 2 - av[1];
      if (Math.abs(rx) < 1.2 && Math.abs(ry) < 1.2) return;   // 수렴 — 종료
      try { g.translateBy([rx * K, ry * K], false); } catch (_) { return; }
    }
    // av 미해소(재빌드 중 일시)면 이 프레임 skip — MAXMS 까지 재시도(조기 포기 없음 → 저사양 프레임드롭에도 팬 미실패).
    await raf();
  }
}

// ── detail-hover-fx: 우측 상세 패널 하위 항목 hover 시각 효과(비커밋 — 커밋 선택/전체 rebuild 미접촉) ──
//   요청(REQ): 상세 패널의 "관련된 객체 및 연결" 하위 항목에 마우스를 올리면 시각적 명확성을 준다.
//     · 카테고리/스키마 클러스터 행 → 해당 객체로 부드러운 카메라 이동
//     · 컬럼 행 → 컬럼 노드 하이라이트 / 참조·함수프로시저 행 → 연결선(엣지) 하이라이트
//   카메라 이동은 hover-intent 지연(스윕 중 요동 방지) + leave 시 취소. 클릭 팬(_metaGraphPanToRelation)과
//   동일하게 _opSeq 를 bump 하지 않는다(진행 중 fetch 를 폐기하지 않음). 하이라이트는 렌더러 오버레이
//   (setHoverHighlight)에 위임 — G6 폴백 어댑터엔 부재라 feature-detect 로 graceful no-op(카메라는 양쪽 동작).
let _metaHoverPanTimer = null;
let _metaHoverPanGen = 0;   // hover-pan 세대 — Cancel/새 Pan 이 bump → 진행 중 팬 루프를 선점 종료(연속 hover 충돌 방지, 적대리뷰 MAJOR).
function _metaGraphHoverPan(key, delay) {
  _metaGraphHoverPanCancel();   // 세대 bump(진행 중 팬 abort) + 대기 타이머 제거
  if (!key) return;
  const d = (delay == null) ? 200 : delay;   // hover-intent: 잠깐 머무를 때만 카메라 이동(행 위 빠른 통과는 무시)
  const gen = _metaHoverPanGen;   // 이 예약의 세대(취소 후 현재값 캡처)
  _metaHoverPanTimer = (typeof window !== "undefined" ? window.setTimeout : setTimeout)(() => {
    _metaHoverPanTimer = null;
    if (gen !== _metaHoverPanGen) return;   // 지연 중 새 hover/leave 로 대체됨 — 폐기
    const g = _metaGraph.graph; if (!g) return;
    const fel = _metaRenderedIdFor(key) || _metaRenderedAncestorFor(key);
    if (!fel) return;   // 화면 밖(미렌더 — 접힌 스키마/컬링) → graceful(클릭으로 펼침 유도, 카메라 요동 없음)
    // 기존 부드러운 적응형 팬 재사용(줌 유지, 팬만) + 세대 abort(이후 hover/leave 가 이 루프를 즉시 종료).
    _metaGraphAnimateFocus(fel, _metaGraph._opSeq, { abort: () => gen !== _metaHoverPanGen });
  }, d);
}
function _metaGraphHoverPanCancel() {
  _metaHoverPanGen++;   // 진행 중 hover-pan 루프(abort 체크) + 대기 타이머를 무효화
  if (_metaHoverPanTimer) { (typeof window !== "undefined" ? window.clearTimeout : clearTimeout)(_metaHoverPanTimer); _metaHoverPanTimer = null; }
}
// spec: { nodeKeys?: [key], edgeKeyPairs?: [[keyA,keyB]] }. key→렌더 요소 id 해소(미렌더면 조상=소속 테이블/카드로 승격).
//   엣지는 양끝 렌더 요소 사이 연결선으로 강조하고 양끝 노드도 함께 링 강조(연결이 명확히 보이게).
function _metaGraphSetHoverHighlight(spec) {
  const g = _metaGraph.graph;
  if (!g || typeof g.setHoverHighlight !== "function") return;   // G6 폴백 등 미지원 렌더러 → no-op
  const resolve = (k) => (k ? (_metaRenderedIdFor(k) || _metaRenderedAncestorFor(k)) : null);
  const nodeIds = [];
  const addNode = (id) => { if (id && nodeIds.indexOf(id) < 0) nodeIds.push(id); };
  ((spec && spec.nodeKeys) || []).forEach((k) => addNode(resolve(k)));
  const edges = [];
  ((spec && spec.edgeKeyPairs) || []).forEach((pair) => {
    const a = resolve(pair && pair[0]), b = resolve(pair && pair[1]);
    if (a && b && a !== b) { edges.push([a, b]); addNode(a); addNode(b); }
    else if (a) { addNode(a); }   // 상대 미렌더 — self 끝점만이라도 강조(연결선은 생략)
    else if (b) { addNode(b); }   // self 미렌더(컬링)·상대 렌더 — 상대 끝점만이라도 강조(적대리뷰 MINOR#4)
  });
  if (!nodeIds.length && !edges.length) { if (typeof g.clearHoverHighlight === "function") { try { g.clearHoverHighlight(); } catch (_) {} } return; }
  try { g.setHoverHighlight({ nodes: nodeIds, edges }); } catch (_) {}
}
function _metaGraphClearHoverHighlight() {
  const g = _metaGraph.graph;
  if (g && typeof g.clearHoverHighlight === "function") { try { g.clearHoverHighlight(); } catch (_) {} }
}

// 라벨별 색 — RFC 팔레트(Table=teal, Column=slate, GlossaryTerm=amber, Schema=indigo, DS/Product=green).
const _META_GRAPH_COLOR = {
  Table: "#0f7d8c", Column: "#5c6773", GlossaryTerm: "#9c6515",
  Schema: "#3f4b8c", Datasource: "#2e7d52", Product: "#2e7d52",
  Routine: "#7b5cd6",   // graph-funcproc(ADR-016): 함수·프로시저 칩(보라 — 테이블 teal 과 구분)
};
// graphux5-progress: 라벨 한글 표기(AI 능동 분석 진행 상세 — 어떤 '항목'인지 사람이 읽게).
const _META_LABEL_KO = {
  Table: "테이블", Column: "컬럼", GlossaryTerm: "용어", Schema: "스키마",
  Datasource: "데이터소스", Product: "제품", Routine: "함수·프로시저",
};
// graph-funcproc: 함수(ƒ)/프로시저(⚙) 표기 접두 — 칩 라벨·상세 헤더 공용.
function _metaRoutineIcon(rt) { return rt === "function" ? "ƒ" : "⚙"; }
function _metaRoutineKo(rt) { return rt === "function" ? "함수" : "프로시저"; }
// graph-navfilter(§54⑤): routine params 문자열("IN a int, OUT b varchar" — routines.py 가 ", " join,
//   piece 는 DATA_TYPE 이라 내부 콤마 없음) → 파라미터 목록. 그래프 수직 배치·상세 패널 공용.
function _metaRoutineParamList(n) {
  const s = (n && n.params) || "";
  return s ? s.split(", ").map((x) => x.trim()).filter(Boolean) : [];
}

function _metaGraphStatus(msg) {
  const el = document.getElementById("metadataGraphStatus");
  if (!el) return;
  el.textContent = msg || "";
  // graph-toolbar-consolidate: 상태가 캔버스 좌상단 오버레이 pill 로 이동(레이아웃 흐름 밖 → reflow 0).
  //   새 메시지는 즉시 표시하고 6s 뒤 유휴(is-idle=투명)로 흐려 캔버스 가림을 최소화한다.
  //   표시/유휴 어느 상태든 position:absolute 라 캔버스·툴바 높이는 절대 변하지 않는다.
  el.classList.remove("is-idle");
  if (_metaGraph._statusTimer) { clearTimeout(_metaGraph._statusTimer); _metaGraph._statusTimer = null; }
  if (msg) {
    _metaGraph._statusTimer = setTimeout(() => {
      _metaGraph._statusTimer = null;
      const e2 = document.getElementById("metadataGraphStatus");
      if (e2) e2.classList.add("is-idle");
    }, 6000);
  }
}

// graph-toolbar-consolidate: '보기 옵션' 버튼 배지 동기화 — 팝오버로 숨겨진 종류 필터 상태(예: 관계·함수 숨김)를
//   상단에서 인지할 수 있게 숨긴 종류 개수를 배지로 표시(0 이면 숨김). 필터가 안 보여도 '무엇을 숨겼는지' 드러남.
function _metaGraphSyncViewOptsBadge() {
  const badge = document.getElementById("metaGraphViewOptsBadge");
  if (!badge) return;
  const n = (_metaGraph.hiddenKinds && _metaGraph.hiddenKinds.size) || 0;
  if (n > 0) { badge.textContent = String(n); badge.hidden = false; }
  else { badge.textContent = ""; badge.hidden = true; }
}

function _metaShowGraph() {
  // feature-0016 §45: 그래프 뷰는 자체 pane(data-admin-pane="graph") 이라 메타데이터 pane DOM 을 숨길 필요가 없다
  //   (pane display 가 가시성을 관장). 여기선 그래프 init + 진입 로드만 수행한다.
  _metaInitGraph();
  _metaRoleLegendTips();   // role-cluster-prefix: 역할 범례 hover 툴팁(desc) 주입(정적 <li data-role> → _META_ROLE 단일 소스).
  _metaGraphBindLegendTabs();   // graphux7(#3): 범례 3-탭 전환 바인딩(멱등).
  // feature-0016: 그래프 뷰 진입 시 현재 선택 datasource 의 그래프(roots)를 즉시 로드 — 각 데이터소스별 그래프 출현.
  _metaGraphLoadRoots();
  const s = document.getElementById("metadataGraphSearch");
  if (s && s.focus) try { s.focus(); } catch (_) {}
}

// 모델 초기화(그래프 교체/리셋/scope 전환 시). 노드·엣지·펼침·마커 clear.
function _metaGraphResetModel() {
  _metaGraph.nodes.clear();
  _metaGraph.edges.clear();
  _metaGraph.expanded.clear();
  _metaGraph.analyzed.clear();
  _metaGraph.running.clear();
  _metaGraph.roles.clear();   // node-role-viz: 역할 표식도 모델과 함께 초기화(sync 가 재적재)
  _metaGraph.selected = null;
  _metaGraph.focusAdj = null;   // §57: 상대 하이라이트 집합도 모델과 함께 초기화.
  _metaGraph._lodBand = null;   // §57 패널 NIT: LOD 밴드 기준선도 초기화(스코프 전환 스퓨리어스 rebuild 방지).
  _metaGraph._colLodActive = false;   // col-lod(§61): 스코프/뷰 전환 시 억제 플래그 초기화(상태줄 stale 마커 방지).
  _metaGraph._aggActive = false;      // agg-lod(§63): 스코프/뷰 전환 시 집계 플래그 초기화.
  _metaGraph._cullActive = false; _metaGraph._cullVp = null; _metaGraph._cullPartial = false; _metaGraph._miniSeedRun = false; _metaGraph._cullSuspendOnce = false; _metaGraph._miniFullSig = null; if (_metaGraph._miniSeedTimer) { try { clearTimeout(_metaGraph._miniSeedTimer); } catch (_) {} _metaGraph._miniSeedTimer = null; }   // viewport-cull(§65)+§77: 스코프/뷰 전환 시 초기화(시딩 가드·전체서명·타이머 포함).
  if (_metaGraph._cullRaf) { try { (typeof window !== "undefined" && window.cancelAnimationFrame ? window.cancelAnimationFrame : clearTimeout)(_metaGraph._cullRaf); } catch (_) {} _metaGraph._cullRaf = null; }   // §76 실시간 컬링 rAF 정리(스코프 전환 stale 방지)
  _metaGraph.colsByTable.clear();   // graph-perf-bg: 펼침 인덱스 초기화(모델 교체와 정합).
  _metaGraph._stateCache.clear();   // graph-perf-bg: state 캐시 무효화(다음 refresh 가 전량 재적용).
  _metaGraph._busyKeys.clear();     // graph-perf-bg fix: 모델 교체 → 명령형 busy 정리.
  if (_metaGraph._busyTs) _metaGraph._busyTs.clear();   // §57.8: TTL 타임스탬프도 동반 정리
  // graph-perf-bg fix(BLOCKING): 모델 교체(search/roots/scope/reset)는 in-flight 펼침·확장을 무효화한다. _opSeq 를 여기서
  //   올리지 않으면 heavy op 만 토큰을 올려, reset 후 뒤늦게 resolve 된 stale expand 가 (a) 새 모델을 덮어써 사용자가
  //   방금 요청한 검색/스코프 화면을 되돌리고(stale 렌더), (b) reset 으로 비워진 모델에 컬럼을 ingest 해 colsByTable 를
  //   포이즌(존재하지 않는 테이블의 hasCols=true → 재펼침 영구 차단)한다. 토큰을 올리면 그 op 는 다음 seq 체크에서 폐기된다.
  _metaGraph._opSeq++;
  // graph-initview: 검색 필터 뷰 상태 초기화(schemaTotals 는 scope 캐시라 보존 — loadRoots 가 재구축).
  _metaGraph.searchMatch = null;
  _metaGraph.searchMatchTables = null;
  _metaGraph.searchMatchNodes = null;   // feature-0016 §45: 검색 매칭 glow 집합 초기화.
  _metaGraph.searchCapped = false;
  _metaGraph.searchAdded.clear();       // graph-navfilter(§54③): 검색 pristine 추적도 스코프와 함께 리셋.
  _metaGraph.routineExpanded.clear();   // graph-navfilter(§54⑤): 루틴 파라미터 펼침 리셋(컬럼 펼침과 동형).
  // (주의) hiddenKinds 는 여기서 clear 하지 않는다 — scope-독립 표시 preference(§54②). 검색·중심보기가
  //   resetModel 을 경유하므로 clear 하면 검색 한 번에 필터가 풀리는 회귀가 된다.
  // graph-initview: 스키마-우선 상태 초기화.
  _metaGraph.schemaExpanded.clear();
  _metaGraph.schemaLoaded.clear();
  _metaGraph.schemaLoading.clear();
  _metaGraph.schemaTruncated.clear();
  _metaGraph.firstElementId = null;
  if (_metaGraph.introspected) _metaGraph.introspected.clear();
  // graph-freeplace: 자유 배치는 스코프 전환·초기화 시 리셋(다른 데이터소스는 다른 클러스터 — 위치 무의미).
  //   펼침/접기(rebuild)는 resetModel 을 거치지 않으므로 그 경로에선 위치가 유지된다(핵심 요구).
  _metaGraph.clusterOffset.clear();
  _metaGraph.nodePos.clear();
  _metaGraph.groupOffset.clear();      // group-interact(§50): sim-group 자유 배치·접기도 fresh load 시 리셋(다른 스코프 = 다른 그룹).
  _metaGraph.groupCollapsed.clear();
  _metaGraph.groupMembers.clear();
  _metaGraph.groupOf.clear();
  _metaGraph.clusterOrder = [];        // feature-0016 §49: 순서 안정화도 fresh load(스코프 전환·초기화) 시 리셋 → 순수 seriation.
  _metaGraph.tableOrder.clear();
  _metaGraph.groupOrder.clear();       // feature-0016 §49(R1): simgroups 순서 안정화도 fresh load 시 리셋.
  _metaGraph.groupTableOrder.clear();
  // graph-layoutmemo(§73, 적대리뷰 하드닝): 배치-정렬 캐시도 fresh load 시 명시 리셋. 실제로는 schemaExpanded.clear()
  //   가 다음 build 서명을 바꿔 무효화되나, 그 결합에 의존하지 않도록 직접 클리어(견고성).
  _metaGraph._layoutSig = undefined; _metaGraph._relOrderCache = null; _metaGraph._simCache = new Map();
  // graph-category(§55 A): 카테고리 순서·접기·인덱스 리셋(다른 스코프 = 다른 카테고리).
  //   schemaProducts 는 schemaTotals 동형의 scope 캐시라 보존 — loadRoots 가 재구축.
  _metaGraph.catOrder = [];
  _metaGraph.catCollapsed.clear();
  _metaGraph.catMembers.clear();
  _metaGraph.catLabelOf.clear();
  _metaGraph._comboDragStart = null;
}

// graph-product-cat(§43): 제품 카테고리 개요 로드 — Product→Datasource 개요(MySQL SSOT 합성).
//   scope='product:<id>' 면 단일 제품 focus, 그 외(common/__products__)는 전체 제품. 데이터소스 노드 클릭으로 drill.
async function _metaGraphLoadProducts(scope) {
  if (!_metaGraph.graph) _metaInitGraph();
  if (!_metaGraph.graph) return;
  _metaGraphHistoryReset();   // graphux7(#1): datasource/제품 컨텍스트 전환 — 방문 이력 초기화.
  _metaGraph._searchBase = null;   // §54③: fresh 컨텍스트 — 검색 base 폐기
  // §54② 패널 MINOR: kind 필터는 스키마 그래프 전용 — 제품 개요(BuildProducts 는 hiddenKinds 미참조)
  //   에서 버튼이 동작하는 척(허위 status)하지 않게 컨트롤 자체를 숨긴다.
  const _kc0 = document.querySelector(".admin-meta-graph-kindctl");
  if (_kc0) _kc0.style.display = "none";
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";
  _metaGraph.lastQuery = "";
  _metaGraph.mode = "products";                 // resetModel 은 mode 를 건드리지 않음(loadRoots 와 동형 순서)
  _metaGraph.loadedScope = scope || "common";   // feature-0016 §45 D1: 제품 개요도 마지막 렌더 스코프 기록.
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);
  _metaGraphResetModel();
  _metaGraph.mode = "products";                 // resetModel 이후 재확정(방어)
  const seq = _metaGraph._opSeq;
  _metaGraphFillJump([]);
  const s = String(scope || "");
  const pid = s.startsWith("product:") ? s.slice("product:".length) : "";
  const url = pid
    ? `/api/admin/metadata/graph?product=${encodeURIComponent(pid)}`
    : `/api/admin/metadata/graph?mode=products`;
  _metaGraphStatus("제품 카테고리 로딩…");
  let data;
  try { data = await apiFetch(url); }
  catch (err) { if (seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "제품 그래프 로드 실패"); return; }
  if (seq !== _metaGraph._opSeq) return;
  _metaGraphIngest(data.nodes || [], data.edges || []);
  await _metaG6Apply(true);
  if (seq !== _metaGraph._opSeq) return;
  const np = (data.nodes || []).filter((n) => n && n.label === "Product").length;
  const nd = (data.nodes || []).filter((n) => n && n.label === "Datasource").length;
  _metaGraphRenderDetailEmpty();
  _metaGraphStatus(np
    ? `제품 카테고리 ${np}개 · 데이터소스 ${nd}개 — 데이터소스 노드를 클릭하면 그 데이터소스의 스키마 그래프로 이동합니다.`
    : "등록된 제품이 없습니다. (관리 콘솔 > 제품 에서 등록 후 데이터소스를 바인딩하세요.)");
}

// 현재 선택 datasource(scope)의 진입 그래프(Schema→Table)를 로드. 'common'/미선택/제품 scope 는 제품 카테고리 개요.
async function _metaGraphLoadRoots() {
  if (!_metaGraph.graph) _metaInitGraph();
  if (!_metaGraph.graph) return;
  _metaGraphHistoryReset();   // graphux7(#1): datasource 컨텍스트 전환 — 방문 이력 초기화.
  const scope = adminState.metadata.scopeKey || "common";
  _metaGraph.loadedScope = scope;   // feature-0016 §45 D1: 마지막 렌더 스코프 기록(탭 재진입 시 diverge 재로드 판정).
  // graph-product-cat(§43): 데이터소스 미선택(공용) 또는 제품 scope 는 제품 카테고리 개요를 랜딩으로 보여준다.
  if (!scope || scope === "common" || scope === "__products__" || String(scope).startsWith("product:")) {
    return _metaGraphLoadProducts(scope);
  }
  _metaGraph._searchBase = null;   // §54③: fresh 컨텍스트 — 검색 base 폐기
  const _kc1 = document.querySelector(".admin-meta-graph-kindctl");
  if (_kc1) _kc1.style.display = "";   // §54②: 스키마 그래프 — kind 필터 컨트롤 표시
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";
  _metaGraph.lastQuery = "";   // 검색 컨텍스트 종료 — 상세 유사도 배지 게이트가 참조
  _metaGraph.mode = "roots";
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);   // 중심 보기 종료(전체 복귀)
  _metaGraphResetModel();
  const seq = _metaGraph._opSeq;   // graph-perf-bg fix: resetModel 직후 세대 캡처 — await 도중 다른 reset(loadRoots/search/scope 전환) 이 _opSeq 를 올리면 이 continuation 을 폐기.
  _metaGraphStatus("데이터소스 그래프 로딩…");
  let data;
  try {
    // graph-initview: 진입은 스키마 카드 경량 뷰(mode=schemas) — 테이블은 스키마 클릭 시 per-schema lazy.
    // (구 백엔드가 mode 를 모르면 scope_roots 전체 응답이 와도 카드 게이팅으로 동일 UX — 하위호환.)
    data = await apiFetch(`/api/admin/metadata/graph?scope=${encodeURIComponent(scope)}&mode=schemas`);
  } catch (err) {
    if (seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "그래프 로드 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) return;   // graph-perf-bg fix: await 사이 다른 reset 이 모델을 교체 → 이 응답은 stale. additive ingest 하면 혼합-스코프 그래프가 남으므로 폐기.
  _metaGraphIngest(data.nodes || [], data.edges || []);
  const schemaKeys = [];
  _metaGraph.nodes.forEach((sn) => { if (sn.label === "Schema") schemaKeys.push(sn.key); });
  schemaKeys.sort(_metaNatSort);
  // graph-initview: scope 별 스키마→전체 테이블 수 캐시(재구축). 검색이 모델을 리셋해도 카드 badge 의
  //   '전체 테이블 개수' 소스로 쓰이므로 여기서만 갱신하고 resetModel 에서는 보존한다.
  _metaGraph.schemaTotals = new Map();
  _metaGraph.nodes.forEach((sn) => { if (sn.label === "Schema" && typeof sn.table_count === "number") _metaGraph.schemaTotals.set(sn.key, sn.table_count); });
  // graph-category(§55 A): 스키마(DB)명 → 제품 매핑 재구축(scope 캐시 — schemaTotals 동형).
  //   key 는 lowercase(WebProductDatabases.SchemaName 과 그래프 스키마명의 대소문자 편차 방어).
  _metaGraph.schemaProducts = new Map();
  if (data.schema_products && typeof data.schema_products === "object") {
    Object.keys(data.schema_products).forEach((sch) => {
      const lst = data.schema_products[sch];
      if (Array.isArray(lst) && lst.length) _metaGraph.schemaProducts.set(String(sch).toLowerCase(), lst);
    });
  }
  _metaGraphFillJump(schemaKeys);
  let truncNote = data.truncated ? " · 스키마 표시 상한 도달(나머지는 검색)" : "";
  // 스키마 1개짜리 데이터소스는 카드 한 장이 무의미 — 즉시 펼쳐 기존 즉시성 유지(silent, 부모 seq 상속).
  if (schemaKeys.length === 1) {
    await _metaGraphExpandSchema(schemaKeys[0], { silent: true, seq });
    if (seq !== _metaGraph._opSeq) return;
    if (_metaGraph.schemaTruncated.has(schemaKeys[0])) truncNote += " · 테이블 표시 상한 도달(나머지는 검색)";
  }
  await _metaG6Apply(true);
  if (seq !== _metaGraph._opSeq) return;
  _metaGraphSyncAnalysisMarkers(scope);   // 이미 분석된/진행중 노드 마커를 클릭 없이 렌더 시점에 적용
  const n = (data.nodes || []).length;
  // graph-product-cat(§43): 이 데이터소스를 쓰는 제품(카테고리) 배너 — 어느 제품 소속인지 즉시 식별.
  const prodNames = Array.isArray(data.products) ? data.products.map((p) => p && p.name).filter(Boolean) : [];
  const prodPrefix = prodNames.length ? `제품: ${prodNames.join(", ")} · ` : "";
  _metaGraphStatus(n
    ? (schemaKeys.length > 1
        ? `${prodPrefix}${scope}: 스키마 ${schemaKeys.length}개 — 카드를 클릭하면 그 스키마의 테이블을 펼칩니다. 검색으로 바로 탐색도 가능.${truncNote}`
        : `${prodPrefix}${scope}: ${_metaGraph.nodes.size}개 노드 — 노드 클릭으로 확장, 또는 검색.${truncNote}`)
    : `${prodPrefix}${scope}: 그래프 데이터 없음(설명/인사이트 미적재).`);
}

// graph-initview(E3): 툴바 스키마 점프 select 채움 — 선택 시 해당 클러스터/카드로 focus.
function _metaGraphFillJump(schemaKeys) {
  const sel = document.getElementById("metadataGraphJump");
  if (!sel) return;
  const escA = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  const opts = ['<option value="">스키마 이동…</option>'];
  (schemaKeys || []).forEach((k) => { opts.push(`<option value="${escA(k)}">${escA(_metaComboName(k))}</option>`); });
  sel.innerHTML = opts.join("");
  sel.style.display = (schemaKeys && schemaKeys.length > 1) ? "" : "none";
}

// 노드 key(`scope:fqn`)에서 카테고리(스키마) compound parent id 도출. schema 없으면 null.
function _metaCatParent(key, fqn) {
  if (!key) return null;
  const idx = key.indexOf(":");
  if (idx < 0) return null;
  const scope = key.slice(0, idx);
  const f = fqn || key.slice(idx + 1);
  if (!f || f.indexOf(".") < 0) return null;   // 스키마 segment 없음(스키마 노드 자체 등)
  return scope + ":" + f.split(".")[0];
}

// graph-drag: 이벤트의 눌린 버튼 비트마스크(buttons)를 견고하게 추출한다.
//   G6/G 의 drag lifecycle 이벤트(node:dragstart, 전역 dragstart)는 pointermove 에서 합성돼
//   `button` 이 -1 일 수 있으므로, 현재 눌림 상태를 나타내는 `buttons`(1=좌,2=우,4=중간)를 우선한다.
//   nativeEvent fallback + button→bitmask 최종 폴백으로 번들 차이에도 안전.
function _metaEventButtons(e) {
  if (!e) return 1;
  if (typeof e.buttons === "number" && e.buttons > 0) return e.buttons;
  const ne = e.nativeEvent || e.originalEvent;
  if (ne && typeof ne.buttons === "number" && ne.buttons > 0) return ne.buttons;
  const b = (typeof e.button === "number") ? e.button
    : (ne && typeof ne.button === "number") ? ne.button : 0;
  return b === 1 ? 4 : b === 2 ? 2 : 1;   // button: 0=좌→1, 1=중간→4, 2=우→2
}
// graph-drag: 중간(휠) 버튼으로 시작한 드래그인지.
function _metaIsMiddleDrag(e) { return (_metaEventButtons(e) & 4) === 4; }
// graph-drag(REQ ①): drag-canvas 활성 판정 — 중간 버튼은 노드 위에서든 어디서든 카메라 팬으로 허용,
//   그 외(좌클릭)는 G6 기본대로 빈 캔버스에서만 팬(노드는 drag-element 가 처리).
function _metaCanvasDragEnable(e) {
  if (_metaIsMiddleDrag(e)) return true;
  return !(e && "targetType" in e) || (e && e.targetType === "canvas");
}
// graph-drag(REQ ①): drag-element 활성 판정 — 노드 이동은 좌클릭만. 중간 버튼은 카메라 팬에
//   양보해 "객체 상호작용(노드 이동)"이 아니라 카메라 드래그가 되게 한다.
function _metaElementDragEnable(e) {
  const id = e && e.target && e.target.id;
  // group-interact(§50): 그룹 접기 컨트롤(GX)만 이동 불가(클릭 전용). GB(배경)/GH(헤더)는 그룹 리지드 드래그 허용
  //   (예전 graph-simgroups 의 GB/GH 이동 차단을 해제 — 카테고리 그룹 drag&drop 위치 이동 복원).
  if (id && String(id).startsWith("GX:")) return false;
  if (id && String(id).startsWith("CATX:")) return false;   // graph-category(§55 A): 카테고리 접기 ctl = 클릭 전용
  // graph-category(§55 A, 패널 MAJOR fix): **접힌** 카테고리 밴드는 드래그 불가 — 밴드 위치가 packing
  //   (bandY) 파생이라 rebuild 로 스냅백하는데, 숨겨진 멤버 클러스터에는 clusterOffset 델타가 조용히
  //   누적돼 펼쳤을 때 멤버만 이동해 있는 모순이 생긴다(클릭 전용 = 상세/펼침 유도).
  if (id && (String(id).startsWith("CATH:") || String(id).startsWith("CAT:"))) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    if (_metaGraph.catCollapsed.has(ck)) return false;
  }
  return !_metaIsMiddleDrag(e);
}

// graph-drag(REQ ②): 테이블 노드 드래그 시 종속 UI(접기 "X:" ctl + 컬럼 노드) 동반 이동.
//   dragstart 에서 각 종속의 테이블 대비 오프셋(월드좌표)을 고정 기록하고, drag/dragend 마다
//   종속을 "테이블 현재위치 + 오프셋" 으로 절대 이동(translateElementTo)한다.
//   절대-오프셋 방식은 이벤트 실행 순서(내 핸들러 vs drag-element)에 무관하다: dragend 시점엔
//   drag-element 가 이미 테이블을 최종 위치로 옮겨 놓았으므로 재정합으로 1-frame lag 이 제거된다.
// graph-freeplace: 클러스터 offset 누적(combo 드래그 · 접힌 카드 드래그 공용). curId 의 현재 위치와
//   기록된 시작 위치의 델타를 clusterOffset[comboId] 에 누적한다(반복 드래그 정합, 미동 무시).
function _metaClusterOffsetAccumulate(comboId, startX, startY, curId) {
  const g = _metaGraph.graph;
  if (!g || !comboId) return;
  let p; try { p = g.getElementPosition(curId); } catch (_) { return; }
  if (!p || !isFinite(p[0]) || !isFinite(p[1])) return;
  const dx = p[0] - startX, dy = p[1] - startY;
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
  const prev = _metaGraph.clusterOffset.get(comboId) || { dx: 0, dy: 0 };
  _metaGraph.clusterOffset.set(comboId, { dx: prev.dx + dx, dy: prev.dy + dy });
  // graph-freeplace(리뷰 MAJOR fix): 클러스터를 통째로 옮기면, 그 클러스터에 속한 **개별 배치된 노드
  //   (nodePos, 절대좌표)** 도 같은 델타로 함께 옮긴다. 안 그러면 nodePos 가 절대값이라 clusterOffset 를
  //   덮어써(build 최종 tx=fp[0]) 그 노드만 원위치에 남아 클러스터에서 분리된다(table-then-cluster 순서).
  _metaGraph.nodePos.forEach((pos, nid) => {
    const n = _metaGraph.nodes.get(nid);
    if (n && _metaSchemaComboOf(n) === comboId) { pos[0] += dx; pos[1] += dy; }
  });
}

function _metaNodeDragStart(e) {
  _metaGraph._drag = null;
  _metaGraph._comboDragStart = null;
  if (_metaIsMiddleDrag(e)) return;             // 중간 버튼은 카메라 팬 — 노드 이동 아님
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  if (!g || !id) return;
  // graph-freeplace: 접힌 스키마 카드("SC:") 드래그 = 클러스터 위치 이동(combo 드래그와 동일 clusterOffset).
  //   L.x0/L.y0 는 카드·펼친 combo 공용 기준이라, 카드에서 옮겨도 펼쳤을 때 같은 offset 이 유지된다.
  if (String(id).startsWith("SC:")) {
    try { const p = g.getElementPosition(id); if (p) _metaGraph._comboDragStart = { comboId: id.slice(3), curId: id, x: p[0], y: p[1] }; } catch (_) {}
    _metaDragZBoost([id]);   // graph-zorder(§52): 내장 frontElement(영구 max+1) 대신 결정론 부스트 — dragend 복원
    return;
  }
  // graph-category(§55 A): 제품 카테고리 밴드(CAT: 배경 여백 / CATH: 헤더 칩) 드래그 = 카테고리 통째
  //   리지드 이동 — 멤버 클러스터(펼친 combo 는 자식 전체, 접힌 카드는 SC:) + 밴드 장식을 고정 오프셋으로
  //   묶는다(그룹 리지드 기전 재사용). dragend 에 멤버별 clusterOffset 일괄 누적(신규 offset 계층 불요).
  if (String(id).startsWith("CATH:") || String(id).startsWith("CAT:")) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    let ap; try { ap = g.getElementPosition(id); } catch (_) { return; }
    if (!ap) return;
    const rendered = _metaGraph.renderedIds;
    const clusters = _metaGraph.catMembers.get(ck) || [];
    const ids = ["CAT:" + ck, "CATH:" + ck, "CATX:" + ck];
    clusters.forEach((cid) => {
      ids.push(cid, "SC:" + cid);   // 펼친 combo / 접힌 카드 — rendered 필터가 실재만 남긴다
      _metaComboMemberIds(cid).forEach((mid) => ids.push(mid));
    });
    const offs = [];
    const seenOff = new Set();
    ids.forEach((eid) => {
      if (eid === id || seenOff.has(eid)) return;
      seenOff.add(eid);
      if (rendered && !rendered.has(eid)) return;
      let dp; try { dp = g.getElementPosition(eid); } catch (_) { return; }
      if (dp) offs.push({ id: eid, ox: dp[0] - ap[0], oy: dp[1] - ap[1] });
    });
    _metaGraph._drag = { id, offs, cat: ck, catClusters: clusters.slice(), startX: ap[0], startY: ap[1] };
    _metaDragZBoost([id].concat(offs.map((o) => o.id)));
    return;
  }
  // group-interact(§50): sim-group(GB 배경/GH 헤더) 드래그 = 카테고리 그룹 통째 리지드 이동.
  //   grabbed 요소를 anchor 로, 그룹 박스·헤더·컨트롤 + 멤버 테이블 + 그 종속(컬럼·"X:")을 고정 오프셋으로
  //   묶어 _drag.offs 에 담는다(테이블 종속 드래그와 동일 기전 재사용). dragend 에 groupOffset 누적.
  if (String(id).startsWith("GB:") || String(id).startsWith("GH:")) {
    const gk = String(id).slice(3);
    let ap; try { ap = g.getElementPosition(id); } catch (_) { return; }
    if (!ap) return;
    const rendered = _metaGraph.renderedIds;
    const ids = ["GB:" + gk, "GH:" + gk, "GX:" + gk];
    const members = _metaGraph.groupMembers.get(gk);
    if (members) members.forEach((tk) => {
      ids.push(tk);
      const deps = _metaGraph.tableDeps.get(tk);
      if (deps) deps.forEach((d) => ids.push(d));
    });
    const offs = [];
    ids.forEach((eid) => {
      if (eid === id) return;                        // grabbed 자신은 anchor(offs 제외)
      if (rendered && !rendered.has(eid)) return;
      let dp; try { dp = g.getElementPosition(eid); } catch (_) { return; }
      if (dp) offs.push({ id: eid, ox: dp[0] - ap[0], oy: dp[1] - ap[1] });
    });
    _metaGraph._drag = { id, offs, group: gk, startX: ap[0], startY: ap[1] };
    // graph-zorder(§52): 그룹 묶음(박스·헤더·컨트롤·멤버·종속) 전체를 함께 부스트 — grabbed 만 오르며
    //   계층이 찢어지던 내장 frontElement 를 덮는다(호출이 늦어 우선). dragend 에 canonical 복원.
    _metaDragZBoost([id].concat(offs.map((o) => o.id)));
    return;
  }
  const deps = _metaGraph.tableDeps.get(id);    // 테이블 key 만 등록됨(ctl/컬럼/용어/카드는 단독 이동)
  if (!deps || !deps.length) { _metaDragZBoost([id]); return; }   // graph-zorder(§52): 종속 없는 단독 노드도 부스트+복원 대칭
  let tp;
  try { tp = g.getElementPosition(id); } catch (_) { return; }
  if (!tp) return;
  const rendered = _metaGraph.renderedIds;       // 렌더된 종속 노드만(접힘 등 미렌더 제외)
  const offs = [];
  deps.forEach((d) => {
    if (rendered && !rendered.has(d)) return;
    let dp;
    try { dp = g.getElementPosition(d); } catch (_) { return; }
    if (dp) offs.push({ id: d, ox: dp[0] - tp[0], oy: dp[1] - tp[1] });
  });
  if (!offs.length) { _metaDragZBoost([id]); return; }
  _metaGraph._drag = { id, offs };
  // graph-zorder(§52): 테이블+종속(컬럼·"X:" ctl)을 함께 부스트 — 드래그 중 칩만 최상층으로 떠서
  //   자기 컬럼과 계층이 찢어지던 내장 frontElement 단독 승격을 결정론 부스트로 대체(dragend 복원).
  _metaDragZBoost([id].concat(offs.map((o) => o.id)));
}
// drag: 종속을 "테이블 현재위치 + 고정 오프셋" 으로 절대 이동(누적 drift·zoom 수학 비의존).
function _metaNodeDrag() {
  const st = _metaGraph._drag;
  const g = _metaGraph.graph;
  if (!st || !g) return;
  let tp;
  try { tp = g.getElementPosition(st.id); } catch (_) { return; }
  if (!tp) return;
  const to = {};
  st.offs.forEach((o) => { to[o.id] = [tp[0] + o.ox, tp[1] + o.oy]; });
  try { g.translateElementTo(to, false); } catch (_) {}
}
// dragend: 최종 위치 재정합(내 핸들러가 drag-element 보다 먼저 실행돼도 마지막 프레임 lag 제거) + 상태 해제.
function _metaNodeDragEnd(e) {
  _metaNodeDrag();
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  // graph-zorder(§52): 드래그 임시 부스트(+내장 frontElement 잔존) canonical 복원 — 이후 분기(그룹
  //   커밋·nodePos 기록·rebuild)와 직교. 드래그 이력이 z-order 로 굳지 않는 것이 본 cycle 의 핵심 불변식.
  {
    const dz = _metaGraph._drag;
    const rids = [];
    if (id) rids.push(id);
    if (dz && dz.id && dz.id !== id) rids.push(dz.id);
    if (dz && dz.offs) dz.offs.forEach((o) => rids.push(o.id));
    _metaDragZRestore(rids);
  }
  // group-interact(§50): sim-group 리지드 드래그 종료 → grabbed 델타를 groupOffset 에 누적 + 소속 멤버
  //   nodePos(절대좌표)도 같은 델타로 시프트(freeplace clusterOffset MAJOR fix 동형 — 개별 배치 노드가
  //   그룹 이동에서 분리되지 않게). 시각 위치는 이미 drag-element+리지드 핸들러가 최종화 — 즉시 rebuild 불요.
  const gd = _metaGraph._drag;
  // graph-category(§55 A): 카테고리 밴드 리지드 드래그 종료 → 델타를 **멤버 클러스터별 clusterOffset 에
  //   일괄 누적**(신규 offset 계층 없이 기존 ① 계층 재사용) + 소속 nodePos 동반 시프트(freeplace MAJOR
  //   fix 동형) → rebuild 로 CAT 박스 재파생(반응형).
  if (gd && gd.cat) {
    _metaGraph._drag = null;
    let p; try { p = g && g.getElementPosition(gd.id); } catch (_) { p = null; }
    if (p && isFinite(p[0]) && isFinite(p[1])) {
      const dx = p[0] - gd.startX, dy = p[1] - gd.startY;
      if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) {
        const cset = new Set(gd.catClusters || []);
        cset.forEach((cid) => {
          const prev = _metaGraph.clusterOffset.get(cid) || { dx: 0, dy: 0 };
          _metaGraph.clusterOffset.set(cid, { dx: prev.dx + dx, dy: prev.dy + dy });
        });
        _metaGraph.nodePos.forEach((pos, nid) => {
          const n = _metaGraph.nodes.get(nid);
          if (n && cset.has(_metaSchemaComboOf(n))) { pos[0] += dx; pos[1] += dy; }
        });
        _metaG6Apply(false);
      }
    }
    return;
  }
  if (gd && gd.group) {
    _metaGraph._drag = null;
    let p; try { p = g && g.getElementPosition(gd.id); } catch (_) { p = null; }
    if (p && isFinite(p[0]) && isFinite(p[1])) {
      const dx = p[0] - gd.startX, dy = p[1] - gd.startY;
      if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) {
        const prev = _metaGraph.groupOffset.get(gd.group) || { dx: 0, dy: 0 };
        _metaGraph.groupOffset.set(gd.group, { dx: prev.dx + dx, dy: prev.dy + dy });
        const members = _metaGraph.groupMembers.get(gd.group);
        if (members) members.forEach((tk) => { const pos = _metaGraph.nodePos.get(tk); if (pos) { pos[0] += dx; pos[1] += dy; } });
      }
    }
    return;
  }
  // graph-freeplace: 접힌 스키마 카드("SC:") 드래그 = 클러스터 이동 → clusterOffset(combo 드래그와 통합).
  if (id && String(id).startsWith("SC:")) { _metaClusterDragCommit(); _metaGraph._drag = null; return; }
  // 그 외 이동 가능 노드(테이블·컬럼·용어)의 최종 절대위치를 nodePos 에 기록 → rebuild 후에도 유지.
  //   컨트롤/장식(X:/XS:/GB:/GH:/GX:)은 제외. 테이블은 위치만 기록하고, 종속(컬럼·"X:")은 build 가 테이블 델타로 시프트.
  if (g && id && !/^(X:|XS:|XR:|RP:|GB:|GH:|GX:|CAT:|CATH:|CATX:)/.test(String(id))) {   // §54⑤·§55: 장식/밴드 — nodePos 오염 방지
    // 컬럼은 소속 테이블에서 재파생(build)되므로 개별 위치를 기록하지 않는다(dead 엔트리·재빌드 snap-back 방지, 리뷰 NIT).
    const _n = _metaGraph.nodes.get(id);
    if (!_n || _n.label !== "Column") {
      try { const p = g.getElementPosition(id); if (p && isFinite(p[0]) && isFinite(p[1])) _metaGraph.nodePos.set(id, [p[0], p[1]]); } catch (_) {}
    }
    // group-interact(§50, #3 반응형): 그룹 소속 테이블을 옮기면 GB 박스가 새 경계를 감싸도록 rebuild(박스=멤버 bbox 파생).
    //   비-그룹(평면 masonry) 테이블은 기존대로 combo auto-fit 만 — rebuild 없음(회귀 0).
    if (_metaGraph.groupOf.get(id)) { _metaGraph._drag = null; _metaG6Apply(false); return; }
  }
  _metaGraph._drag = null;
}

// graph-freeplace: 스키마 클러스터(combo) 드래그 — 전체 클러스터 위치 이동("분류 drag&drop 위치 이동").
//   dragstart 에서 중심을 기록하고 dragend 에서 델타를 clusterOffset 에 누적 → build 가 L.x0/L.y0 에 가산해
//   카드·테이블·컬럼·장식을 coherent 하게 이동시키고 rebuild(펼침/접기) 후에도 유지한다.
function _metaComboDragStart(e) {
  const g = _metaGraph.graph;
  const id = e && e.target && e.target.id;
  _metaGraph._comboDragStart = null;
  if (!g || !id) return;
  try { const p = g.getElementPosition(id); if (p) _metaGraph._comboDragStart = { comboId: id, curId: id, x: p[0], y: p[1] }; } catch (_) {}
}
function _metaComboDragEnd(e) {
  const id = e && e.target && e.target.id;
  _metaClusterDragCommit();
  // graph-zorder(§52): 내장 drag-element frontElement 는 combo 드래그 시 combo+**하위 전체(내부 엣지
  //   포함)**를 델타 승격(영구 잔존·반복 시 단조 증가 — 드래그 이력이 클러스터 간 z-order 로 굳음).
  //   드래그 중에는 그 coherent 승격을 그대로 쓰고(시각적으로 자연), 종료 시 같은 범위를 canonical 로
  //   복원한다 — 노드+콤보(_metaComboMemberIds) + 엣지(_metaComboEdgesRestore, 패널 ux BLOCKING).
  if (id) { _metaDragZRestore([id].concat(_metaComboMemberIds(id))); _metaComboEdgesRestore(id); }
}
// combo:dragend · 접힌 카드 dragend 공용 커밋: _comboDragStart 의 델타를 clusterOffset 에 누적 후 클리어.
function _metaClusterDragCommit() {
  const st = _metaGraph._comboDragStart;
  _metaGraph._comboDragStart = null;
  if (!st || !st.comboId) return;
  _metaClusterOffsetAccumulate(st.comboId, st.x, st.y, st.curId);
}

// G6 v5 그래프 초기화(1회). 이후 상태변경은 _metaG6Apply(setData+draw). Canvas 렌더러(선명·벡터).
function _metaInitGraph() {
  const container = document.getElementById("metadataGraphCanvas");
  if (!container) return;
  const _rk = _metaRendererKind();   // feature-0016 §78: 'pixi' | 'g6'
  if (_rk === "g6" && (!window.G6 || typeof window.G6.Graph !== "function")) {
    _metaGraphStatus("그래프 라이브러리(G6)를 불러오지 못했습니다.");
    return;
  }
  if (_rk === "pixi" && !window.PIXI) {
    _metaGraphStatus("그래프 라이브러리(PixiJS)를 불러오지 못했습니다.");
    return;
  }
  if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} return; }
  if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
  const baseCfg = {
    container,
    autoResize: true,
    // graph-initview(A2): 과도 줌아웃/과확대 하드 클램프(Cytoscape 시절 minZoom/maxZoom 의 G6 이식).
    zoomRange: [0.05, 4],
    // 상태 스타일만 config 로(기본 스타일은 per-element 인라인 — 매퍼 undefined→To() 크래시 회피).
    node: { state: {
      // feature-0016 §45: 검색 매칭 soft glow — 예전 '너비 증가' 대신 부드러운 앰버 글로우(shadow)로 매칭 강조.
      //   shadow 계열이라 selected/analyzed 의 stroke 와 독립적으로 공존(테두리색 충돌 없음). animation:false 라
      //   전환은 즉시지만 넓은 blur 가 시각적으로 '부드러운' 하이라이트로 읽힌다.
      match: { stroke: "#e8a400", lineWidth: 2, shadowColor: "#f4b400", shadowBlur: 18 },
      analyzed: { stroke: "#7b2fbe", lineWidth: 3 },
      // node-role-viz(적대 패널 U2): 역할색 fill(특히 log #E69F00) 위에서 주황 점선이 위장되지 않게
      //   진행 중엔 fill 을 desaturate — 어느 역할색 위에서도 "분석 중" 이 읽힌다(재분석 경로 실재).
      running: { stroke: "#e08a1e", lineWidth: 2, lineDash: [4, 3], fillOpacity: 0.45 },
      // node-role-viz(적대 패널 U1): 선택 테두리 #9c6515(앰버)는 log/config 역할색과 동계열이라 위장 —
      //   전 역할색·teal 위에서 성립하는 어두운 무채색으로 교체(흰 캔버스 경계 대비 확보).
      selected: { stroke: "#161b22", lineWidth: 3 },
      busy: { stroke: "#0a5b66", lineWidth: 3, lineDash: [2, 2] },   // graph-perf-bg: 펼침/확장 조회 중 임시 표시(teal 점선)
      // §57(사용자 요구 ②): 상대 하이라이트 — 선택 1-hop 밖 데이터 노드 흐리게.
      //   §57.5: 0.15→0.38(라벨 판독 유지). §57.9(사용자 4차 실측): 침강 opacity 는 이제 **G6 상태가
      //   아니라 base style 에 직접 굽는다**(_metaBakeBaseOpacity, dim=_META_DIM_OPACITY/lit=1). 상태로
      //   두면 dimmed 제거 시 G6 가 base 로 복원하지 못해 선택 노드가 0.38 로 stale 하게 남았다(실측).
      //   'dimmed' 문자열은 상태 배열에 계속 실려 서명 비교(rebuild 감지)·base bake 입력으로 쓰인다.
    } },
    // graph-drag(edge-midpan fix): 엣지(관계선)를 드래그 소스로 등록(draggable). @antv/g-plugin-dragndrop 는
    //   pointerdown 대상의 closest("[draggable=true]") 를 드래그 소스로 삼아 drag 이벤트를 합성하는데, 노드/콤보만
    //   draggable 기본값(true)이고 엣지는 아니라, 관계선 위에서 시작한 드래그는 dragstart 자체가 발화하지 않아
    //   drag-canvas(중간버튼 카메라 팬)가 발동하지 않았다(관계선 위 중간드래그 무반응 버그). 엣지 draggable=true 로
    //   드래그가 합성되면 global dragstart → drag-canvas.enable(_metaCanvasDragEnable) 이 중간버튼 팬을 허용한다.
    //   엣지가 실제로 "이동"되지는 않는다 — drag-element 는 enableElements=["node","combo"] 라 edge:dragstart 를
    //   아예 바인딩하지 않으므로(_metaElementDragEnable 도달 전에 미발동), 관계선은 위치가 바뀌지 않는다. 좌드래그는
    //   targetType!=="canvas" 라 _metaCanvasDragEnable 이 false → 팬 안 됨(기존 동작 보존, 클릭/우클릭 메뉴 정상).
    //   ⚠ 위 6053 계약("기본 스타일은 config 아닌 per-element 인라인 — 매퍼 undefined→To() 크래시 회피")의 유일한
    //   예외: draggable 은 정적 boolean(매퍼·애니메이션 대상 아님)이라 안전. 여기에 함수 매퍼/애니메이션 수치
    //   프롭을 추가하지 말 것 — 그 순간 6053 이 경고한 To() 크래시가 재현된다(정적 boolean 만 허용).
    edge: { style: { draggable: true } },
    // graph-drag: 중간 버튼 드래그 = 카메라 팬(어디서든), 좌클릭 = 기존대로(빈 캔버스 팬 / 노드 이동).
    behaviors: [
      { type: "drag-canvas", key: "drag-canvas", enable: _metaCanvasDragEnable },
      "zoom-canvas",
      { type: "drag-element", key: "drag-element", enable: _metaElementDragEnable },
    ],
    animation: false,
  };
  // graph-initview(E1): 미니맵 — 초기 화면이 "부분"이 될 수 있으므로 전체 지도+뷰포트 표시로 보완.
  // 플러그인 미지원 번들이면 그래프 자체는 살린다(minimap 없이 재생성 — 번들 교체 시 POC 재검증 전제).
  let graph = null;
  if (_rk === "pixi") {
    // feature-0016 §78: PixiGraphAdapter — baseCfg(container/autoResize/zoomRange/node.state) 소비.
    //   behaviors/edge.style/plugins(minimap) 는 어댑터가 자체 처리(중버튼 팬·좌클릭 노드드래그·자체 미니맵).
    // §78 적대리뷰 M2: 어댑터는 G6 behaviors 를 소비 안 하므로 drag-enable predicate 를 명시 주입 —
    //   GX:/CATX: 접기 컨트롤·접힌 카테고리 밴드가 pixi 에서 드래그돼 clusterOffset 을 오염시키는 것을 차단.
    try { graph = new PixiGraphAdapter(Object.assign({}, baseCfg, { minimap: true, minimapSize: [168, 112], renderer: "webgl",
      elementDragEnable: _metaElementDragEnable, canvasDragEnable: _metaCanvasDragEnable })); } catch (_) { graph = null; }
    if (!graph) { _metaGraphStatus("그래프 초기화 실패(PixiJS)."); return; }
  } else {
    try {
      graph = new window.G6.Graph(Object.assign({}, baseCfg, { plugins: [{ type: "minimap", key: "minimap", size: [168, 112], position: "right-bottom" }] }));   // graph-minimap-reuse: 명시 key → getPluginInstance("minimap") 직접 히트(by-type 폴백 경고 회피)
    } catch (_) { graph = null; }
    if (!graph) {
      try { graph = new window.G6.Graph(baseCfg); } catch (_) { graph = null; }
    }
    if (!graph) { _metaGraphStatus("그래프 초기화 실패(G6)."); return; }
  }
  _metaGraph.graph = graph;
  // graph-minimap-reuse: 미니맵 재사용 패치는 여기(init)서 걸지 않는다 — G6 v5 는 context.plugin 을 첫 draw 의
  //   initRuntime() 에서 lazy 생성하므로 이 시점 getPluginInstance("minimap") 는 실패한다. _metaG6ApplyOnce 의
  //   `await g.draw()` 직후에 멱등 호출로 건다(첫 draw 후 plugin 존재).
  // feature-0016 §45: 그래프 pane 자체 데이터소스 스코프 select — 변경 시 그 데이터소스 그래프(roots) 재로드.
  //   메타데이터 pane 의 metadataScopeSelect 와 상태(scopeKey)를 공유하되 양쪽 select 값을 동기화한다. 1회 바인딩.
  const _gsc = document.getElementById("graphScopeSelect");
  if (_gsc && !_gsc.dataset.bound) {
    _gsc.dataset.bound = "1";
    _gsc.addEventListener("change", () => {
      adminState.metadata.scopeKey = _gsc.value || "common";
      const ms = document.getElementById("metadataScopeSelect");
      if (ms) ms.value = _gsc.value || "common";
      _metaGraphLoadRoots();
    });
  }
  graph.on("node:click", (e) => _metaGraphOnNodeClick(e));
  graph.on("combo:click", (e) => { const id = e && e.target && e.target.id; if (id) _metaGraphShowClusterDetailById(id); });
  // §57(사용자 요구 ②): 빈 캔버스 클릭 = 선택/상대 하이라이트 해제. §18.8 패널 MINOR: 좌클릭 팬
  //   직후 click 오발화 가드 — pointerdown 대비 이동 5px 초과면 팬으로 간주(선택 보존).
  let _cvDown = null;
  try { container.addEventListener("pointerdown", (ev) => { _cvDown = { x: ev.clientX, y: ev.clientY }; }, true); } catch (_) {}
  graph.on("canvas:click", (e) => {
    if (!_metaGraph.selected) return;
    const cx = e && e.client ? e.client.x : null, cy = e && e.client ? e.client.y : null;
    if (_cvDown && cx != null && cy != null
        && (Math.abs(cx - _cvDown.x) > 5 || Math.abs(cy - _cvDown.y) > 5)) return;
    _metaGraphSetSelected(null);
  });
  // §57(declutter): 줌 밴드(LOD 임계) 전이 시에만 디바운스 rebuild — 경계 부근 휠 미세조작 왕복 방지.
  //   §18.8 패널 BLOCKING: G6 v5 번들에 'viewportchange' 이벤트 없음(grep 실증) — 줌/팬은
  //   GraphEvent.AFTER_TRANSFORM('aftertransform')으로 발화한다. 밴드 미전이는 즉시 return 이라
  //   transform 다발 발화 비용은 비교 1회뿐.
  if (_metaGraph._lodBand === undefined) _metaGraph._lodBand = null;
  graph.on("aftertransform", () => {
    let z = 1;
    try { z = graph.getZoom() || 1; } catch (_) { return; }
    // viewport-cull(§65): 컬링 활성 중 팬으로 뷰포트 중심이 build 커버 범위를 크게 벗어나면(마진 소진) 새로
    //   보이는 테이블의 컬럼을 위해 rebuild. graph-cull-realtime(§76, 사용자 요구 "드래그 도중 실시간 컬링 재계산"):
    //   과거 260ms 디바운스는 드래그 **정착 후**에만 반영해 드래그 중 새 노드가 늦게 튀어나왔다(pop). 메모이즈(§73)로
    //   rebuild layout 비용이 사라져(8ms) 이제 **rAF 스로틀**로 드래그 매 프레임 재-emit 가능 — _metaG6Apply 는 직렬화
    //   (진행 중이면 1회 병합)라 rebuild 코스트가 크면 자연히 프레임 스킵돼 파일업 없이 코스트에 적응한다. 순수 팬은
    //   아래 밴드 로직이 `band===_lodBand` 로 즉시 return(rAF 유지), 줌+팬은 밴드 debounce 가 마커·기준선을 별도 갱신.
    if (_metaGraph._cullActive && _metaGraph._cullVp) {
      try {
        const _s = graph.getSize(), _a = graph.getCanvasByViewport([0, 0]), _b = graph.getCanvasByViewport([_s[0], _s[1]]);
        const _cx = (_a[0] + _b[0]) / 2, _cy = (_a[1] + _b[1]) / 2, _V = _metaGraph._cullVp;
        // 임계 0.35(구 0.5) — rAF 로 자주 재산정하므로 더 이른 예측 재-emit 로 경계 pop 을 마진 소진 전 흡수.
        if (Math.abs(_cx - _V.cx) > _V.hw * 0.35 || Math.abs(_cy - _V.cy) > _V.hh * 0.35) {
          if (!_metaGraph._cullRaf) {
            const _raf = (typeof window !== "undefined" && window.requestAnimationFrame) ? window.requestAnimationFrame.bind(window) : (f) => setTimeout(f, 16);
            _metaGraph._cullRaf = _raf(() => { _metaGraph._cullRaf = null; try { _metaG6Apply(false); } catch (_) {} });
          }
        }
      } catch (_) {}
    }
    // col-lod(§61)+agg-lod(§63): 4단 밴드 — full(≥0.5) / collod(0.35~0.5: 컬럼억제) / lod(0.15~0.35: 컬럼+엣지억제)
    //   / agg(<0.15: 클러스터 집계). 어느 임계(0.5·0.35·0.15)를 교차해도 밴드가 바뀌어 디바운스 rebuild 로 반영한다.
    const band = z < _META_AGG_ZOOM ? "agg" : (z < _META_EDGE_LOD_ZOOM ? "lod" : (z < _META_COL_LOD_ZOOM ? "collod" : "full"));
    if (band === _metaGraph._lodBand) return;
    const prev = _metaGraph._lodBand;
    _metaGraph._lodBand = band;
    if (prev === null) return;   // 최초 관측(로드/스코프 전환 직후)은 기준선만 세움 — 스퓨리어스 rebuild 방지
    if (_metaGraph._lodTimer) clearTimeout(_metaGraph._lodTimer);
    _metaGraph._lodTimer = setTimeout(() => {
      _metaGraph._lodTimer = null;
      // §57.8: busy 게이트 제거 — _metaG6Apply 는 직렬화(진행 중이면 재실행 1회 병합)라 fetch apply 와
      //   안전히 조율된다. 과거 busy 유예는 _lodBand=null 리셋으로 밴드 기준선을 잃어, busy 창이
      //   길어진 §57.8 에서 줌아웃 LOD 축약이 통째로 누락되는 "최초 관측 skip" 을 유발했다.
      try { _metaG6Apply(false); } catch (_) {}
      // §57 패널 MINOR: LOD 축약 안내 — 사용자가 '관계 없음'으로 오독하지 않게 상태줄에 1줄.
      try {
        const st = document.getElementById("metadataGraphStatus");
        if (st) {
          // col-lod(§61)+agg-lod(§63): 안내는 **밴드 문자열이 아니라 실제 억제 플래그**로 게이트한다 — 억제
          //   (lodActive/colLodActive)는 원시 줌 임계(0.35/0.5)로 산정돼 밴드(agg/lod/collod)와 독립이라,
          //   밴드로 게이트하면 band=agg·aggActive=false(nodes≤60·edges>120) 구간에서 실제 관계선 축약이
          //   일어나는데 마커만 침묵해 §57 '관계 없음' 오독-가드가 재발한다(리뷰 MINOR). 과거 변형 마커도 회수.
          const base = String(st.innerText || "").replace(/ · (줌아웃|개요)[^\n]*?\(확대 시[^)]*\)/g, "");
          const aggCut = !!_metaGraph._aggActive;              // 집계 실제 활성(클러스터 강등)
          const edgeCut = (_metaGraph._lodDropped || 0) > 0;   // 관계선 실제 드롭(lodActive 결과)
          const colCut = !!_metaGraph._colLodActive;           // 컬럼 실제 억제
          // agg-lod(§63): 집계 상태 안내는 제거(사용자 피드백 "그래서 뭐?" — 그래프 사용에 무의미·노이즈).
          //   집계는 카드로 자명하다. col/edge LOD 안내는 §57 오독-가드 목적이라 유지(비-집계 밴드에서만).
          const marker = aggCut ? ""
            : (edgeCut && colCut) ? " · 줌아웃 — 컬럼·관계선 일부 축약(확대 시 전체 표시)"
            : colCut ? " · 줌아웃 — 컬럼 표시 축약(확대 시 전체 표시)"
            : edgeCut ? " · 줌아웃 — 관계선 일부 축약(확대 시 전체 표시)" : "";
          const showMarker = !!marker;
          st.innerText = showMarker ? (base + marker) : base;
          // graph-toolbar-consolidate: 이 마커는 _metaGraphStatus 를 거치지 않고 innerText 를 직접 조작하므로,
          //   줌아웃 상태 안내가 auto-fade(is-idle)로 흐려지지 않게 표시 중엔 유휴 클래스를 해제하고 fade 타이머도 취소한다
          //   (마커는 줌아웃이 유지되는 동안 지속되는 상태 표시 — review MINOR: 6s 뒤 사라지던 것 방지).
          if (showMarker) {
            st.classList.remove("is-idle");
            if (_metaGraph._statusTimer) { clearTimeout(_metaGraph._statusTimer); _metaGraph._statusTimer = null; }
          }
        }
      } catch (_) {}
    }, 300);
  });
  // graph-ctxmenu: 우클릭 상호작용 메뉴(REQ-20260702T113000). 좌표는 container capture 리스너가
  //   선캡처(_metaCtx.x/y — capture 단계가 G6 캔버스 target 핸들러보다 먼저 실행됨). G6 이벤트에
  //   client 좌표가 실리면 그것을 우선 사용. "X:" 접기 컨트롤 우클릭은 소속 테이블 메뉴로 귀속.
  graph.on("node:contextmenu", (e) => {
    let id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    // graph-initview: 스키마 카드("SC:")·펼친 스키마 접기 ctl("XS:") 우클릭 → 스키마 전용 메뉴로 귀속.
    //   이 prefix 를 안 벗기면 _metaGraphCtxForNode 가 모델(SC: 없는 순수 key)에서 노드를 못 찾아 무반응.
    // graph-category(§55 A): 카테고리 밴드 요소 우클릭 — 노드 메뉴 부적합(합성 밴드) → 메뉴 숨김(무반응 방지 후속 여지).
    if (/^CAT(H|X)?:/.test(String(id))) { _metaGraphCtxHide(); return; }
    if (String(id).startsWith("GB:") || String(id).startsWith("GH:") || String(id).startsWith("GX:")) {   // graph-simgroups(§18.8 MAJOR): 그룹 박스/헤더/컨트롤(GX 포함, group-interact §50 REV) 우클릭 = 소속 스키마 메뉴(combo 배경 대체 — 데드존 방지)
      const gk = String(id).slice(3), sep = gk.indexOf("\u0001");
      if (sep >= 0) _metaGraphCtxForSchema(gk.slice(0, sep), p.x, p.y); else _metaGraphCtxHide();
      return;
    }
    if (String(id).startsWith("SC:")) { _metaGraphCtxForSchema(id.slice(3), p.x, p.y); return; }
    if (String(id).startsWith("XS:")) { _metaGraphCtxForSchema(id.slice(3), p.x, p.y); return; }
    if (String(id).startsWith("XR:")) id = String(id).slice(3);   // §54⑤: 루틴 파라미터 ctl → 소속 루틴 메뉴
    else if (String(id).startsWith("RP:")) id = String(id).slice(3).replace(/:\d+$/, "");   // §54⑤: 파라미터 행 → 소속 루틴
    else if (String(id).startsWith("X:")) id = String(id).slice(2);   // 테이블 접기 ctl → 소속 테이블 메뉴
    _metaGraphCtxForNode(id, p.x, p.y);
  });
  graph.on("combo:contextmenu", (e) => {
    const id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    _metaGraphCtxForCombo(id, p.x, p.y);
  });
  graph.on("edge:contextmenu", (e) => {
    // review MAJOR-2: 관계선 자체도 우클릭 대상 — 신뢰도·근거 + 양끝 노드 이동.
    const id = e && e.target && e.target.id;
    if (!id) return;
    const p = _metaCtxPoint(e);
    _metaGraphCtxForEdge(id, p.x, p.y);
  });
  graph.on("canvas:contextmenu", (e) => {
    const p = _metaCtxPoint(e);
    _metaGraphCtxForCanvas(p.x, p.y);
  });
  // capture 단계: 캔버스 전역 브라우저 기본 메뉴 차단 + 클라이언트 좌표 캡처.
  container.addEventListener("contextmenu", (ev) => {
    ev.preventDefault();
    _metaCtx.x = ev.clientX; _metaCtx.y = ev.clientY;
  }, true);
  // graph-drag(REQ ①): 중간(휠) 버튼 mousedown 의 브라우저 기본 동작(자동 스크롤 = 팬 커서)을
  //   억제해 G6 카메라 팬만 남긴다. pointer 이벤트 흐름은 유지되므로 drag-canvas 는 정상 작동.
  container.addEventListener("mousedown", (ev) => {
    if (ev.button === 1) ev.preventDefault();
  }, true);
  // graph-drag(REQ ②): 테이블 노드를 드래그하면 그 하위 종속 UI(접기 "X:" 컨트롤 + 컬럼 노드)도
  //   함께 이동한다. dragstart 에서 각 종속의 테이블 대비 월드 오프셋을 고정 기록하고, node:drag/
  //   dragend 마다 종속을 "테이블 현재 월드좌표 + 오프셋" 으로 translateElementTo 절대이동한다
  //   — 절대-오프셋이라 핸들러 실행 순서·누적 delta·줌 배율에 무관(월드좌표 기준).
  graph.on("node:dragstart", (e) => _metaNodeDragStart(e));
  graph.on("node:drag", (e) => _metaNodeDrag(e));
  graph.on("node:dragend", (e) => _metaNodeDragEnd(e));
  // graph-freeplace: 클러스터(combo) 드래그 = 분류 위치 이동(clusterOffset 누적 → rebuild 유지).
  graph.on("combo:dragstart", (e) => _metaComboDragStart(e));
  graph.on("combo:dragend", (e) => _metaComboDragEnd(e));
  if (!_metaGraph.bound) {
    _metaGraph.bound = true;
    const s = document.getElementById("metadataGraphSearch");
    if (s) {
      let t = null;
      s.addEventListener("input", () => { if (t) clearTimeout(t); t = setTimeout(() => _metaGraphSearch(s.value.trim()), 300); });
    }
    const reset = document.getElementById("metadataGraphResetBtn");
    if (reset) reset.addEventListener("click", () => { _metaGraphLoadRoots(); });
    // graph-product-cat(§43): 제품 카테고리 개요 진입 — scope 를 제품 개요로 전환(공유 scope select 는 datasource 전용 유지).
    const prodBtn = document.getElementById("metadataGraphProductsBtn");
    if (prodBtn) prodBtn.addEventListener("click", () => { adminState.metadata.scopeKey = "__products__"; _metaGraphLoadProducts("__products__"); });
    // graph-initview(E2): 줌 툴바 — +/− 단계 줌, 전체(클램프 없는 조망), 100%.
    const zin = document.getElementById("metaGraphZoomIn");
    if (zin) zin.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomBy(1.25, false); } catch (_) {} } });
    const zout = document.getElementById("metaGraphZoomOut");
    if (zout) zout.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomBy(0.8, false); } catch (_) {} } });
    const zfit = document.getElementById("metaGraphZoomFit");
    if (zfit) zfit.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.fitView({ padding: 30 }, false); } catch (_) {} } });
    const z100 = document.getElementById("metaGraphZoom100");
    if (z100) z100.addEventListener("click", () => { const g = _metaGraph.graph; if (g) { try { g.zoomTo(1, false); } catch (_) {} } });
    // graph-initview(E3): 스키마 점프 — 판독 줌 보장 후 해당 클러스터/카드로 focus.
    const jump = document.getElementById("metadataGraphJump");
    if (jump) jump.addEventListener("change", async () => {
      const g = _metaGraph.graph;
      const key = jump.value;
      if (!g || !key) return;
      try {
        const z = (typeof g.getZoom === "function") ? g.getZoom() : 1;
        if (isFinite(z) && z < _META_MIN_READ_ZOOM) await g.zoomTo(_META_MIN_READ_ZOOM, false);
        const el = _metaRenderedIdFor(key);   // 접힌 스키마는 카드(SC:) 로 렌더됨
        if (el) await g.focusElement(el, false);
      } catch (_) {}
      jump.value = "";
    });
    const tgl = document.getElementById("metadataGraphDetailToggle");
    if (tgl) tgl.addEventListener("click", () => {
      const body = document.getElementById("metadataGraphView");
      if (body) body.classList.toggle("detail-collapsed");
      setTimeout(() => { if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} _metaGraphFitClamped(false); } }, 60);
    });
    const depthSel = document.getElementById("metadataGraphDepth");
    if (depthSel) depthSel.addEventListener("change", () => {
      const key = _metaGraph.selected || _metaGraph.lastDetailKey || null;
      if (key) { _metaGraphExpand(key); }
      else { _metaGraphStatus(`이웃 깊이 ${depthSel.value}-hop 적용 — 노드를 선택/더블클릭하면 이 깊이로 확장됩니다.`); }
    });
    // graphux7(#1): 상세 패널 방문 이력 뒤로/앞으로.
    const dnBack = document.getElementById("metaGraphDetailBack");
    if (dnBack) dnBack.addEventListener("click", () => _metaGraphHistoryGo(-1));
    const dnFwd = document.getElementById("metaGraphDetailFwd");
    if (dnFwd) dnFwd.addEventListener("click", () => _metaGraphHistoryGo(1));
    // graph-navfilter(§54②): 노드 종류 표시 필터 토글 — Set 갱신 → 버튼 시각 → 전체 rebuild(제자리).
    //   localStorage 영속(metaGraphHiddenKinds, metaGraphDetailW 관례) — scope-독립 preference.
    const _kindLabelKo = { edges: "관계선", function: "ƒ 함수", procedure: "⚙ 프로시저" };
    const _kindBtns = ["metaGraphKindEdges", "metaGraphKindFn", "metaGraphKindProc"]
      .map((bid) => document.getElementById(bid)).filter(Boolean);
    try {
      const saved = JSON.parse(localStorage.getItem("metaGraphHiddenKinds") || "[]");
      if (Array.isArray(saved)) saved.forEach((k) => { if (Object.prototype.hasOwnProperty.call(_kindLabelKo, k)) _metaGraph.hiddenKinds.add(k); });
    } catch (_) {}
    _kindBtns.forEach((b) => {
      const k = b.getAttribute("data-kind");
      const shown = !_metaGraph.hiddenKinds.has(k);
      b.classList.toggle("is-active", shown);
      b.setAttribute("aria-pressed", String(shown));
      b.addEventListener("click", () => {
        const hide = !_metaGraph.hiddenKinds.has(k);
        if (hide) _metaGraph.hiddenKinds.add(k); else _metaGraph.hiddenKinds.delete(k);
        b.classList.toggle("is-active", !hide);
        b.setAttribute("aria-pressed", String(!hide));
        try { localStorage.setItem("metaGraphHiddenKinds", JSON.stringify(Array.from(_metaGraph.hiddenKinds))); } catch (_) {}
        _metaG6Apply(false);   // 카메라 유지 rebuild — masonry/simgroups 가 자리 자동 회수(GX 토글 동형)
        _metaGraphStatus(hide ? `${_kindLabelKo[k]} 숨김 — 그래프에서 제외하고 재배치했습니다.`
                              : `${_kindLabelKo[k]} 표시 — 그래프에 복원했습니다.`);
        _metaGraphSyncViewOptsBadge();   // graph-toolbar-consolidate: 팝오버 버튼 배지(숨긴 종류 수) 갱신
      });
    });
    _metaGraphSyncViewOptsBadge();   // graph-toolbar-consolidate: 복원된 hiddenKinds 반영한 초기 배지
    // graph-toolbar-consolidate: '보기 옵션' 팝오버 토글 — 버튼 클릭 open/close, 바깥 클릭·Esc 로 닫기.
    //   종류 필터 토글·깊이/스키마 select 조작 중엔 열어두고(연속 조작), 제품 카테고리 등 네비게이션 클릭이나
    //   바깥 클릭이면 닫는다.
    const voBtn = document.getElementById("metaGraphViewOptsBtn");
    const voMenu = document.getElementById("metaGraphViewOptsMenu");
    if (voBtn && voMenu && !voBtn._bound) {
      voBtn._bound = true;
      const setVO = (open) => { voMenu.hidden = !open; voBtn.setAttribute("aria-expanded", String(open)); };
      voBtn.addEventListener("click", (ev) => { ev.stopPropagation(); setVO(voMenu.hidden); });
      document.addEventListener("click", (ev) => {
        if (voMenu.hidden) return;
        const t = ev.target;
        if (t === voBtn || voBtn.contains(t)) return;   // 버튼은 위 토글 핸들러가 처리
        if (voMenu.contains(t)) {
          // 팝오버 자체(라벨·여백·필터·select)를 클릭해도 닫지 않는다 — 라벨/여백 클릭에 조기 닫힘 방지(review MINOR).
          //   네비게이션 커밋인 '제품 카테고리'(뷰 전환)만 닫는다.
          if (t.closest("#metadataGraphProductsBtn")) setVO(false);
          return;
        }
        setVO(false);   // 바깥 클릭 → 닫기
      });
      document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !voMenu.hidden) { setVO(false); try { voBtn.focus(); } catch (_) {} } });
    }
    _metaGraphInitResizer();
  }
}

// 노드 클릭 라우팅: "−" ctl=접기 · 단일=상세(+테이블은 펼침 전용) · 더블(320ms)=이웃 확장.
//   버그① 해소: 펼쳐진 테이블 body 클릭은 접지 않는다(접기는 "−" 컨트롤만).
function _metaGraphOnNodeClick(e) {
  const id = e && e.target && e.target.id;
  if (!id) return;
  // graph-category(§55 A): 카테고리 밴드 접기/펼치기(CATX) + 밴드/헤더 클릭 = 카테고리 상세.
  if (String(id).startsWith("CATX:")) {
    const ck = String(id).slice(5);
    if (_metaGraph.catCollapsed.has(ck)) _metaGraph.catCollapsed.delete(ck);
    else _metaGraph.catCollapsed.add(ck);
    _metaG6Apply(false);
    return;
  }
  if (String(id).startsWith("CATH:") || String(id).startsWith("CAT:")) {
    const ck = String(id).slice(String(id).startsWith("CATH:") ? 5 : 4);
    _metaGraphShowCategoryDetail(ck);
    return;
  }
  // group-interact(§50): 카테고리 그룹 접기/펼치기 토글(GX 컨트롤 — GB/GH 보다 먼저 판정). groupCollapsed 는
  //   사용자 지속 의도로 보존하고, 검색 시 매칭 그룹만 build 가 강제 펼침(결과 가시).
  if (String(id).startsWith("GX:")) {
    const gk = String(id).slice(3);
    if (_metaGraph.groupCollapsed.has(gk)) _metaGraph.groupCollapsed.delete(gk);
    else _metaGraph.groupCollapsed.add(gk);
    _metaG6Apply(false);
    return;
  }
  // graph-simgroups(§18.8 패널 MAJOR): 그룹 배경/헤더의 **클릭(무이동)** 은 소속 스키마 클러스터 상세로 위임
  //   (데드존 방지). group-interact(§50): GB/GH 는 이제 드래그 가능 — G6 이동 임계값으로 click/drag 를 구분하므로
  //   무이동 클릭만 여기 도달(드래그는 node:dragstart/end 리지드 경로).
  if (String(id).startsWith("GB:") || String(id).startsWith("GH:")) {
    const gk = String(id).slice(3), sep = gk.indexOf("\u0001"), sc = sep >= 0 ? gk.slice(0, sep) : null;
    if (sc) _metaGraphShowClusterDetailById(sc);
    return;
  }
  if (String(id).startsWith("XS:")) { _metaGraphCollapseSchema(id.slice(3)); return; }   // graph-initview: 스키마 접기
  // graph-navfilter(§54⑤): 루틴 파라미터 접기 ctl — 모델 삭제 없이 Set 토글(합성 노드라 rebuild 로 소멸).
  //   "XR:" 은 콜론 위치상 startsWith("X:") 에 안 걸리지만 XS: 관례대로 X: 보다 먼저 명시 판정.
  if (String(id).startsWith("XR:")) { _metaGraph.routineExpanded.delete(id.slice(3)); _metaG6Apply(false); return; }
  if (String(id).startsWith("X:")) { _metaGraphCollapse(id.slice(2)); return; }
  // graph-navfilter(§54⑤): 파라미터 행 클릭 → 소속 루틴 상세(RP: 는 합성 id — bogus API fetch 차단).
  //   routine key 자체에 ':' 가 있으므로 꼬리 인덱스(:N)만 strip.
  if (String(id).startsWith("RP:")) { _metaGraphShowDetail(String(id).slice(3).replace(/:\d+$/, "")); return; }
  if (String(id).startsWith("SC:")) {
    // graph-initview: 스키마 카드 클릭 = 그 스키마 테이블 lazy 펼침 + 클러스터 상세(더블클릭 구분 불필요 —
    // 스키마의 이웃확장은 곧 테이블 펼침). 상세는 펼침 성공 시에만 모델 로컬 렌더(실패/빈/stale 시 오도 패널 방지).
    const sk = id.slice(3);
    _metaGraphExpandSchema(sk).then((st) => {
      if (st === "expanded" || st === "already") _metaGraphShowClusterDetailLocal(sk);
    }).catch(() => {});
    return;
  }
  // graph-product-cat(§43): 제품 개요 노드 — Datasource 클릭 → 그 데이터소스 스키마 그래프로 drill(scope 전환),
  //   Product 클릭 → 단일 제품 focus(그 제품의 데이터소스만).
  if (String(id).startsWith("ds:")) {
    const sc = id.slice(3);
    adminState.metadata.scopeKey = sc;
    const selEl = document.getElementById("metadataScopeSelect");
    if (selEl) { try { selEl.value = sc; } catch (_) {} }   // 드롭다운 동기화(datasource 옵션 존재 시)
    _metaGraphLoadRoots();
    return;
  }
  if (String(id).startsWith("product:")) {
    adminState.metadata.scopeKey = id;
    _metaGraphLoadProducts(id);
    return;
  }
  const now = (window.performance && performance.now) ? performance.now() : Date.now();
  const isDbl = (_metaGraph._lastClickId === id && (now - (_metaGraph._lastClickAt || 0)) < 320);
  _metaGraph._lastClickId = id; _metaGraph._lastClickAt = now;
  if (isDbl) {
    _metaGraph._lastClickId = null;
    if (_metaGraph._clickTimer) { clearTimeout(_metaGraph._clickTimer); _metaGraph._clickTimer = null; }
    _metaGraphExpand(id);
    return;
  }
  const n = _metaGraph.nodes.get(id);
  _metaGraphShowDetail(id);
  if (n && n.label === "Table") {
    if (_metaGraph._clickTimer) clearTimeout(_metaGraph._clickTimer);
    _metaGraph._clickTimer = setTimeout(() => {
      _metaGraph._clickTimer = null;
      if (!_metaTableHasCols(id)) _metaGraphToggleColumns(id);   // 접힌 테이블만 펼침(펼쳐졌으면 no-op) — hasCols 단일소스
    }, 340);   // 더블클릭 창(320ms) 초과로 설정 — 빠른 더블클릭이 컬럼펼침+이웃확장 동시발동하는 것 방지(review MINOR-1)
  }
  // graph-navfilter(§54⑤): 루틴 단일클릭 = 파라미터 수직 펼침(테이블 컬럼 펼침과 동형 340ms 타이머).
  //   params 는 모델에 이미 있어 fetch 없는 동기 토글 — 더블클릭(이웃확장)은 기존 경로 그대로.
  //   terms 클러스터(flat-scope)는 방출 게이트와 짝 맞춰 미지원(무효 토글 방지).
  if (n && n.label === "Routine" && _metaSchemaComboOf(n) !== _META_TERMS_COMBO) {
    if (_metaGraph._clickTimer) clearTimeout(_metaGraph._clickTimer);
    _metaGraph._clickTimer = setTimeout(() => {
      _metaGraph._clickTimer = null;
      if (!_metaGraph.routineExpanded.has(id) && _metaRoutineParamList(n).length) {
        _metaGraph.routineExpanded.add(id);
        _metaG6Apply(false);
      }
    }, 340);
  }
}


export { _META_GRAPH_COLOR, _META_LABEL_KO, _metaCatParent, _metaG6Apply, _metaGraphAnimateFocus, _metaGraphClearHoverHighlight, _metaGraphFitClamped, _metaGraphHoverPan, _metaGraphHoverPanCancel, _metaGraphLoadRoots, _metaGraphResetModel, _metaGraphSetHoverHighlight, _metaGraphStatus, _metaRenderedAncestorFor, _metaRenderedIdFor, _metaRoutineIcon, _metaRoutineKo, _metaRoutineParamList, _metaShowGraph };
