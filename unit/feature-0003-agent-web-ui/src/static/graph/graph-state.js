// ITEM-09 batch3 — graph.js L7~L168 pure move: 그래프 상태(_metaGraph)·결정론적 배치 상수.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { _metaCatParent } from "./graph-core.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)

// ── feature-0016: 메타데이터 지식그래프 뷰 (AntV G6 v5 + 투영 API) ─────────────────
//   렌더링 엔진: Cytoscape(WebGL) → AntV G6 v5(Canvas). 근거·설계·검증은
//   unit/feature-0016-metadata-graph/g6-migration/BLUEPRINT.md + DECISIONS ADR-004.
//   구버전 대비 해소: ①클릭접힘 ②위치점프 ③줌 동기화지연(HTML오버레이 제거) ④클러스터 뒤섞임
//   ⑤테두리 왜곡(WebGL 텍스처) — 전부 구조적 해소 + 점선 엣지 복원.
//   아키텍처: JS 모델(_metaGraph.nodes/edges/expanded/…) → _metaG6Build() 로 위치 포함
//   전체 G6 데이터 재구성 → graph.setData()+draw()(증분 add/translate 미사용 — 결정론·안정).
const _metaGraph = {
  graph: null,            // G6 Graph 인스턴스
  bound: false,
  lastQuery: "",
  lastDetailKey: null,
  activeRunId: null,
  _analyzePending: new Set(),  // graphux7(#4): AI 능동 분석 POST in-flight 중인 node key 집합 — 연타 동시 POST(중복 큐잉) 차단(노드별 독립).
  introspected: null,     // Set: information_schema 즉석조회한 테이블 key
  mode: "roots",          // "roots"|"search"|"neighbor" (현재는 전부 결정론 grid)
  nodes: new Map(),       // key -> {key,label,name,fqn,description,source,ordinal,score,rel,cardinality,edge_source}
  edges: new Map(),       // id  -> {id,source,target,type,status,edge_source,weight}
  expanded: new Set(),    // 컬럼 펼친 Table key
  analyzed: new Set(),    // AI 분석 완료 key(보라 마커)
  running: new Set(),     // AI 분석 중 key(주황 마커)
  roles: new Map(),       // node-role-viz: 분석 완료 Table key -> 역할 분류(_META_ROLE 키). 칩 색·아이콘 표식 소스.
  selected: null,         // 선택 강조 key
  // graph-initview: 스키마-우선 진입 상태.
  schemaExpanded: new Set(),  // 테이블을 펼친 Schema key(roots 진입은 스키마 카드만)
  schemaLoaded: new Set(),    // per-schema lazy 로드 완료(정식 schema_tables 응답+테이블>0 시만 — 재펼침 무-refetch)
  schemaLoading: new Set(),   // in-flight per-schema fetch(카드 연타 이중 fetch 차단)
  schemaTruncated: new Set(), // schema_tables 가 cap 절단을 보고한 Schema key
  firstElementId: null,       // 자연정렬 첫 요소 id(줌 클램프 시 시선 앵커, 카드는 SC:)
  renderedIds: null,          // 마지막 build 가 렌더한 요소 id 집합 — 미렌더 모델키 setElementState 차단
  schemaTotals: null,         // graph-initview: scope 별 스키마→전체 테이블 수(roots mode=schemas 에서 캐시). search 리셋에도 보존(카드 badge 전체 수 소스).
  searchMatch: null,          // 검색 필터 뷰: schemaKey -> Set(매칭 테이블 key). 카드 badge = 매칭/전체.
  searchMatchTables: null,    // 검색 매칭 테이블 key Set(펼침 시 강조).
  searchMatchNodes: null,     // feature-0016 §45: 검색 직접 매칭 노드 key Set(테이블/컬럼/용어) — 'match' 상태 soft glow 대상(너비 증가 대체).
  searchCapped: false,        // 검색 결과가 cap(_META_SEARCH_CAP) 도달 → 매칭 카운트는 부분값(badge 에 '+' 표기).
  // graph-perf-bg: 성능 인덱스·논블로킹 상태.
  colsByTable: new Map(), // Table key -> 펼쳐진 Column 개수(O(1) _metaTableHasCols 단일소스 — 매 클릭 전노드 스캔 제거).
  _opSeq: 0,              // 펼침/확장 조작 시퀀스 토큰. await(fetch·yield) 경계마다 대조해 stale 렌더 폐기.
  _stateCache: new Map(), // key -> 마지막 적용된 state signature. _metaGraphRefreshStates 가 변화분만 setElementState.
  _busyKeys: new Map(),   // graph-perf-bg fix: key -> busy 를 세운 _opSeq(소유권). refreshStates 가 busy 를 보존·복원하고, 같은 key 재트리거 시 신 op busy 를 stale op 가 지우지 않게 한다.
  tableDeps: new Map(),   // graph-drag(REQ ②): Table key -> [종속 UI 노드 id](접기 "X:" ctl + 컬럼 노드). 매 _metaG6Build 재구성. 테이블 드래그 시 함께 이동.
  _drag: null,            // graph-drag(REQ ②): 진행 중 테이블 드래그 상태 {id, offs:[{id,ox,oy}]}(종속별 테이블 대비 월드 오프셋). null=비활성.
  _dragZBoosted: new Set(),   // graph-zorder h2(리뷰 MINOR): 드래그 부스트 중 id — rebuild 의 _metaGraphZAssert 가 canonical 로 회수하지 않게 보호(dragend 복원 시 해제).
  aiPrompt: "",           // graph-funcproc(ADR-017): AI 능동 분석 hover 지침 — 세션 내 보존(상세 재렌더 시 prefill).
  // graph-freeplace: 자유 배치 persistence(ADR-004 결정론 배치가 rebuild 마다 초기화하던 것을 복원 — 사용자 후속 회귀 보고).
  //   clusterOffset: 스키마 클러스터(combo) 단위 사용자 드래그 누적 이동(dx,dy) — build 가 L.x0/L.y0 에 가산해 클러스터
  //     전체(카드·테이블·컬럼·장식)를 coherent 하게 이동시키고 rebuild(펼침/접기) 후에도 유지. combo:dragend 가 누적.
  //   nodePos: 개별 노드(주로 테이블) 사용자 드래그 최종 절대위치 — build place-loop 이 그 노드+종속을 델타 시프트해
  //     유지 + combo auto-fit 리사이즈(#3). node:dragend 가 기록. 둘 다 resetModel(스코프 전환·초기화)에서 clear.
  clusterOffset: new Map(),   // comboId(schema key) -> {dx, dy}
  nodePos: new Map(),         // nodeId -> [x, y] (사용자 확정 절대 위치)
  // group-interact(§50): sim-group(카테고리 그룹 = 유사 속성 그룹, ADR-013) 자유 배치·접기 상호작용.
  //   clusterOffset·nodePos 사이 계층(cluster → group → node)의 offset. GB 박스는 멤버 bbox 에서 파생돼
  //   그룹 이동(groupOffset)·개별 노드 이동(nodePos) 양쪽에 반응형으로 맞춰진다(#3). resetModel 에서 clear.
  groupOffset: new Map(),     // groupKey -> {dx, dy} (sim-group 단위 드래그 누적 — clusterOffset 의 그룹판)
  groupCollapsed: new Set(),  // 접힌 sim-group key(멤버 미방출·헤더만)
  groupMembers: new Map(),    // groupKey -> [멤버 테이블 id] (드래그 시 묶음 이동 — 매 build 재구성, 펼친 그룹만)
  groupOf: new Map(),         // 테이블 id -> groupKey (멤버 이동 시 GB 박스 반응형 rebuild 판정 — 매 build 재구성)
  // feature-0016 §49(요구②): 배치 순서 안정화 — 이웃확장/펼침 rebuild 시 re-seriation 으로 노드가 그리드를 점프하지
  //   않도록 직전 클러스터·테이블 순서를 보존하고 신규만 seriated 순서로 append. 드래그(nodePos/clusterOffset)와 직교.
  //   resetModel(스코프 전환·초기화)에서 clear → fresh load 는 순수 seriation.
  clusterOrder: [],           // 안정화된 클러스터(comboId) 순서
  tableOrder: new Map(),      // comboId -> 안정화된 테이블/루틴 key 순서(flat masonry 경로)
  groupOrder: new Map(),      // feature-0016 §49(R1): schemaId -> 안정화된 simgroups 그룹 순서
  groupTableOrder: new Map(), // feature-0016 §49(R1): groupKey -> 안정화된 그룹내 테이블 key 순서
  _comboDragStart: null,      // combo:dragstart 시 {id, x, y}(중심) — dragend 델타 산출용
  // graphux7(#1) + graph-navfilter(§54①): 상세 패널 방문 이력(뒤로/앞으로). datasource 컨텍스트
  //   전환(loadRoots/Products) 시 _metaGraphHistoryReset 로 초기화. _histNav=네비 중(중복 push 억제).
  detailHist: [],             // 방문 스택 — {v:"node"|"cluster"|"rel", k:key} (오래된 앞 → 최근 뒤)
  detailHistIdx: -1,          // 현재 위치 인덱스(-1=비어 있음)
  _histNav: false,            // 뒤로/앞으로 네비게이션 진행 중 플래그
  // graph-navfilter(§54②): 노드 종류 표시 필터 — "edges"|"function"|"procedure" 를 빌드 입력에서
  //   제외(스타일 숨김 아님 — masonry/simgroups/shelf-pack 이 자동 재배치). 테이블·컬럼은 항상 표시.
  //   scope-독립 preference 라 resetModel 에서 clear 하지 않는다(localStorage 영속).
  hiddenKinds: new Set(),
  // graph-navfilter(§54③): 검색이 순수 추가한 노드 key(카드·terms) — 재검색/클리어 시 사용자
  //   미접촉(pristine)만 회수해 펼침·배치·확장은 보존.
  searchAdded: new Set(),
  // §54③ 패널 MAJOR: 검색 진입 직전의 base 컨텍스트 {mode, focusName} — products/중심보기 위에서
  //   검색→클리어 시 원 화면(제품 개요/중심 보기 칩)으로 정확히 복귀·복원하기 위함.
  _searchBase: null,
  _focusName: null,           // 중심 보기 대상 이름(FocusChip 단일소스 미러 — DOM 파싱 회피)
  // graph-navfilter(§54⑤): 파라미터를 펼친 Routine key — 컬럼 펼침(expanded)의 루틴 판.
  routineExpanded: new Set(),
  // graph-category(§55 A, REQ-20260706 ①): 스키마(DB)별 제품 매핑 — 스키마 클러스터를 제품 카테고리
  //   밴드(CAT:/CATH:/CATX:)로 묶는 데이터 원천. key=스키마명 lowercase, val=[{id,name,sort}].
  //   schemaTotals 와 같은 scope 캐시 — resetModel 보존, loadRoots 가 재구축(응답 schema_products).
  schemaProducts: new Map(),
  catOrder: [],               // §49 동형: 카테고리(catKey) 순서 안정화
  catCollapsed: new Set(),    // 접힌 카테고리 catKey(멤버 클러스터 미방출·헤더 밴드만)
  catMembers: new Map(),      // catKey -> [멤버 클러스터(comboId)] — 매 build 재구성(카테고리 드래그 소비)
  catLabelOf: new Map(),      // catKey -> 표시 라벨 — 매 build 재구성(상세·헤더)
};

// ── 결정론적 배치 상수(스키마 클러스터 grid·테이블 스택·컬럼 세로열) ──
const _METtype = "rect";
const _METLAY = { COLS: 3, SW: 300, GAPX: 48, GAPY: 52, PADT: 34, PADX: 16, TROW: 34, CROW: 21, CIND: 26, TGAP: 12, TW: 150,
  CARDW: 210, CARDH: 44 };   // graph-initview: 접힌 스키마 카드 치수
const _META_MIN_READ_ZOOM = 0.55;   // graph-initview(A1): 초기 fit 이 이 배율 밑이면 판독 불가 — 클램프
// §57(declutter): 중간 줌 LOD — 줌이 이 임계 밑이고 모델 엣지가 _MIN 개를 넘으면 무상태(FK)·비크로스
//   단건 선을 축약(의미 신호만 유지). 임계 1점 왕복 rebuild 방지는 밴드 전이+디바운스(_lodBand).
const _META_EDGE_LOD_ZOOM = 0.35;
const _META_EDGE_LOD_MIN = 120;
// col-lod(§61): 노드-레벨 LOD — 개요 줌(판독 불가 배율) + 대형 모델(펼친 컬럼 多)에서 컬럼 circle·루틴
//   파라미터·per-table 접기 ctl 의 **방출을 억제**한다(테이블/스키마 칩·관계선은 유지). draw 지배항은
//   테이블당 최대 500 Column circle 이라(INV-COLUMN-CAP-DRAW), 개요에서 이들을 방출하지 않으면 setData
//   diff·draw 요소 수가 급감한다. 결정론 보존: realH(공간 예약)는 **불변** → 테이블 좌표·combo extent 가
//   band-invariant(reflow 0). combo 는 자식 auto-fit 이므로, 억제해도 테이블(realH 반영 위치)이 combo
//   범위를 정의해 카드 크기 불변. 억제 시 테이블 라벨에 '▤N' 컬럼수 배지로 정보 손실 방지. 컬럼 끝점 엣지는
//   renderEndpoint 가 소속 테이블로 자동 승격(접힌 스키마와 동일 경로). 밴드 전이는 _lodBand 300ms 디바운스.
const _META_COL_LOD_ZOOM = 0.5;   // 이 배율 밑 + 아래 임계 초과 컬럼이면 억제(엣지 LOD 0.35 보다 넓은 밴드)
const _META_COL_LOD_MIN = 200;    // 전체 펼친 컬럼 수가 이 미만이면 draw 저렴 — 억제 안 함(정보 손실만 유발 방지)
// agg-lod(§63): 극단 줌아웃(개별 노드 식별이 무의미한 배율)에서 **확장 클러스터를 단일 집계 카드로 강등**한다.
//   수천 개 테이블/컬럼 노드 방출을 클러스터 수(~수십)로 축약 → draw 요소 급감(병목 = setData/draw 요소 수).
//   레이아웃 슬롯은 그대로 유지(집계 카드를 슬롯 좌상단에 배치)해 **reflow 0** — 확대하면 다시 펼쳐진다.
//   카드(SC:id)↔combo(id)는 서로 다른 id 라 setData 가 add/remove 로 처리(노드↔combo 타입전환·자식유실 회피,
//   기존 카드 게이팅과 동일 계약, admin.js:4961 주석). 밴드 전이는 _lodBand 300ms 디바운스.
const _META_AGG_ZOOM = 0.15;      // 이 배율 밑 + 대형 모델이면 클러스터 집계(개별 노드가 사실상 점 — 식별 무의미).
                                  //   보수적 값(정말 zoom-out 됐을 때만). 필요 시 상향해 더 이르게 집계 가능.
const _META_AGG_MIN = 60;         // 전체 모델 노드 수가 이 미만이면 집계 안 함(소형 모델은 그대로 열람)
// viewport-cull(§65): 줌인 대형모델에서 **화면(뷰포트+마진) 밖 테이블의 컬럼/파라미터 방출을 억제**한다 —
//   병목=draw 방출 요소 수라, 보이지 않는 컬럼을 안 그리면 줌인 클릭/팬이 가벼워진다. 뷰포트를 덮는 개요에선
//   모든 테이블이 in-view 라 자동 무효(집계·col-LOD 가 담당). combo-safe: 테이블 칩은 항상 유지 → combo extent 불변.
const _META_CULL_MIN = 400;       // 모델 노드 수가 이 미만이면 컬링 안 함(작은 모델은 전체가 화면에 근접)
const _META_CULL_MARGIN = 0.3;    // 뷰포트 밖 여유(뷰포트 크기 배수) — 팬 시 컬럼이 경계에서 갑자기 튀지 않게.
//   graph-layoutmemo(§73): 0.6→0.3 — 고배율 줌인에서 방출 영역이 과대(margin 0.6 이면 방출면적=뷰포트×4.84,
//   zoom 2.5 에서 337 방출)해 setData+draw 를 키웠다. 메모이즈로 re-emit 의 layout 비용이 사라져 더 tight 한
//   마진(방출면적 ×2.25)이 감당 가능 — 방출 수↓ = draw↓. 팬 재-emit 은 §65 debounce 로 경계 pop 흡수.
// §57.9: 상대 하이라이트 침강 opacity — base style bake(_metaBakeBaseOpacity)와 dimmed G6 상태가 공유.
const _META_DIM_OPACITY = 0.38;
// graph-zorder(§52): 캔버스 요소 의미 z-스케일 — **단일 소스**. @antv/g 는 (zIndex → 삽입순 renderOrder)로
//   페인팅·hit-test 하므로, 전 요소에 zIndex 를 명시해 setData diff 의 생성 순서·드래그 이력(내장
//   drag-element 의 frontElement 영구 승격)이 페인팅 순서를 결정하지 못하게 한다. 의미 계층:
//   클러스터 배경(COMBO) < 그룹 배경(GROUP_BG) < 관계선(EDGE) < 컬럼(COLUMN) < 칩·카드(NODE)
//   < 그룹 헤더(GROUP_HD, §50 드래그 핸들 hit-test) < 컨트롤(CTL, 항상 클릭 가능). DRAG_BOOST 는
//   드래그 중 임시 부스트 오프셋(canonical+1000) — dragend 에 canonical 복원(_metaDragZRestore).
//   흐름 내 per-table "X:" ctl 은 NODE 밴드(허위 소속 어포던스 방지, 패널 ux MINOR) — 자기 칩과 비겹침이라
//   클릭성 손실 없음. 코너 앵커 컨트롤(GX/XS)만 CTL(항상 클릭 가능).
//   EDGE 층 내부는 신뢰 강도 소수 오프셋(trusted+0.2 > candidate/교차DB+0.1)으로 tie 분해(_metaEdgeStyleFor).
// graph-category(§55 A): CAT_BG(-1) = 제품 카테고리 밴드 배경 — 클러스터 배경(COMBO 0) **아래**.
//   combo 내부 hit-test 는 combo 가 갖고, 밴드 여백·헤더(CATH, GROUP_HD 밴드)가 카테고리 상호작용 표면.
const _METZ = { CAT_BG: -1, COMBO: 0, GROUP_BG: 1, EDGE: 2, COLUMN: 3, NODE: 4, GROUP_HD: 5, CTL: 6, DRAG_BOOST: 1000 };
const _META_SEARCH_CAP = 50;        // search-badge: 백엔드 search_nodes 기본 limit(50) 미러 — 도달 시 매칭 카운트 부분값(badge '+')
const _META_TERMS_COMBO = "__terms__";   // GlossaryTerm/misc 를 담는 합성 클러스터

// node key(`scope:fqn`) → 소속 스키마 클러스터 combo id. Table/Column 은 스키마, 그 외는 terms 클러스터.
function _metaSchemaComboOf(n) {
  if (!n) return _META_TERMS_COMBO;
  if (n.label === "Schema") return n.key;
  if (n.label === "Table" || n.label === "Column" || n.label === "Routine") {
    const sc = _metaCatParent(n.key, n.fqn);
    if (sc) return sc;
  }
  return _META_TERMS_COMBO;
}
function _metaComboName(id) {
  if (id === _META_TERMS_COMBO) return "용어·기타";
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(i + 1) : id;
}
const _metaNatSort = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });


export { _META_AGG_ZOOM, _META_COL_LOD_MIN, _META_COL_LOD_ZOOM, _META_CULL_MARGIN, _META_CULL_MIN, _META_DIM_OPACITY, _META_EDGE_LOD_MIN, _META_EDGE_LOD_ZOOM, _META_MIN_READ_ZOOM, _META_SEARCH_CAP, _META_TERMS_COMBO, _METLAY, _METZ, _METtype, _metaComboName, _metaGraph, _metaNatSort, _metaSchemaComboOf };
