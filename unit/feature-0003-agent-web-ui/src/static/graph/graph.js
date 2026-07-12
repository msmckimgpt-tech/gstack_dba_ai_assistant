// feature-0003 ITEM-09 — 메타데이터 지식그래프 뷰 (admin.js 에서 분리, byte-준동치 pure move).
// admin.js ↔ graph.js 순환 import(ES live-binding): core 는 함수 호출 시점 사용이라 안전.
// G6 는 UMD 전역(window.G6) — module scope 에서 bare G6 참조를 위해 상단 bridge.
import { adminState, apiFetch, can, showToast, _metaSubmitForm } from "../admin.js";
const G6 = window.G6;

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

// ── node-role-viz: AI 능동 분석 완료 테이블의 역할 분류 → 시각 표식(칩 색 + 아이콘 + 범례) ──
//   분류체계는 BE(node_analysis.NODE_ROLES)와 1:1. 팔레트 = Okabe-Ito 8색(색약 안전 표준) —
//   색(범주 최강 채널) + 아이콘(중복 인코딩, 색약·흑백 대응) + 범례/상세패널 라벨 3중 인코딩.
//   dark=true 는 밝은 색이라 흰 라벨 대비가 부족한 항목 — 라벨을 어두운 글자로 전환.
const _META_ROLE = {
  // dark 배정(적대 패널 U3): 12px bold 흰 라벨 대비가 부족한 밝은/중간 색은 어두운 라벨(#161b22) —
  //   account 2.2 / log 1.9 / stats 1.1 / mapping 3.1 / transaction 3.4 (흰 라벨 대비, 전부 4.5 미달) → dark.
  // desc: 범례 hover 툴팁·클러스터 상세 접두사 툴팁의 단일 소스. BE node_analysis.NODE_ROLES 휴리스틱과 정합.
  master:      { ko: "기준·정의", icon: "📘", color: "#0072B2", dark: false, desc: "다른 테이블이 참조하는 기준·마스터·코드성 데이터 (코드표·정의·사전 등)" },
  account:     { ko: "계정·유저", icon: "👤", color: "#56B4E9", dark: true,  desc: "사용자·계정·회원 등 주체 정보 (캐릭터·플레이어 포함)" },
  transaction: { ko: "거래·행위", icon: "💳", color: "#009E73", dark: true,  desc: "결제·주문·구매·보상 등 거래·행위 이벤트 (핵심 비즈니스 팩트)" },
  log:         { ko: "로그·이력", icon: "📜", color: "#E69F00", dark: true,  desc: "시간순 로그·이력·감사 기록 (주로 append)" },
  mapping:     { ko: "매핑·연결", icon: "🔗", color: "#CC79A7", dark: true,  desc: "두 엔티티를 잇는 N:M 매핑·연결(교차 참조) 테이블" },
  config:      { ko: "설정",     icon: "⚙️", color: "#D55E00", dark: false, desc: "시스템·기능 설정·옵션·파라미터·환경값" },
  stats:       { ko: "집계·통계", icon: "📊", color: "#F0E442", dark: true,  desc: "집계·통계·랭킹·스냅샷 등 파생·요약 데이터" },
  etc:         { ko: "기타",     icon: "📦", color: "#6e7681", dark: false, desc: "위 분류에 속하지 않는 테이블" },   // ◽ 는 회색 칩 위 tofu 처럼 비가시(패널 U4) → 📦
};
// role-cluster-prefix: 역할 칩 HTML 조립(그래프 칩·상세 배지와 동일 색/아이콘). small=상세 테이블 목록 접두사(고정 폭).
function _metaRoleChipHTML(role, esc, small) {
  const rd = _META_ROLE[role]; if (!rd) return "";
  const tip = esc(`${rd.icon} ${rd.ko} — ${rd.desc}`);
  return `<span class="amgr-role-chip${small ? " amgr-role-chip-sm" : ""}" style="background:${rd.color}${rd.dark ? ";color:#161b22" : ""}" title="${tip}">${rd.icon}</span>`;
}
// role-cluster-prefix: 정적 역할 범례 <li data-role> 에 hover 툴팁(desc) 주입 — _META_ROLE 단일 소스. 그래프 뷰 진입 시 1회.
function _metaRoleLegendTips() {
  document.querySelectorAll(".admin-meta-graph-rolelegend-list li[data-role]").forEach((li) => {
    const rd = _META_ROLE[li.getAttribute("data-role")];
    if (rd) li.title = `${rd.icon} ${rd.ko} — ${rd.desc}`;
  });
}
// graphux7(#3): 그래프 범례 3-탭(노드 종류·관계·AI 상태·테이블 역할) 전환. 그래프 뷰 진입 시 1회 바인딩(멱등).
//   탭 버튼 → is-active + 대응 패널 표시(hidden 토글). ←/→ 로 탭 이동(roving tabindex 접근).
function _metaGraphBindLegendTabs() {
  const wrap = document.getElementById("metadataGraphLegendTabs");
  if (!wrap || wrap.dataset.bound === "1") return;
  wrap.dataset.bound = "1";
  const tabs = Array.prototype.slice.call(wrap.querySelectorAll(".amg-legend-tab"));
  const panels = Array.prototype.slice.call(wrap.querySelectorAll(".amg-legend-panel"));
  const activate = (name) => {
    tabs.forEach((t) => {
      const on = t.getAttribute("data-legend-tab") === name;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((p) => {
      const on = p.getAttribute("data-legend-panel") === name;
      p.classList.toggle("is-active", on);
      if (on) p.removeAttribute("hidden"); else p.setAttribute("hidden", "");
    });
  };
  tabs.forEach((t) => {
    t.addEventListener("click", () => activate(t.getAttribute("data-legend-tab")));
    t.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      const i = tabs.indexOf(t);
      const n = ev.key === "ArrowRight" ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
      const nt = tabs[n];
      if (!nt) return;
      activate(nt.getAttribute("data-legend-tab"));
      try { nt.focus(); } catch (_) {}
    });
  });
}
function _metaRoleOf(key) {
  const r = _metaGraph.roles.get(key);
  return (r && _META_ROLE[r]) ? r : null;
}

// G6 per-element inline style helpers (설정 매퍼 금지 — undefined→To() 크래시 회피, BLUEPRINT §3).
// graph-zorder(§52): 렌더 요소 id → canonical(의미) zIndex. build bake·dragend 복원의 공용 해석기.
//   장식 prefix(GB/GH/GX/X/XS/SC)가 우선하고, 그 외는 모델 label(Column/Schema)로 판정.
//   combo id == Schema 모델 key(펼침 시) — COMBO 층. 미상은 칩과 동급(NODE).
function _metaZFor(id) {
  const s = String(id);
  // graph-category(§55 A, 패널 BLOCKING fix): CAT 밴드 3종 — 누락 시 기본 NODE(4) 로 해석돼
  //   _metaGraphZAssert(매 draw 후 canonical 재-assert)가 배경을 최상층으로 승격, 밴드가 내부
  //   클러스터·노드를 반투명으로 덮고 hit-test 를 가로챈다. bake(-1/5/6)와 1:1 로 고정.
  if (s.startsWith("CATX:")) return _METZ.CTL;
  if (s.startsWith("CATH:")) return _METZ.GROUP_HD;
  if (s.startsWith("CAT:")) return _METZ.CAT_BG;
  if (s.startsWith("GB:")) return _METZ.GROUP_BG;
  if (s.startsWith("GH:")) return _METZ.GROUP_HD;
  if (s.startsWith("GX:") || s.startsWith("XS:")) return _METZ.CTL;
  if (s.startsWith("XR:")) return _METZ.NODE;   // graph-navfilter(§54⑤): 루틴 파라미터 접기 ctl — X: 와 동일 밴드(bake 1:1)
  if (s.startsWith("RP:")) return _METZ.COLUMN; // graph-navfilter(§54⑤): 루틴 파라미터 행 — 컬럼과 동일 밴드(bake 1:1)
  if (s.startsWith("X:")) return _METZ.NODE;   // 패널 ux MINOR: 흐름 내 per-table ctl 은 칩과 같은 밴드(bake 와 1:1)
  if (s.startsWith("SC:")) return _METZ.NODE;
  if (s === _META_TERMS_COMBO) return _METZ.COMBO;   // 용어·기타 클러스터 combo — 모델 노드 없음(합성 id)
  const n = _metaGraph.nodes.get(id);
  if (n && n.label === "Column") return _METZ.COLUMN;
  if (n && n.label === "Schema") return _METZ.COMBO;
  return _METZ.NODE;
}
// graph-zorder(§52): 드래그 중 대상+종속을 canonical+DRAG_BOOST 로 결정론 승격. 내장 drag-element 는
//   grabbed 만 frontElement(전역 max+1, **영구**)로 올려 종속(컬럼·ctl)과 계층이 찢어지고 드래그
//   이력이 z-order 로 굳는다 — 부스트가 그 값을 덮고(호출이 늦어 우선), dragend 가 canonical 복원.
function _metaDragZBoost(ids) { _metaDragZApply(ids, _METZ.DRAG_BOOST); }
// dragend 복원 — rebuild(_metaG6Apply)도 canonical 을 재-bake 하므로 이중 안전망(자가 치유).
function _metaDragZRestore(ids) { _metaDragZApply(ids, 0); }
function _metaDragZApply(ids, boost) {
  const g = _metaGraph.graph;
  if (!g || !ids || !ids.length) return;
  // setElementZIndex 는 미존재 id 1개로도 전체 reject — 마지막 build 의 renderedIds 로 필터
  //   (드래그 중 rebuild 로 요소가 제거된 edge case 에 나머지 복원까지 무산되지 않게).
  const r = _metaGraph.renderedIds;
  const m = {};
  let n = 0;
  ids.forEach((id) => {
    if (!r || r.has(id)) {
      m[id] = _metaZFor(id) + boost;
      n += 1;
      // h2(리뷰 MINOR): 부스트 중 id 를 기록 — 백그라운드 rebuild(_metaGraphZAssert)가 드래그 도중
      //   canonical 로 회수하지 않게 보호. 복원(boost=0) 시 해제.
      if (boost > 0) _metaGraph._dragZBoosted.add(id); else _metaGraph._dragZBoosted.delete(id);
    }
  });
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}
// graph-zorder(§52): 렌더 요소 id → 소속 클러스터(combo id). 장식 prefix 는 파싱, 그 외는 모델 기반.
function _metaComboOwnerOf(id) {
  const s = String(id);
  if (s.startsWith("SC:") || s.startsWith("XS:")) return s.slice(3);
  if (s.startsWith("GB:") || s.startsWith("GH:") || s.startsWith("GX:")) {
    const gk = s.slice(3), sep = gk.indexOf("\u0001");
    return sep >= 0 ? gk.slice(0, sep) : null;
  }
  // graph-navfilter(§54⑤): 루틴 파라미터 합성 id — 소속 루틴의 스키마 combo 로 귀속(X: 관례와 동형).
  if (s.startsWith("XR:")) {
    const n = _metaGraph.nodes.get(s.slice(3));
    return n ? _metaSchemaComboOf(n) : null;
  }
  if (s.startsWith("RP:")) {
    const n = _metaGraph.nodes.get(s.slice(3).replace(/:\d+$/, ""));
    return n ? _metaSchemaComboOf(n) : null;
  }
  if (s.startsWith("X:")) {
    const n = _metaGraph.nodes.get(s.slice(2));
    return n ? _metaSchemaComboOf(n) : null;
  }
  const n = _metaGraph.nodes.get(s);
  return n ? _metaSchemaComboOf(n) : null;
}
// graph-zorder(§52): combo(클러스터)의 렌더된 하위 요소 id 전부 — 내장 frontElement 가 combo 드래그
//   시 하위 전체를 델타 승격하므로, dragend canonical 복원 대상을 같은 범위로 재구성한다.
function _metaComboMemberIds(comboId) {
  const out = [];
  const r = _metaGraph.renderedIds;
  if (!r || !comboId) return out;
  r.forEach((id) => {
    if (String(id) === comboId) return;
    if (_metaComboOwnerOf(id) === comboId) out.push(id);
  });
  return out;
}
// graph-zorder(§52, 패널 ux BLOCKING): 엣지 datum → canonical zIndex — _metaEdgeStyleFor/_metaRoutineEdgeStyle
//   의 bake 규칙과 1:1 (EDGE + trusted 0.2 / candidate·교차DB 0.1 / 그 외 0, ROUTINE_USES·USES = EDGE).
function _metaEdgeZFor(ed) {
  const d = (ed && ed.data) || {};
  if (d.label === "ROUTINE_USES") return _METZ.EDGE;
  if (d.cross_ds) return _METZ.EDGE + 0.1;
  return _METZ.EDGE + (d.status === "trusted" ? 0.2 : (d.status === "candidate" ? 0.1 : 0));
}
// graph-zorder(§52, 패널 ux BLOCKING): 내장 frontElement 는 combo 드래그 시 **내부 엣지**도 델타 승격한다
//   (번들 실측: getRelatedEdgesData(...).internal). 노드+콤보만 복원하면 관계선이 칩(4)·헤더(5)·컨트롤(6)
//   위로 영구 잔존(반복 드래그 시 단조 증가 — 콤보 드래그는 rebuild 를 유발하지 않아 다음 rebuild 까지
//   지속) — combo 소속 끝점을 가진 엣지 전부를 canonical 로 복원한다(내장의 internal 범위 상위집합 —
//   비승격분 재-세팅은 no-op 라 무해).
function _metaComboEdgesRestore(comboId) {
  const g = _metaGraph.graph;
  if (!g || !comboId) return;
  let eds;
  try { eds = g.getEdgeData(); } catch (_) { eds = null; }
  if (!eds || !eds.length) return;
  const m = {};
  let n = 0;
  eds.forEach((ed) => {
    if (!ed || ed.id == null) return;
    if (_metaComboOwnerOf(ed.source) === comboId || _metaComboOwnerOf(ed.target) === comboId) { m[ed.id] = _metaEdgeZFor(ed); n += 1; }
  });
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}
// graph-zorder h2(§52.4, PB-0008 라이브 실측 적발): G6 v5 computeZIndex 는 setData diff 의 **update** 에서
//   datum 에 `combo` 키가 있으면(combo-자식 노드 datum 은 항상 combo: 포함 — 접힌 카드 SC:·products
//   빌드 노드는 combo 키가 없어 애초 평탄화 비대상) 제공된 style.zIndex 를 무시하고 comboZ+1(=1) 로
//   재산정한다 — add 는 명시 zIndex 존중(skip). 즉 첫 렌더는 canonical, **기존 요소가 업데이트되는
//   rebuild 마다 combo-자식 전부 z1 평탄화**(실측: 그룹 멤버 드래그 rebuild 후 칩/컬럼/ctl=1). 엣지는
//   명시 zIndex 정의 시 항상 skip 이라 무영향. setElementZIndex 경로는 datum 에 combo 키가 없어 재산정을
//   우회(sticky)하므로, 매 rebuild(draw) 직후 canonical 과 어긋난 요소만 골라 일괄 re-assert 한다.
function _metaGraphZAssert() {
  const g = _metaGraph.graph;
  if (!g || !_metaGraph.renderedIds) return;
  const m = {};
  let n = 0;
  _metaGraph.renderedIds.forEach((id) => {
    if (_metaGraph._dragZBoosted.has(id)) return;   // h2(리뷰 MINOR): 드래그 부스트 중 — 회수 금지(dragend 가 복원)
    let z; try { z = g.getElementZIndex(id); } catch (_) { return; }
    const want = _metaZFor(id);
    if (z !== want) { m[id] = want; n += 1; }
  });
  try {
    g.getEdgeData().forEach((ed) => {
      if (!ed || ed.id == null) return;
      let z; try { z = g.getElementZIndex(ed.id); } catch (_) { return; }
      const want = _metaEdgeZFor(ed);
      if (z !== want) { m[ed.id] = want; n += 1; }
    });
  } catch (_) {}
  if (!n) return;
  try { Promise.resolve(g.setElementZIndex(m)).catch(() => {}); } catch (_) {}
}

function _metaTableStyle(x, y, rel, role) {
  // feature-0016 §45: 검색 매칭 표현을 '너비 증가'에서 'match 상태 soft glow'로 이관 — 노드 폭은 rel 과 무관하게 고정한다
  //   (가변 폭은 setData 재packing 을 유발하고 검색 가시성도 떨어졌다). rel 인자는 호출부 호환 위해 유지(폭 계산엔 미사용).
  const w = _METLAY.TW;
  // node-role-viz: 분석 완료 + 역할 분류가 있으면 칩 색 = 역할색(미분석은 기존 teal 유지 — 색 자체가 "분석됨+역할" 신호).
  const rd = role ? _META_ROLE[role] : null;
  return { x, y, size: [w, 24], radius: 6, fill: rd ? rd.color : _META_GRAPH_COLOR.Table, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    // feature-0016 §45: 폭이 rel 무관 고정(TW=150)이 되며 라벨이 박스를 넘치지 않도록 labelMaxWidth 를 박스 안으로 클램프(예전 176 은 rel 부스트로 최대 190 폭일 때 기준).
    labelPlacement: "center", labelFill: rd && rd.dark ? "#161b22" : "#ffffff", labelFontSize: 12, labelFontWeight: 700, labelMaxWidth: _METLAY.TW - 10, cursor: "pointer" };
}
function _metaTermStyle(x, y, rel) {
  // feature-0016 §45: 용어 노드 폭도 rel 무관 고정(검색 매칭은 match 상태 soft glow 로 표시). rel 인자는 호환 유지.
  const w = 130;
  return { x, y, size: [w, 22], radius: 11, fill: _META_GRAPH_COLOR.GlossaryTerm, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    // feature-0016 §45: 폭 고정(130)에 맞춰 라벨을 박스 안으로 클램프(예전 168 은 rel 부스트 폭 기준).
    labelPlacement: "center", labelFill: "#ffffff", labelFontSize: 11, labelFontWeight: 700, labelMaxWidth: 118, cursor: "pointer" };
}
function _metaColStyle(x, y) {
  return { x, y, size: 11, fill: _META_GRAPH_COLOR.Column, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.COLUMN,
    labelPlacement: "right", labelFill: "#161b22", labelFontSize: 10, labelOffsetX: 5, labelMaxWidth: 168, cursor: "pointer" };
}
// graph-funcproc(ADR-016): 함수·프로시저 칩 — 테이블 칩과 같은 자리(클러스터 열)에 서되 보라 + 둥근 모서리로 구분.
function _metaRoutineStyle(x, y, rel) {
  const w = Math.min(190, _METLAY.TW + (typeof rel === "number" ? Math.round(rel * 40) : 0));
  return { x, y, size: [w, 24], radius: 12, fill: _META_GRAPH_COLOR.Routine, stroke: "#ffffff", lineWidth: 1, zIndex: _METZ.NODE,
    labelPlacement: "center", labelFill: "#ffffff", labelFontSize: 11, labelFontWeight: 700, labelMaxWidth: 176, cursor: "pointer" };
}
function _metaCtlStyle(x, y) {
  return { x, y, size: [18, 18], radius: 4, fill: "#ffffff", stroke: "#0a5b66", lineWidth: 1.5, zIndex: _METZ.CTL,
    labelText: "−", labelPlacement: "center", labelFill: "#0a5b66", labelFontSize: 15, labelFontWeight: 700, cursor: "pointer" };
}
// graph-initview: 접힌 스키마 카드(진입 뷰 기본) — 클릭 시 그 스키마의 테이블만 lazy 펼침.
function _metaSchemaCardStyle(x, y) {
  return { x, y, size: [_METLAY.CARDW, _METLAY.CARDH], radius: 10, fill: "#eef0f8",
    stroke: _META_GRAPH_COLOR.Schema, lineWidth: 1.5, zIndex: _METZ.NODE,
    labelPlacement: "center", labelFill: "#2a3567", labelFontSize: 12, labelFontWeight: 700,
    labelMaxWidth: _METLAY.CARDW - 16, cursor: "pointer" };
}
// graph-initview: 스키마 combo 의 "−" 접기 컨트롤(카드로 복귀).
function _metaSchemaCtlStyle(x, y) {
  return { x, y, size: [18, 18], radius: 4, fill: "#ffffff", stroke: _META_GRAPH_COLOR.Schema, lineWidth: 1.5,
    labelText: "−", labelPlacement: "center", labelFill: _META_GRAPH_COLOR.Schema, labelFontSize: 15,
    labelFontWeight: 700, cursor: "pointer", zIndex: _METZ.CTL };
}
function _metaComboStyleFor(isTerms) {
  return { radius: 12, padding: [30, 16, 14, 16], labelPlacement: "top", labelFontWeight: 700, labelFontSize: 13,
    labelFill: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema,
    fill: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema,
    fillOpacity: 0.045, stroke: isTerms ? "#d3b06a" : "#aab3c5", lineWidth: 1, lineDash: [6, 4], collapsedMarker: false,
    zIndex: _METZ.COMBO };   // graph-zorder(§52): 클러스터 배경 = 최하층 — 드래그 frontElement 잔존 승격도 rebuild 재-bake 로 복원
}
function _metaEdgeStyleFor(status, crossDs) {
  // crossds-rel(ADR-019): 교차DB 관계는 상태 무관 별도 클래스 — 마젠타 점선(same-ds candidate 골드 점선과 구분).
  //   프로브 검증 불가라 항상 추정성. trusted 승격돼도 교차DB 임을 시각 유지.
  // graph-zorder(§52, 패널 design MINOR): EDGE 층 내부 tie 를 의미로 분해 — 신뢰 강도가 강한 엣지가
  //   교차점에서 위에 그려지게 소수 오프셋(trusted +0.2 > candidate/교차DB +0.1 > 기본 +0). @antv/g 는
  //   수치 정렬이라 유효. 층 상한(COLUMN=3) 미만 유지.
  if (crossDs) return { stroke: "#a855c7", lineWidth: 1.8, lineDash: [2, 4], endArrow: true, zIndex: _METZ.EDGE + 0.1 };
  const s = { stroke: status === "trusted" ? "#6b4410" : (status === "candidate" ? "#c9a24a" : "#cbd2db"),
    lineWidth: status === "trusted" ? 3 : (status === "candidate" ? 1.8 : 1.4), endArrow: true,
    zIndex: _METZ.EDGE + (status === "trusted" ? 0.2 : (status === "candidate" ? 0.1 : 0)) };
  if (status === "candidate") s.lineDash = [6, 4];   // 실선은 lineDash 키 생략(false 금지 — G6 크래시, BLUEPRINT §3)
  return s;
}
// graph-funcproc(ADR-016): 함수·프로시저 → 테이블 사용 엣지(ROUTINE_USES) — 보라 잔점선(추정 점선과 구분).
//   graph-dataflow: AGE 모델은 항상 Routine(source)→Table(target) 방향이지만, 화살표는 **데이터 흐름**을
//   따른다 — 쓰기(write)=루틴이 테이블로 데이터를 보냄=루틴→테이블(endArrow), 읽기(read)=테이블에서
//   데이터를 읽어옴=테이블→루틴(startArrow, 출발점=루틴 쪽에 화살촉). read·relation_type 미상은 startArrow
//   (테이블→루틴) — 상세 패널 텍스트 라벨 kindKo 기본값 '읽기'와 정합(모순 방지). false 키 미설정(G6 arrow 안전).
function _metaRoutineEdgeStyle(relationType, crossDs) {
  // §57(사용자 검증 지적 ②): 크로스-DB 루틴 참조는 로컬 사용선과 색으로 구분 — REFERENCES 의
  //   교차DB 마젠타(ADR-019)와 동일 색상 어휘를 쓰되 ROUTINE_USES 고유 잔점선([2,3])·화살표 방향은
  //   유지(관계 종류는 dash·방향, 교차 여부는 색 — 직교 인코딩). zIndex 는 _metaEdgeZFor 의
  //   ROUTINE_USES 분기(_METZ.EDGE 고정)와 1:1 이어야 하므로 변경하지 않는다.
  const s = { stroke: crossDs ? "#a855c7" : _META_GRAPH_COLOR.Routine,
    lineWidth: crossDs ? 1.8 : 1.5, lineDash: [2, 3], zIndex: _METZ.EDGE };
  if (relationType === "write") s.endArrow = true;    // 데이터: 루틴 → 테이블(쓰기)
  else s.startArrow = true;                            // read·미상: 테이블 → 루틴(상세 패널 kindKo 기본 '읽기'와 정합)
  return s;
}
// §57(사용자 요구 ①): 접힌 스키마 카드 간 집계 연결선(SCHEMA_REF) — 관계 의미(신뢰/추정/루틴)와
//   구분되는 중립 슬레이트 실선. 굵기는 관계 수 로그 스케일, count 라벨로 규모 노출. 무향 집계라
//   화살표 없음(양 키 생략 — false 금지, BLUEPRINT §3).
function _metaSchemaRefEdgeStyle(count) {
  const n = Math.max(1, Number(count) || 1);
  return { stroke: "#8fa3bf", lineWidth: 1 + Math.min(2.4, Math.log2(n + 1) * 0.55),
    strokeOpacity: 0.75, zIndex: _METZ.EDGE,
    labelText: n > 1 ? String(n) : "", labelFontSize: 9, labelFill: "#64748b",
    labelBackground: true, labelBackgroundFill: "#f6f8fb", labelBackgroundOpacity: 0.85,
    labelPlacement: "center" };
}
function _metaNodeStates(key) {
  const st = [];
  // feature-0016 §45: 검색 매칭 노드 = 'match' 상태 soft glow(예전 '너비 증가' 대체). glow 는 shadow 라
  //   뒤의 selected/analyzed stroke 와 독립적으로 공존한다(테두리색 충돌 없음).
  if (_metaGraph.mode === "search" && _metaGraph.searchMatchNodes && _metaGraph.searchMatchNodes.has(key)) st.push("match");
  if (_metaGraph.analyzed.has(key)) st.push("analyzed");
  if (_metaGraph.running.has(key)) st.push("running");
  if (_metaGraph.selected === key) st.push("selected");
  // §57(사용자 요구 ②): 상대 하이라이트 — 선택 노드의 1-hop 인접 밖 **모델 데이터 노드**만 흐리게.
  //   _metaNodeStates 경유라 _metaStateSig/_metaCacheSig 에 자동 포함 — 2.5s 상태 폴과 정합(§33 교훈).
  //   합성 chrome(CAT:/GX:/GB: 등)은 모델 밖 키라 자동 비대상.
  //   §57.5(리뷰 F1): 컬럼은 **소속 테이블의 밝기를 따른다** — 엣지 lit() 의 컬럼 폴딩과 규칙을
  //   일치시켜 "밝은 선이 흐린 컬럼에 꽂히는" 불일치(체감 무작위의 재생산)를 제거.
  const fa = _metaGraph.focusAdj;
  // §57.6(불변식): 선택 노드 자신은 fa 가 어떤 이유로든 stale 이어도 **절대 dim 되지 않는다** —
  //   사용자 실측(선택 노드가 흐린 채 잔존) 재발 방지의 최종 방어선.
  if (fa && key !== _metaGraph.selected && _metaGraph.nodes.has(key)) {
    let k2 = key;
    const nd = _metaGraph.nodes.get(key);
    if (nd && nd.label === "Column") {
      const pk = _metaColParent(key, nd.fqn);
      if (pk) k2 = pk;
    }
    if (!fa.self.has(key) && !fa.self.has(k2) && !fa.nodes.has(key) && !fa.nodes.has(k2)) st.push("dimmed");
  }
  return st;
}

// reltrace-colnav(사용자 결정 2026-07-10): 하이라이트(focusAdj) 산출 기준 키 해소. 선택 키가 모델에
//   있으면 그대로. 모델에 없는 컬럼(미펼침 테이블의 컬럼 — 접힘 시 제거·미펼침 시 미적재)이면
//   **소속 테이블이 모델의 Table 노드일 때만** 그 테이블로 폴백한다 — 선택 상태는 컬럼 그대로 두되,
//   화면 하이라이트(dim/lit focus)는 상위 종속 객체(테이블)가 선택된 것처럼 구성. 부모가 Table 이 아니거나
//   없으면 null — 테이블 접기·검색 prune 로 사라진 선택(§57.5 F2)의 '앵커 없는 전역 흐림 정리'(null)를 보존.
//   _metaGraphSetSelected(즉시)·_metaG6Build(매 빌드 재산출) 양쪽이 공유해 두 경로의 하이라이트를 일치시킨다.
function _metaFocusKeyFor(selKey) {
  if (!selKey) return null;
  if (_metaGraph.nodes.has(selKey)) return selKey;
  const ptk = _metaColParent(selKey, null);
  const pnode = ptk && _metaGraph.nodes.get(ptk);
  return (pnode && pnode.label === "Table") ? ptk : null;
}

// §57: 선택 노드의 1-hop 인접 집합 — self(자신+자기 컬럼) / nodes(인접 노드+컬럼의 소속 테이블+상대
//   스키마). 모델 1회 순회 — §57.5부터 **매 빌드 재산출**(선택 존재 시, 6k 모델 실측 ~10ms ≈ 빌드의
//   3% — stale 스냅샷 제거 비용으로 수용).
function _metaFocusAdjacency(selKey) {
  const self = new Set([selKey]);
  const nodes = new Set();
  const selNode = _metaGraph.nodes.get(selKey);
  if (selNode && selNode.label === "Table") {
    _metaGraph.nodes.forEach((n, k) => {
      if (n.label === "Column" && _metaColParent(k, n.fqn) === selKey) self.add(k);
    });
  }
  // 패널 MINOR: 컬럼 선택 시 소속 테이블 칩이 dim 되지 않게(선택 컬럼이 유령 컨테이너 위에 뜨는 오독 방지).
  if (selNode && selNode.label === "Column") {
    const ptk = _metaColParent(selKey, selNode.fqn);
    if (ptk) nodes.add(ptk);
  }
  const touch = (k) => {
    if (self.has(k)) return true;
    // REFERENCES 끝점은 모델 밖 컬럼 키일 수 있다(접힌 스키마 = 컬럼 미적재) — 키 문자열 파싱으로
    //   소속 테이블을 접어 판정(_metaColParent 는 fqn 없으면 key 로 파싱). 모델에 있는 비-Column
    //   노드(Table/Routine/Schema)는 자기 키가 곧 판정 단위라 부모 접기 비적용.
    const gn = _metaGraph.nodes.get(k);
    if (gn && gn.label !== "Column") return false;
    const pk = _metaColParent(k, gn && gn.fqn);
    return !!(pk && self.has(pk));
  };
  let touched = 0;   // §57.7: 바깥에 닿는 관계 수 — 0 이면 고립 노드(하이라이트 미발동)
  _metaGraph.edges.forEach((e) => {
    const sTouch = touch(e.source), tTouch = touch(e.target);
    if (!sTouch && !tTouch) return;
    const other = sTouch ? e.target : e.source;
    // §57.7 정련(리뷰 적발): self-FK 처럼 양끝이 모두 자기(자기 컬럼 포함)로 접히는 엣지는
    //   렌더러가 드롭(rs===rt)해 보이는 관계선이 없다 — 강조할 외부 부분그래프가 아니므로 미집계.
    if (!touch(other)) touched += 1;
    nodes.add(other);
    const on = _metaGraph.nodes.get(other);
    const opk = (!on || on.label === "Column") ? _metaColParent(other, on && on.fqn) : null;
    if (opk) nodes.add(opk);
    // 승격 렌더 대비: 상대의 소속 스키마 키도 포함(접힌 카드로 승격돼도 카드가 흐려지지 않게).
    const osk = _metaCatParent(other, on && on.fqn);
    if (osk) nodes.add(osk);
  });
  // 자신의 소속 스키마도 유지(자기 클러스터 카드/컨텍스트 보존).
  const ssk = _metaCatParent(selKey, selNode && selNode.fqn);
  if (ssk) nodes.add(ssk);
  // §57.7(사용자 실측 "비연관 노드 클릭 시 UI 무너짐"): 모델에 1-hop 관계가 하나도 없는 **고립
  //   노드**는 강조할 부분그래프가 없다 — 화면 전체가 침강해 파괴처럼 읽힌다. 하이라이트 모드를
  //   발동하지 않고(null) 선택 테두리·상세만 제공한다(관계가 늦게 ingest 되면 다음 build 재산출이
  //   자동으로 하이라이트를 켠다 — §57.5 빌드 시점 재산출과 합성).
  if (touched === 0) return null;
  return { self, nodes };
}

// ── graph-perf-bg: 논블로킹 유틸(펼침/확장이 메인스레드를 얼리지 않도록) ──
// 무거운 setData+draw 직전에 브라우저가 busy 상태를 실제로 페인트하도록 두 번의 rAF 후 넘긴다.
//   단일 rAF 는 같은 프레임에 병합될 수 있고, microtask(Promise.resolve)는 페인트를 유발하지 못하므로 둘 다 부적합.
function _metaRaf() {
  return new Promise((res) => {
    if (typeof window !== "undefined" && window.requestAnimationFrame) window.requestAnimationFrame(() => res());
    else setTimeout(res, 0);
  });
}
function _metaYieldPaint() { return _metaRaf().then(() => _metaRaf()); }

// graph-perf-bg fix: 노드에 "적용할" state = 영속 마커(_metaNodeStates) + 명령형 busy(_busyKeys).
//   busy 를 signature 에 포함시켜 _metaGraphRefreshStates(2.5s 폴)가 fetch 창 도중 busy 를 덮어써 지우지 못하게 한다.
function _metaStateSig(key) {
  const st = _metaNodeStates(key);              // 매 호출 새 배열 — push 안전
  if (_metaGraph._busyKeys.has(key)) st.push("busy");
  return st;
}
// node-role-viz: 캐시 서명 = state 서명 + 역할 suffix. 역할은 G6 state 가 아니라 **build 시 칩 색/라벨로
//   bake 되는 style** 이라 setElementState 로 반영할 수 없다 — 대신 서명에 포함시켜 refreshStates 가
//   "역할 도착"을 변화로 감지하고 rebuild(_metaG6Apply)로 승격하게 한다. setElementState 에는 넘기지 않는다.
function _metaCacheSig(key) {
  const role = _metaGraph.roles.get(key);
  return _metaStateSig(key).join("|") + (role ? "#R=" + role : "");
}
function _metaSigRole(sig) {
  const i = (sig || "").indexOf("#R=");
  return i >= 0 ? sig.slice(i + 3) : "";
}
// 요소 state 적용 단일 진입점 — 적용과 동시에 _stateCache signature 를 동기화한다.
//   불변식: _stateCache.get(key) === 요소에 마지막 적용된 state 의 signature. 명령형 writer(busy·selected)도 이 경로를 쓰면
//   refreshStates 가 "변화 없음"으로 오판해 필요한 재적용을 건너뛰는 false-negative 가 원천 차단된다.
function _metaApplyState(key) {
  const g = _metaGraph.graph;
  if (!g || !key || !_metaGraph.nodes.has(key)) return;
  const st = _metaStateSig(key);
  // graph-initview: 렌더된 요소 id 로 매핑(접힌 스키마 카드=SC:) — 카드 게이팅으로 미렌더인 모델 키에
  // setElementState 하면 async reject 가 pageerror 로 새므로 skip + promise reject 흡수.
  const el = _metaRenderedIdFor(key);
  if (el) { try { Promise.resolve(g.setElementState(el, st)).catch(() => {}); } catch (_) {} }
  _metaGraph._stateCache.set(key, _metaCacheSig(key));   // node-role-viz: 역할 suffix 포함(불변식 유지)
}

// 클릭 노드에 임시 busy 하이라이트(명령형). **_metaNodeStates 에는 넣지 않는다**(rebuild 마다 재-bake 되어 영구
//   하이라이트로 굳음) — 대신 _busyKeys 로 소유 op(seq)와 함께 추적해 rebuild(_metaG6Apply)·reset 시 일괄 소멸.
//   on=true: seq 소유권 기록. on=false: op-scoped 해제 — seq 를 주면 그 op 가 여전히 소유할 때만 해제하여, 같은 key 를
//   재트리거한 신 op 의 busy 를 뒤늦게 resolve 된 stale op 가 지우지 못하게 한다(seq 미지정이면 무조건 해제).
function _metaSetBusy(key, on, seq) {
  if (!key) return;
  if (!_metaGraph._busyTs) _metaGraph._busyTs = new Map();   // §57.8: stale busy TTL 소거용
  if (on) {
    _metaGraph._busyKeys.set(key, seq == null ? -1 : seq);
    _metaGraph._busyTs.set(key, Date.now());
  } else {
    if (seq != null && _metaGraph._busyKeys.get(key) !== seq) return;   // 신 op 가 이미 같은 key busy 소유 — stale op 는 건드리지 않음
    _metaGraph._busyKeys.delete(key);
    _metaGraph._busyTs.delete(key);
  }
  _metaApplyState(key);
}

// ── graph-rel-layout: 관계(REFERENCES) 기반 배치 pre-pass — 엣지 교차 최소화 ──
//   배치 순서(스키마 seriation + 클러스터 내 테이블 군집 순서)를 관계 가중치의 순수 함수로 결정한다.
//   유사도 w = Σ 컬럼-쌍(trusted=2 · 그 외 1). 관계 0 이면 기존 자연정렬과 동일(강등 없음) — 관계가
//   쌓일수록 다음 rebuild 에서 배치가 관계 기준으로 수렴한다(사용자 요청: 관계 확보에 따른 기준 배치).
//   결정론·펼침-불변: schemaExpanded 를 읽지 않는다(ADR-004 ② 배정 불변식 유지) — 입력(nodes+edges)이
//   같으면 출력이 같고, 순서 변경은 관계 데이터가 늘어난 rebuild 시점(기존 shelf 재배치 시야고정 경로)뿐.

// REFERENCES 끝점(항상 컬럼 키, 간혹 테이블 키) → 소속 테이블 키. 미해석 시 null.
function _metaRelTableKeyOf(k) {
  const n = _metaGraph.nodes.get(k);
  if (n && n.label === "Table") return k;
  return _metaColParent(k, n && n.fqn);
}
// 테이블-레벨 무향 인접행렬: tKey -> Map(tKey -> w). 모델에 실재하는 테이블 쌍만.
function _metaRelAdjacency(tableByKey) {
  const adj = new Map();
  const bump = (a, b, w) => { let m = adj.get(a); if (!m) { m = new Map(); adj.set(a, m); } m.set(b, (m.get(b) || 0) + w); };
  _metaGraph.edges.forEach((e) => {
    if (e.type !== "REFERENCES") return;
    const a = _metaRelTableKeyOf(e.source), b = _metaRelTableKeyOf(e.target);
    if (!a || !b || a === b || !tableByKey.has(a) || !tableByKey.has(b)) return;
    const w = e.status === "trusted" ? 2 : 1;   // 신뢰 관계를 유사도에 더 크게 반영
    bump(a, b, w); bump(b, a, w);
  });
  return adj;
}
// 스키마 seriation(greedy attachment): 관계 가중치가 큰 스키마끼리 shelf 순서상 인접 → 교차 엣지가 짧아진다.
//   seed = 총 외부 가중 최대 → 이후 "이미 배치된 집합과의 가중 합" 최대를 반복 선택(다른 연결군이면 새 seed).
//   tie-break 는 자연정렬 입력 순서(ids)의 first-win — 결정론. 관계 없는 스키마는 자연정렬 그대로 후미.
function _metaRelSchemaOrder(ids, adj, schemaOf) {
  const pairW = new Map(), deg = new Map();
  adj.forEach((m, a) => m.forEach((w, b) => {
    if (a >= b) return;                                       // 무향 1회
    const sa = schemaOf(a), sb = schemaOf(b);
    if (!sa || !sb || sa === sb) return;
    const k = sa < sb ? sa + "\n" + sb : sb + "\n" + sa;
    pairW.set(k, (pairW.get(k) || 0) + w);
    deg.set(sa, (deg.get(sa) || 0) + w);
    deg.set(sb, (deg.get(sb) || 0) + w);
  }));
  if (!pairW.size) return ids;                                // 스키마 간 관계 없음 → 자연정렬 유지
  const pw = (x, y) => pairW.get(x < y ? x + "\n" + y : y + "\n" + x) || 0;
  const connected = ids.filter((s) => (deg.get(s) || 0) > 0);
  const isolated = ids.filter((s) => !((deg.get(s) || 0) > 0));
  const remaining = new Set(connected), out = [], att = new Map();   // att = 배치 집합과의 누적 가중
  while (remaining.size) {
    let best = null, bw = -1;
    for (const s of connected) {
      if (!remaining.has(s)) continue;
      const w = out.length ? (att.get(s) || 0) : (deg.get(s) || 0);
      if (w > bw) { bw = w; best = s; }
    }
    if (out.length && bw === 0) {                             // 남은 것이 전부 미연결(다른 연결군) → 새 seed
      bw = -1;
      for (const s of connected) { if (!remaining.has(s)) continue; const w = deg.get(s) || 0; if (w > bw) { bw = w; best = s; } }
    }
    out.push(best); remaining.delete(best);
    for (const s of connected) if (remaining.has(s)) att.set(s, (att.get(s) || 0) + pw(s, best));
  }
  return out.concat(isolated);
}
// 클러스터 내 테이블 순서: 스키마 내부 관계의 연결 컴포넌트를 군집으로 붙이고(BFS, 가중 내림차순),
//   내부 무관계지만 외부 관계 보유 테이블은 이웃 스키마 seriation idx 순으로, 완전 고립은 자연정렬 그대로.
//   masonry Pass1 은 균등높이 최단열(=행 우선 채움)이라 순서상 인접 = 화면상 인접 → 관계 테이블이 모인다.
function _metaRelTableOrder(items, adj, schemaIdx, schemaOf) {
  if (!adj.size || items.length < 3) return items;
  const keys = items.map((t) => t.key), inSet = new Set(keys);
  const intra = new Map(), deg = new Map(), extAnchor = new Map();
  keys.forEach((k) => {
    const m = adj.get(k);
    let d = 0, ei = 0, ew = 0;
    if (m) m.forEach((w, o) => {
      if (inSet.has(o)) { let im = intra.get(k); if (!im) { im = new Map(); intra.set(k, im); } im.set(o, w); d += w; }
      else { const oi = schemaIdx.get(schemaOf(o)); if (oi != null) { ei += oi * w; ew += w; } }
    });
    deg.set(k, d);
    if (ew > 0) extAnchor.set(k, ei / ew);
  });
  const visited = new Set(), comps = [];
  keys.forEach((k) => {                                       // 컴포넌트 수집 — 입력(자연정렬) 순 seed, 결정론
    if (visited.has(k) || !(deg.get(k) > 0)) return;
    const comp = [], q = [k]; visited.add(k);
    while (q.length) {
      const c = q.shift(); comp.push(c);
      const im = intra.get(c);
      if (im) [...im.keys()].sort(_metaNatSort).forEach((o) => { if (!visited.has(o)) { visited.add(o); q.push(o); } });
    }
    comps.push(comp);
  });
  if (!comps.length && !extAnchor.size) return items;
  const compW = (comp) => comp.reduce((a, k) => a + (deg.get(k) || 0), 0);
  comps.sort((a, b) => (compW(b) - compW(a)) || (b.length - a.length) || _metaNatSort(a[0], b[0]));
  const orderComp = (comp) => {                               // 군집 내부: 최고 가중度 seed → BFS(간선 가중 내림차순)
    const cs = new Set(comp);
    const seed = comp.slice().sort((a, b) => ((deg.get(b) || 0) - (deg.get(a) || 0)) || _metaNatSort(a, b))[0];
    const out = [], seen = new Set([seed]), q = [seed];
    while (q.length) {
      const c = q.shift(); out.push(c);
      const im = intra.get(c);
      if (im) [...im.entries()].filter(([o]) => cs.has(o) && !seen.has(o))
        .sort((x, y) => (y[1] - x[1]) || _metaNatSort(x[0], y[0]))
        .forEach(([o]) => { seen.add(o); q.push(o); });
    }
    return out;
  };
  const ordered = [];
  comps.forEach((comp) => ordered.push(...orderComp(comp)));
  const rest = keys.filter((k) => !visited.has(k));
  const ext = rest.filter((k) => extAnchor.has(k)).sort((a, b) => (extAnchor.get(a) - extAnchor.get(b)) || _metaNatSort(a, b));
  const iso = rest.filter((k) => !extAnchor.has(k));          // 입력 자연정렬 순서 보존
  const pos = new Map(); let pi = 0;
  ordered.concat(ext, iso).forEach((k) => pos.set(k, pi++));
  return items.slice().sort((a, b) => pos.get(a.key) - pos.get(b.key));
}
// 전 스키마 테이블 순서 선산정: 군집 초기순서(_metaRelTableOrder) 위에 **barycenter 4-sweep** —
//   각 테이블을 이웃(스키마 내부+외부 관계 상대)들의 전역 위치 가중평균 순으로 재정렬하는 층별
//   교차 최소화 휴리스틱. 스키마-레벨 앵커만으로는 나란한 두 클러스터 사이의 상호 교차(a↔d, b↔c)를
//   못 풀기 때문에, 이웃 "테이블" 위치 기준 정렬로 관계선이 평행에 가깝게 정돈된다.
//   이웃 없는 테이블은 자기 현재 위치가 barycenter(제자리 안정). 접힌 스키마 테이블도 순서를 계산해
//   이웃 위치 근사에 쓴다(렌더 여부는 layouts 의 카드 게이팅이 결정 — 본 pre-pass 는 펼침-비의존).
function _metaRelOrderAll(groups, ids, adj, schemaIdx, schemaOf) {
  const orderBySchema = new Map();
  ids.forEach((s) => {
    const g = groups.get(s);
    if (!g || g.isTerms) return;
    const nat = g.tables.slice().sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
    orderBySchema.set(s, adj.size ? _metaRelTableOrder(nat, adj, schemaIdx, schemaOf) : nat);
  });
  if (!adj.size) return orderBySchema;
  // SPAN=1(gpos = schemaIdx + 로컬 rank): 상대 테이블의 "클러스터 내 순위"가 barycenter 를 지배하고
  //   스키마 원근은 약한 앵커로만 작용. 합성 벤치(시드 3종 × 랜덤/허브 토폴로지 6구성, 2D 세그먼트
  //   교차)에서 SPAN∈{4096,30,10,1} 중 5/6 최선·1D 층간 역전도 유일 개선(59→51) — 원거리 스키마
  //   위치가 지배(SPAN=4096)하면 같은 스키마쌍 엣지들의 상호 정렬이 무너져 1D 역전이 되레 늘었다.
  const SPAN = 1;
  const gpos = new Map();
  ids.forEach((s) => { const arr = orderBySchema.get(s); if (arr) arr.forEach((n, i) => gpos.set(n.key, schemaIdx.get(s) * SPAN + i)); });
  for (let pass = 0; pass < 4; pass++) {   // 벤치 기준 4-pass 수렴(2-pass 는 미수렴 잔차)
    ids.forEach((s) => {
      const arr = orderBySchema.get(s);
      if (!arr || arr.length < 2) return;
      const base = schemaIdx.get(s) * SPAN;
      const bc = new Map();
      arr.forEach((n) => {
        const m = adj.get(n.key);
        let acc = 0, tw = 0;
        if (m) m.forEach((w, o) => { const p = gpos.get(o); if (p != null) { acc += p * w; tw += w; } });
        bc.set(n.key, tw > 0 ? acc / tw : gpos.get(n.key));
      });
      arr.sort((a, b) => (bc.get(a.key) - bc.get(b.key)) || (gpos.get(a.key) - gpos.get(b.key)));
      arr.forEach((n, i) => gpos.set(n.key, base + i));
    });
  }
  return orderBySchema;
}

// ── graph-simgroups: 유사 속성 그룹 — 이름 affix family + 관계 attach + 역할 폴백 ──
//   사용자 요청 "각 테이블이 서로 유사한 속성끼리 배치 + 속성 범위가 가시적으로": 스키마 클러스터 내부를
//   유사 속성 그룹 블록(배경 박스 + 헤더 칩)으로 분할해, 군집이 '순서'가 아니라 '영역'으로 보이게 한다.
//   그룹핑은 (테이블명, 관계, 역할)의 순수 함수 — 결정론·펼침-비의존(schemaExpanded 무참조).

// 테이블명 affix family: 이름의 접두/접미 토큰(4~12자) 중 지원도(공유 테이블 수) ≥2 인 것에서
//   score = 지원도×길이 최대 토큰을 family 로 채택. "view_" 접두는 정규화 시 제거(뷰는 원본 가족으로).
//   반환: Map(tableKey → token|null). 게임 DB 처럼 구분자 없는 소문자 연접 이름에서도 동작하는 유일한
//   실용 신호가 공유 affix 다(underscore/camel 분할은 이런 이름에 무력).
// graph-simgroups: 테이블명 정규화 — 소문자화 + view 접두 제거(뷰는 원본 가족으로 묶기 위해).
//   §18.8 패널 MINOR: bare "view" 를 무조건 4자 절단하면 "viewer_log"→"er_log" mangle. 구분자 있는
//   "view_" 접두만 제거하고, 그 외 "view" 로 시작하는 실명(viewer 등)은 보존한다.
function _metaViewNorm(t) {
  const s = String((t && (t.name || t.key)) || "").toLowerCase();
  return s.startsWith("view_") ? s.slice(5) : s;
}
function _metaSimFamilies(tables) {
  const norm = _metaViewNorm;
  const support = new Map();   // token -> Set(tableKey)
  const bump = (tok, k) => { let s = support.get(tok); if (!s) { s = new Set(); support.set(tok, s); } s.add(k); };
  tables.forEach((t) => {
    const nm = norm(t);
    const L = Math.min(nm.length, 16);   // 16자: battletimereward 류 긴 스템 보존(12는 중간 절단)
    for (let l = 4; l <= L; l++) { bump(nm.slice(0, l), t.key); if (l < nm.length) bump(nm.slice(nm.length - l), t.key); }
  });
  const fam = new Map();
  tables.forEach((t) => {
    const nm = norm(t);
    let best = null, bs = 0;
    const L = Math.min(nm.length, 16);
    const consider = (tok) => {
      const sup = support.get(tok) ? support.get(tok).size : 0;
      if (sup < 2) return;
      const score = sup * tok.length;
      if (score > bs || (score === bs && best != null && tok < best)) { bs = score; best = tok; }
    };
    for (let l = 4; l <= L; l++) { consider(nm.slice(0, l)); if (l < nm.length) consider(nm.slice(nm.length - l)); }
    fam.set(t.key, best);
  });
  return fam;
}

// 그룹 조립: ① 이름 family ② family 없음 → 관계 가중 최대 family 로 attach ③ 역할 family ④ 기타.
//   싱글턴 family 는 ②~④ 로 강등(1개짜리 박스 노이즈 방지). 그룹 순서 = 관계 seriation(무관계는
//   크기 desc·라벨 natural), 그룹 내 테이블 순서 = _metaRelOrderAll 재사용(컴포넌트 군집 + barycenter —
//   "그룹"을 컨테이너로 취급). 반환: { list: [{key,label,n,tables[]}], orderIds: [...] } (결정론).
function _metaSimGroups(schemaId, tables, adj) {
  const fam = _metaSimFamilies(tables);
  const roleFam = (t) => { const r = _metaRoleOf(t.key); return r ? "role:" + r : null; };
  // Phase C(ADR-013 후속, semantic-embed): 백엔드 의미 클러스터(be:) 우선. namespace 는 정확히 1회('be:'+id)
  //   부여 — 하류 nm: 재접두 대상에서 제외(verify MAJOR: 이중 namespace 방지). 이 스키마 내 be: 멤버 ≥2 일
  //   때만 그룹화하고, 싱글턴이면 affix 폴백(be: 클러스터는 datasource 전역이라 한 스키마엔 1개만 있을 수 있음).
  const beOf = new Map(), beCnt = new Map();
  tables.forEach((t) => {
    const be = (t.cluster_id != null && String(t.cluster_id) !== "") ? ("be:" + t.cluster_id) : null;
    beOf.set(t.key, be);
    if (be) beCnt.set(be, (beCnt.get(be) || 0) + 1);
  });
  // 1차 배정 + 싱글턴 판정
  const byFam = new Map();
  tables.forEach((t) => { const f = fam.get(t.key); if (f) { if (!byFam.has(f)) byFam.set(f, []); byFam.get(f).push(t); } });
  const famOf = new Map();   // tKey -> famKey (확정)
  tables.forEach((t) => {
    const be = beOf.get(t.key);
    if (be && beCnt.get(be) >= 2) { famOf.set(t.key, be); return; }   // 백엔드 클러스터 우선(namespace 1회)
    const f = fam.get(t.key);
    if (f && byFam.get(f).length >= 2) { famOf.set(t.key, "nm:" + f); return; }
    famOf.set(t.key, null);   // 싱글턴/무family — 2차에서 attach
  });
  // 2차: 관계 가중 최대 family attach — **1차 확정(nm:) family 만** 부착 대상.
  //   §18.8 패널 MAJOR: 이웃 family 를 갱신 중인 live famOf 에서 읽으면 방금 2차-배정된 이웃으로 연쇄
  //   attach 되어 입력순서 의존 그룹이 생긴다(주석의 "무연쇄" 위배). 1차 스냅샷 fam1 에서만 읽어 연쇄 차단.
  const fam1 = new Map(famOf);
  tables.forEach((t) => {
    if (famOf.get(t.key)) return;
    const m = adj.get(t.key);
    if (!m) return;
    const wByFam = new Map();
    m.forEach((w, o) => { const f = fam1.get(o); if (f) wByFam.set(f, (wByFam.get(f) || 0) + w); });
    let best = null, bw = 0;
    [...wByFam.keys()].sort(_metaNatSort).forEach((f) => { const w = wByFam.get(f); if (w > bw) { bw = w; best = f; } });
    if (best) famOf.set(t.key, best);
  });
  // 3차: 역할 family → 기타
  tables.forEach((t) => { if (!famOf.get(t.key)) famOf.set(t.key, roleFam(t) || "misc"); });
  // 역할/기타 family 도 싱글턴이면 기타로 흡수 (nm: 은 2차 attach 로 커질 수 있어 유지)
  const cnt = new Map();
  famOf.forEach((f) => cnt.set(f, (cnt.get(f) || 0) + 1));
  tables.forEach((t) => { const f = famOf.get(t.key); if (f !== "misc" && !f.startsWith("nm:") && !f.startsWith("be:") && cnt.get(f) < 2) famOf.set(t.key, "misc"); });
  // 그룹 리스트 + 라벨
  const groupsBy = new Map();
  tables.forEach((t) => { const f = famOf.get(t.key); if (!groupsBy.has(f)) groupsBy.set(f, []); groupsBy.get(f).push(t); });
  const normNm = _metaViewNorm;   // §18.8 MINOR: view_ 만 제거(viewer 등 실명 보존) — _metaSimFamilies 와 동일 규칙
  const commonAffix = (arr) => {   // 멤버 정규화 이름의 최장 공통 접두/접미 중 긴 쪽(≥4) — 자연 스템 라벨
    if (!arr.length) return null;
    const ns = arr.map(normNm);
    let p = ns[0], sfx = ns[0];
    ns.forEach((x) => {
      let i = 0; while (i < p.length && i < x.length && p[i] === x[i]) i++;
      p = p.slice(0, i);
      let j = 0; while (j < sfx.length && j < x.length && sfx[sfx.length - 1 - j] === x[x.length - 1 - j]) j++;
      sfx = sfx.slice(sfx.length - j);
    });
    const best = p.length >= sfx.length ? p : sfx;
    return best.length >= 4 ? best : null;
  };
  const labelOf = (f, members) => {
    if (f === "misc") return "기타";
    if (f.startsWith("role:")) { const r = f.slice(5); const R = _META_ROLE[r]; return R ? R.icon + " " + R.ko : r; }
    if (f.startsWith("be:")) {   // Phase C: 백엔드 의미 클러스터 — 서버 라벨 우선, 없으면 affix/멤버 폴백
      const m = (members || []).find((x) => x && x.cluster_label);
      if (m && m.cluster_label) return String(m.cluster_label);
      const ca = commonAffix(members || []);
      return ca || ("의미군 " + f.slice(3));
    }
    let tok = f.slice(3);   // nm:token
    if (members && members.length >= 2) { const ca = commonAffix(members); if (ca && ca.length > tok.length) tok = ca; }
    if (members && members.length) {   // 방향 말줄임 — "이 스템으로 시작/끝나는 테이블들" 범위 신호(정확 일치 멤버가 있으면 생략)
      const ns = members.map(normNm);
      if (!ns.some((x) => x === tok)) {
        if (ns.every((x) => x.startsWith(tok))) return tok + "…";
        if (ns.every((x) => x.endsWith(tok))) return "…" + tok;
      }
    }
    return tok;
  };
  const nsKey = (f) => schemaId + "\u0001" + f;   // 그룹 키 네임스페이스(스키마별 유일, 제어문자 구분자)
  const baseOrder = [...groupsBy.keys()].sort((a, b) => (groupsBy.get(b).length - groupsBy.get(a).length) || _metaNatSort(labelOf(a, groupsBy.get(a)), labelOf(b, groupsBy.get(b))));
  // misc 는 항상 마지막(잡동사니가 seriation 으로 가운데 끼는 것 방지)
  const miscIdx = baseOrder.indexOf("misc");
  if (miscIdx >= 0) { baseOrder.splice(miscIdx, 1); baseOrder.push("misc"); }
  const nsIds = baseOrder.map(nsKey);
  const groupOfT = new Map();
  groupsBy.forEach((arr, f) => arr.forEach((t) => groupOfT.set(t.key, nsKey(f))));
  const groupOf = (tk) => groupOfT.get(tk) || null;
  // 그룹 seriation(관계 많은 그룹끼리 인접) — misc 제외 후 재부착(항상 마지막 유지)
  let serIds = _metaRelSchemaOrder(nsIds.filter((k) => k !== nsKey("misc")), adj, groupOf);
  if (groupsBy.has("misc")) serIds.push(nsKey("misc"));
  // feature-0016 §49(요구②, 적대리뷰 R1): 그룹 순서 안정화 — 이웃확장 rebuild 시 그룹이 재-seriate 되어 형제가 점프하지
  //   않도록 직전 순서(groupOrder[schemaId])를 보존하고 신규 그룹만 append. (misc 는 위에서 이미 마지막.)
  serIds = _metaStableSeq(serIds, _metaGraph.groupOrder.get(schemaId), (x) => x);
  _metaGraph.groupOrder.set(schemaId, serIds.slice());
  const gIdx = new Map(serIds.map((k, i) => [k, i]));
  // 그룹 내 순서: 컴포넌트 군집 + 그룹-간 barycenter (컨테이너=그룹으로 _metaRelOrderAll 재사용)
  const pseudo = new Map();
  groupsBy.forEach((arr, f) => pseudo.set(nsKey(f), { isTerms: false, tables: arr, terms: [], colsByTable: new Map() }));
  const ordered = _metaRelOrderAll(pseudo, serIds, adj, gIdx, groupOf);
  // feature-0016 §49(R1): 그룹 내 테이블 순서 안정화 — 신규 테이블만 append(기존 테이블 그룹내 열/행 위치 유지).
  serIds.forEach((k) => {
    const _fr = ordered.get(k); if (!_fr) return;
    const _st = _metaStableSeq(_fr, _metaGraph.groupTableOrder.get(k), (t) => t.key);
    ordered.set(k, _st);
    _metaGraph.groupTableOrder.set(k, _st.map((t) => t.key));
  });
  const list = serIds.map((k) => {
    const f = k.slice(schemaId.length + 1);
    const arr = ordered.get(k) || groupsBy.get(f) || [];
    return { key: k, fam: f, label: labelOf(f, arr), n: arr.length, tables: arr };
  }).filter((g) => g.n > 0);
  return list;
}

// 그룹 블록 시각 팔레트(연한 틴트 8종 순환 — 칩 teal·역할색과 경쟁하지 않는 저채도 배경/테두리)
const _META_GROUP_TINTS = [
  { bg: "#eef4fb", hd: "#dbe7f7", bd: "#b9cfe8" },
  { bg: "#eff8f1", hd: "#dcefe1", bd: "#bcdcc6" },
  { bg: "#fdf6ec", hd: "#f7e8cf", bd: "#e6cfa3" },
  { bg: "#f7f0fa", hd: "#ecdcf3", bd: "#d5b9e4" },
  { bg: "#fbf0f2", hd: "#f4dbe1", bd: "#e4b9c4" },
  { bg: "#eef7f9", hd: "#d9edf2", bd: "#b3d8e2" },
  { bg: "#f4f6ee", hd: "#e7ecd7", bd: "#cdd8ab" },
  { bg: "#f3f4f7", hd: "#e3e6ec", bd: "#c6ccd8" },
];

// 모델(_metaGraph.nodes/edges) → 위치 포함 G6 데이터. 스키마 클러스터를 관계 seriation(무관계 시 자연정렬)
// grid 로, 클러스터 내부는 유사 속성 그룹 블록(배경 박스+헤더, graph-simgroups)으로, 펼친 테이블의 컬럼을
// 그 아래 세로열로 결정론 배치(무-shuffle). 그룹이 1개뿐이면 기존 평면 masonry 그대로(시각 노이즈 방지).
// feature-0016 §49(요구②): 시퀀스 안정화 — 저장된 순서(savedKeys)의 항목을 먼저(현재 존재하는 것만, 저장 순서대로),
//   신규 항목은 fresh(seriated) 순서로 뒤에 append. 이웃확장 rebuild 시 기존 항목이 masonry 슬롯을 유지하고 신규만
//   추가돼 '더블클릭 시 전체 재배치' 를 제거한다. keyOf: 항목→비교 key. 순수 함수(부수효과 없음).
function _metaStableSeq(fresh, savedKeys, keyOf) {
  const byKey = new Map();
  fresh.forEach((x) => { byKey.set(keyOf(x), x); });
  const out = [], seen = new Set();
  (savedKeys || []).forEach((k) => { if (byKey.has(k) && !seen.has(k)) { out.push(byKey.get(k)); seen.add(k); } });
  fresh.forEach((x) => { const k = keyOf(x); if (!seen.has(k)) { out.push(x); seen.add(k); } });
  return out;
}

// graph-category(§55 A, REQ-20260706 ①): 스키마 클러스터의 **제품 카테고리** 배정 + ids 재배열.
//   WebProductDatabases(제품별 접근 DB SSOT)의 스키마→제품 매핑(schemaProducts)으로 각 클러스터를
//   catKey("PC:<제품id>" | "PC:__none__" 미분류)에 배정한다 — 하위 '유사 속성 그룹'(sim-group)과 같은
//   가시적 구분(배경 밴드+헤더 칩)의 데이터 계층. 매핑이 전무하면 enabled=false(기존 배치 그대로 — 회귀 0).
//   다제품 스키마는 대표 제품(백엔드 정렬 1순위 = 제품 SortOrder)으로 배정하고 상세에서 전체 노출.
function _metaCatAssign(ids) {
  const res = { enabled: false, cats: [], inCat: new Set(), ids: null };
  const sp = _metaGraph.schemaProducts;
  const core = (ids || []).filter((k) => k !== _META_TERMS_COMBO);
  if (!sp || !sp.size || !core.length) return res;
  const byCat = new Map();
  let mapped = 0;
  // 패널 MINOR fix: 매핑은 schemaProducts 가 로드된 scope 의 클러스터에만 적용 — 크로스-DS 이웃확장으로
  //   유입된 타 scope 클러스터가 동명 DB 로 현재 제품 밴드에 오배정되지 않게(타 scope = 미분류).
  const spScope = String(_metaGraph.loadedScope || "");
  core.forEach((id) => {
    const inScope = !spScope || String(id).startsWith(spScope + ":");
    const nm = String(_metaComboName(id) || "").toLowerCase();
    const plist = inScope ? sp.get(nm) : null;
    let key = "PC:__none__", label = "미분류", sort = Number.MAX_SAFE_INTEGER;
    if (Array.isArray(plist) && plist.length) {
      const p = plist[0];
      key = "PC:" + p.id; label = p.name || ("제품#" + p.id);
      sort = (typeof p.sort === "number" ? p.sort : 100) * 100000 + (p.id || 0);
      mapped++;
    }
    let c = byCat.get(key);
    if (!c) { c = { key, label, sort, members: [] }; byCat.set(key, c); }
    c.members.push(id);
  });
  if (!mapped) return res;   // 전부 미분류 → 카테고리 계층 미방출(단일 흐름 유지)
  const cats = [...byCat.values()].sort((a, b) =>
    ((a.key === "PC:__none__") - (b.key === "PC:__none__")) || (a.sort - b.sort) || _metaNatSort(a.label, b.label));
  // §49 동형: 카테고리 순서 안정화 — rebuild 시 밴드가 자리를 점프하지 않게.
  const stable = _metaStableSeq(cats, _metaGraph.catOrder, (c) => c.key);
  _metaGraph.catOrder = stable.map((c) => c.key);
  _metaGraph.catMembers = new Map(); _metaGraph.catLabelOf = new Map();
  const pos = new Map(core.map((k, i) => [k, i]));
  const ordered = [];
  stable.forEach((c) => {
    c.memberSet = new Set(c.members);
    // 접힘: 사용자 지속 의도. 단 검색 매칭/추가 스키마를 품은 카테고리는 강제 펼침(결과 가시 — 그룹 접힘 동형).
    c.collapsed = _metaGraph.catCollapsed.has(c.key) && !c.members.some((sid) =>
      (_metaGraph.searchMatch && _metaGraph.searchMatch.has(sid)) || _metaGraph.searchAdded.has(sid));
    c.members.sort((a, b) => pos.get(a) - pos.get(b));   // 카테고리 내부는 기존(안정화된) 클러스터 순서 유지
    c.members.forEach((m) => { res.inCat.add(m); ordered.push(m); });
    _metaGraph.catMembers.set(c.key, c.members.slice());
    _metaGraph.catLabelOf.set(c.key, c.label);
  });
  res.enabled = true; res.cats = stable; res.ids = ordered;
  return res;
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
  if (!aggActive && _metaGraph.nodes.size > _META_CULL_MIN) {
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
  // viewport-cull(§65): 이 build 가 커버한 뷰포트 중심·반경(마진 제외 실 뷰포트) — 팬 후 재-emit 판정용(aftertransform).
  _metaGraph._cullVp = _cullActive
    ? { cx: (_vx0 + _vx1) / 2, cy: (_vy0 + _vy1) / 2, hw: (_vx1 - _vx0) / 2, hh: (_vy1 - _vy0) / 2 }
    : null;
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
    if (_cullActive && !g.isTerms && !_freePlaced && !_clusterKeep(g) && _offView(L.x0, L.y0, L.x0 + L.w, L.y0 + L.h)) return;
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
        if (!_keepFromCull(it.key) && _offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + realH(g, it))) return;
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
      if (!_keepFromCull(it.key) && _offView(colLeftX, ty - _METLAY.TROW / 2, colLeftX + COLW, ty - _METLAY.TROW / 2 + realH(g, it))) return;   // 화면 밖 테이블 컬링(§76: 선택 관계 상대는 예외 — 엣지·상호작용 보존)
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
  _metaGraph._cullActive = false; _metaGraph._cullVp = null;   // viewport-cull(§65): products 뷰 stale 소거.
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
      mm.__lastGeomSig = sig;
    } catch (_) { /* 서명 비교 실패 → 아래 원본 렌더로 안전 폴백 */ }
    return orig();
  };
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
async function _metaGraphAnimateFocus(key, seq) {
  const g = _metaGraph.graph;
  if (!g || !key) return;
  // graph-rel-layout(§18.8 패널 MINOR): tween 생존 마커 — expand 가 rebuild 후 "tween 이 이미 죽었는지"를
  //   판정해 시야 보정 폴백을 결정한다(관계 재배치로 앵커가 원거리 이동 가능해져 필요해짐). seq 소유 기준.
  _metaGraph._focusLive = seq == null ? -1 : seq;
  try {
    await _metaGraphAnimateFocusRun(g, key, seq);
  } finally {
    if (_metaGraph._focusLive === (seq == null ? -1 : seq)) _metaGraph._focusLive = null;
  }
}
async function _metaGraphAnimateFocusRun(g, key, seq) {
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
  _metaGraph._cullActive = false; _metaGraph._cullVp = null;   // viewport-cull(§65): 스코프/뷰 전환 시 초기화.
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
  if (!window.G6 || typeof window.G6.Graph !== "function") {
    _metaGraphStatus("그래프 라이브러리(G6)를 불러오지 못했습니다.");
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
  try {
    graph = new window.G6.Graph(Object.assign({}, baseCfg, { plugins: [{ type: "minimap", key: "minimap", size: [168, 112], position: "right-bottom" }] }));   // graph-minimap-reuse: 명시 key → getPluginInstance("minimap") 직접 히트(by-type 폴백 경고 회피)
  } catch (_) { graph = null; }
  if (!graph) {
    try { graph = new window.G6.Graph(baseCfg); } catch (_) { graph = null; }
  }
  if (!graph) { _metaGraphStatus("그래프 초기화 실패(G6)."); return; }
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

// ── graph-ctxmenu: 노드 우클릭 상세 상호작용 (REQ-20260702T113000) ──────────────────
//   스키마를 모르는 사용자가 선택 노드의 연관 관계를 파악하는 진입점. 메뉴는 **HTML 오버레이**
//   (G6 요소 아님) — _metaG6Apply 의 setData 전체 재구성과 무간섭(BLUEPRINT §3 함정 회피).
//   전 항목이 읽기성 탐색 + 기존 AI 분석 트리거 재사용 — mutation 0 (CONVENTIONS §10.7 대상 아님).
const _metaCtx = { el: null, x: 0, y: 0, bound: false };

// G6 이벤트 → 메뉴 표시용 client 좌표. e.client 우선, 없으면 capture 리스너가 담은 좌표.
function _metaCtxPoint(e) {
  if (e && e.client && typeof e.client.x === "number" && typeof e.client.y === "number") {
    return { x: e.client.x, y: e.client.y };
  }
  return { x: _metaCtx.x || 0, y: _metaCtx.y || 0 };
}

function _metaGraphCtxHide() {
  if (!_metaCtx.el) return;
  // 접근성(review): 포커스가 메뉴 안에 있을 때만 이전 지점으로 복원 — 외부클릭 dismiss 의 포커스는 뺏지 않음.
  const pf = _metaCtx.prevFocus;
  const restore = pf && pf.focus && _metaCtx.el.contains(document.activeElement) && document.contains(pf);
  try { _metaCtx.el.remove(); } catch (_) {}
  _metaCtx.el = null;
  _metaCtx.prevFocus = null;
  if (restore) { try { pf.focus({ preventScroll: true }); } catch (_) {} }
}

// 메뉴 렌더. items: {head,badge,badgeColor,label} 헤더 · {sep} 구분선 · {label,icon,hint,onClick} 항목 ·
//   {label,icon,chips:[{label,onClick}]} 한 행 소형버튼(hop 선택). 전부 DOM 생성(innerHTML 미사용 — XSS 0).
//   뷰포트 clamp + Esc/외부클릭/스크롤/리사이즈 dismiss + ↑/↓/Enter 키보드 접근.
function _metaGraphCtxShow(items, x, y) {
  const prevFocus = document.activeElement;   // hide 전에 캡처(Hide 가 prevFocus 를 소거하므로)
  _metaGraphCtxHide();
  _metaCtx.prevFocus = prevFocus;
  const menu = document.createElement("div");
  menu.className = "admin-meta-graph-ctxmenu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "그래프 상호작용 메뉴");
  (items || []).forEach((it) => {
    if (!it) return;
    if (it.sep) {
      const s = document.createElement("div");
      s.className = "amgc-sep";
      menu.appendChild(s);
      return;
    }
    if (it.head) {
      const h = document.createElement("div");
      h.className = "amgc-head";
      if (it.badge) {
        const b = document.createElement("span");
        // 상세/관계 패널의 배지 스타일을 재사용(디자인 리뷰 — 동일 개념 배지 시각 통일). 라벨만 한글.
        b.className = "admin-meta-graph-badge amgc-badge";
        b.style.background = it.badgeColor || "#5c6773";
        b.textContent = it.badge;
        h.appendChild(b);
      }
      const t = document.createElement("strong");
      t.textContent = it.label || "";
      h.appendChild(t);
      menu.appendChild(h);
      return;
    }
    if (it.chips) {
      const row = document.createElement("div");
      row.className = "amgc-item amgc-chip-row";
      const lbl = document.createElement("span");
      lbl.className = "amgc-label";
      lbl.textContent = (it.icon ? it.icon + " " : "") + (it.label || "");
      row.appendChild(lbl);
      it.chips.forEach((c) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "amgc-chip";
        b.setAttribute("role", "menuitem");
        b.textContent = c.label;
        b.addEventListener("click", (ev) => { ev.stopPropagation(); _metaGraphCtxHide(); if (c.onClick) c.onClick(); });
        row.appendChild(b);
      });
      menu.appendChild(row);
      return;
    }
    const el = document.createElement("button");
    el.type = "button";
    el.className = "amgc-item";
    el.setAttribute("role", "menuitem");
    if (it.disabled) el.disabled = true;
    const lbl = document.createElement("span");
    lbl.className = "amgc-label";
    lbl.textContent = (it.icon ? it.icon + " " : "") + (it.label || "");
    el.appendChild(lbl);
    if (it.hint) {
      const h = document.createElement("span");
      h.className = "amgc-hint";
      h.textContent = it.hint;
      el.appendChild(h);
    }
    if (!it.disabled) el.addEventListener("click", () => { _metaGraphCtxHide(); if (it.onClick) it.onClick(); });
    menu.appendChild(el);
  });
  document.body.appendChild(menu);
  // 뷰포트 clamp — 우/하단 넘침 시 화면 안쪽으로 이동.
  const r = menu.getBoundingClientRect();
  let px = x, py = y;
  if (px + r.width > window.innerWidth - 8) px = Math.max(8, window.innerWidth - r.width - 8);
  if (py + r.height > window.innerHeight - 8) py = Math.max(8, window.innerHeight - r.height - 8);
  menu.style.left = px + "px";
  menu.style.top = py + "px";
  _metaCtx.el = menu;
  const first = menu.querySelector("button.amgc-item:not(:disabled)");
  if (first) { try { first.focus({ preventScroll: true }); } catch (_) {} }
  if (!_metaCtx.bound) {
    _metaCtx.bound = true;
    // 외부 클릭(모든 버튼) dismiss — 메뉴 내부 pointerdown 은 유지(click 에서 액션 후 hide).
    document.addEventListener("pointerdown", (ev) => {
      if (_metaCtx.el && !_metaCtx.el.contains(ev.target)) _metaGraphCtxHide();
    }, true);
    document.addEventListener("keydown", (ev) => {
      if (!_metaCtx.el) return;
      if (ev.key === "Escape" || ev.key === "Tab") { _metaGraphCtxHide(); return; }   // Tab=닫기(포커스 트랩 대신 복원)
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      const btns = Array.prototype.slice.call(
        _metaCtx.el.querySelectorAll("button.amgc-item:not(:disabled), button.amgc-chip"));
      if (!btns.length) return;
      ev.preventDefault();
      const i = btns.indexOf(document.activeElement);
      const next = btns[(i + (ev.key === "ArrowDown" ? 1 : -1) + btns.length) % btns.length];
      try { next.focus({ preventScroll: true }); } catch (_) {}
    }, true);
    window.addEventListener("resize", _metaGraphCtxHide);
    document.addEventListener("scroll", _metaGraphCtxHide, true);
    // review: 휠 줌(zoom-canvas)은 scroll 이벤트가 없어 메뉴가 옛 좌표에 부유 — wheel 도 dismiss.
    document.addEventListener("wheel", _metaGraphCtxHide, { capture: true, passive: true });
  }
}

// 클립보드 복사(FQN/이름) — navigator.clipboard 우선, 거부/미지원 시 textarea 폴백(review: 침묵 실패 방지).
function _metaGraphCopyText(txt) {
  if (!txt) return;
  const done = () => { if (typeof showToast === "function") showToast(`복사했습니다: ${txt}`); };
  const fallback = () => {
    try {
      const ta = document.createElement("textarea");
      ta.value = txt;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      if (ok) done();
      else if (typeof showToast === "function") showToast("복사에 실패했습니다.", true);
    } catch (_) {
      if (typeof showToast === "function") showToast("복사에 실패했습니다.", true);
    }
  };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done, fallback);
      return;
    }
  } catch (_) {}
  fallback();
}

// 노드(Table/Column/Term) kind 별 우클릭 메뉴 구성.
function _metaGraphCtxForNode(key, x, y) {
  const n = _metaGraph.nodes.get(key);
  if (!n) return;
  const scope = key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common");
  const hopChips = {
    icon: "🕸", label: "관계 확장",
    // review: 1회성 확장 — 툴바 '이웃 깊이' select 를 조용히 바꾸지 않고 depth 를 직접 넘긴다.
    chips: ["1", "2", "3"].map((d) => ({ label: `${d}-hop`, onClick: () => _metaGraphExpand(key, d) })),
  };
  const items = [
    { head: true, badge: _META_LABEL_KO[n.label] || n.label || "노드", badgeColor: _META_GRAPH_COLOR[n.label] || "#5c6773", label: n.name || key },
    { icon: "📋", label: "상세 보기", hint: "설명·컬럼·용어", onClick: () => _metaGraphShowDetail(key) },
    { icon: "🔗", label: "관계 상세", hint: "방향·신뢰도·근거", onClick: () => _metaGraphShowRelations(key) },
    hopChips,   // review: 더블클릭 확장과 파리티 — Column 포함 전 kind 노출
  ];
  items.push({ icon: "🎯", label: "이 노드 중심으로 보기", hint: "주변만 남김", onClick: () => _metaGraphFocus(key) });
  if (n.label === "Table") {
    items.push(_metaTableHasCols(key)
      ? { icon: "▦", label: "컬럼 접기", onClick: () => _metaGraphCollapse(key) }
      : { icon: "▦", label: "컬럼 펼치기", onClick: () => _metaGraphToggleColumns(key) });
  }
  // graph-navfilter(§54⑤): 루틴 파라미터 접기/펼치기 — 테이블 컬럼 항목의 루틴 판(동기 Set 토글).
  //   terms 클러스터는 방출 게이트와 짝 맞춰 항목 미노출.
  if (n.label === "Routine" && _metaSchemaComboOf(n) !== _META_TERMS_COMBO && _metaRoutineParamList(n).length) {
    const rOpen = _metaGraph.routineExpanded.has(key);
    items.push({ icon: "▦", label: rOpen ? "파라미터 접기" : "파라미터 펼치기",
      onClick: () => { if (rOpen) _metaGraph.routineExpanded.delete(key); else _metaGraph.routineExpanded.add(key); _metaG6Apply(false); } });
  }
  if (n.label === "Column") {
    const pk = _metaColParent(key, n.fqn);
    if (pk) items.push({ icon: "📄", label: "소속 테이블 상세", onClick: () => _metaGraphShowDetail(pk) });
  }
  items.push({ sep: true });
  items.push({
    // graph-funcproc(REQ ④): '재분석' 라벨 제거 — 능동 분석 재실행이 곧 재분석(UX 중복 정리).
    icon: "✨", label: "AI 능동 분석", hint: "관련 노드 자동 분석 · 상세 패널 버튼 hover 로 지침 입력",
    // 상세 카드를 먼저 열어 AI box 에 진행이 보이게 한 뒤 트리거(ShowDetail 은 내부 catch 라 항상 resolve).
    // §18.8 패널(MINOR): ctxmenu 경로는 지침 미전송 — 이전 노드의 stale 지침이 화면 표시 없이 암묵
    // 적용되는 것을 차단. 지침은 popover(입력이 눈에 보이는 경로)로만 전송한다.
    onClick: () => { _metaGraphShowDetail(key).then(() => _metaGraphAnalyze(key, scope)); },
  });
  items.push({
    icon: "📑", label: n.label === "GlossaryTerm" ? "이름 복사" : "FQN 복사",
    onClick: () => _metaGraphCopyText(n.fqn || n.name || key),
  });
  _metaGraphCtxShow(items, x, y);
}

// graph-initview: 스키마(접힌 카드 "SC:" 또는 펼친 스키마의 접기 ctl "XS:") 우클릭 메뉴.
//   좌클릭(펼치기/접기)과 파리티 — 접힌 카드도 우클릭이 동작해 펼치기·상세·복사에 도달한다.
function _metaGraphCtxForSchema(schemaKey, x, y) {
  if (!schemaKey) return;
  const n = _metaGraph.nodes.get(schemaKey);
  const name = _metaComboName(schemaKey);
  const expanded = _metaGraph.schemaExpanded.has(schemaKey);
  const cnt = (n && typeof n.table_count === "number") ? n.table_count : null;
  const items = [
    { head: true, badge: "스키마", badgeColor: _META_GRAPH_COLOR.Schema, label: cnt != null ? `${name} · 테이블 ${cnt}` : name },
  ];
  items.push(expanded
    ? { icon: "▦", label: "접기 (카드로)", onClick: () => _metaGraphCollapseSchema(schemaKey) }
    : { icon: "▦", label: "펼치기 (테이블 표시)", hint: cnt != null ? `${cnt}개` : "", onClick: () => {
        // 좌클릭 SC: 경로와 동일 — 펼침 성공/기존 상태에서만 로컬 클러스터 상세 렌더(실패·빈·stale 오도 방지).
        //   ("already" 는 SC 경로에선 도달 불가 — expanded 면 위 접기 항목이 대신 붙음 — 이나 좌클릭과 대칭 유지.)
        _metaGraphExpandSchema(schemaKey).then((st) => { if (st === "expanded" || st === "already") _metaGraphShowClusterDetailLocal(schemaKey); }).catch(() => {});
      } });
  // 클러스터 상세는 그래프를 펼치지 않고 API 로 테이블 목록을 조회(접힌 카드에서 "펼치지 않고 훑어보기").
  items.push({ icon: "📋", label: "클러스터 상세", hint: "테이블 목록(펼치지 않음)", onClick: () => _metaGraphShowClusterDetailById(schemaKey) });
  // routine-dbanalysis(§53): DB(스키마) 단위 AI 능동 분석 — 미분석 테이블 일괄 시드(confirm 에 대상 수 표시).
  items.push({ icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(schemaKey) });
  items.push({ icon: "📑", label: "스키마명 복사", onClick: () => _metaGraphCopyText(name) });
  _metaGraphCtxShow(items, x, y);
}

// 스키마 클러스터(펼친 combo) 우클릭 메뉴 — combo 배경/테두리 우클릭. 접힌 카드는 _metaGraphCtxForSchema.
function _metaGraphCtxForCombo(comboId, x, y) {
  const name = _metaComboName(comboId);
  const isTerms = comboId === _META_TERMS_COMBO;
  _metaGraphCtxShow([
    { head: true, badge: isTerms ? "묶음" : "스키마", badgeColor: isTerms ? _META_GRAPH_COLOR.GlossaryTerm : _META_GRAPH_COLOR.Schema, label: name },
    { icon: "📋", label: "클러스터 상세", hint: "테이블 목록", onClick: () => _metaGraphShowClusterDetailById(comboId) },
    // graph-initview 파리티: 펼친 스키마 combo 우클릭도 카드로 접기 도달(기존엔 "−" ctl 클릭만).
    (isTerms || !_metaGraph.schemaExpanded.has(comboId)) ? null
      : { icon: "▦", label: "접기 (카드로)", onClick: () => _metaGraphCollapseSchema(comboId) },
    // routine-dbanalysis(§53): DB 단위 능동 분석 — 용어 묶음(합성)은 제외.
    isTerms ? null : { icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(comboId) },
    isTerms ? null : { icon: "📑", label: "스키마명 복사", onClick: () => _metaGraphCopyText(name) },
  ], x, y);
}

// 엣지(관계선) 우클릭 메뉴 (review MAJOR-2) — 관계 자체의 신뢰도·근거·cardinality + 양끝 노드 이동.
function _metaGraphCtxForEdge(edgeId, x, y) {
  const e = _metaGraph.edges.get(edgeId);
  if (!e) { _metaGraphCtxForCanvas(x, y); return; }
  const sn = _metaGraph.nodes.get(e.source) || { name: e.source };
  const tn = _metaGraph.nodes.get(e.target) || { name: e.target };
  const w = (e.weight != null && e.weight !== "" && !isNaN(Number(e.weight))) ? Number(e.weight).toFixed(2) : "";
  const statusKo = e.status === "trusted" ? "신뢰" : (e.status === "candidate" ? "추정" : (e.edge_source === "fk_introspect" ? "FK" : ""));
  const srcKo = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "";
  const info = [
    _META_EDGE_TYPE_KO[e.type] || e.type,
    statusKo ? `${statusKo}${w ? ` w=${w}` : ""}` : "",
    e.cardinality ? `[${e.cardinality}]` : "",
    srcKo ? `근거: ${srcKo}` : "",
  ].filter(Boolean).join(" · ");
  // 관계 상세의 앵커: 컬럼 단위 엣지면 소속 테이블 관점으로 (테이블 행에 조인 컬럼이 함께 표기됨).
  const anchor = (sn.label === "Column" && _metaColParent(e.source, sn.fqn)) || e.source;
  _metaGraphCtxShow([
    { head: true, badge: "관계", badgeColor: "#6b4410", label: `${sn.name || e.source} → ${tn.name || e.target}` },
    { icon: "ℹ️", label: info, disabled: true },
    { icon: "📋", label: `출발 노드 상세 — ${sn.name || e.source}`, onClick: () => _metaGraphShowDetail(e.source) },
    { icon: "📋", label: `도착 노드 상세 — ${tn.name || e.target}`, onClick: () => _metaGraphShowDetail(e.target) },
    { icon: "🔗", label: "관계 상세 (출발 기준)", hint: "방향·신뢰도·근거", onClick: () => _metaGraphShowRelations(anchor) },
  ], x, y);
}

// 빈 캔버스 우클릭 메뉴.
function _metaGraphCtxForCanvas(x, y) {
  _metaGraphCtxShow([
    { icon: "⛶", label: "전체 맞춤", onClick: () => { const g = _metaGraph.graph; if (g) { try { g.fitView({ padding: 30 }, false); } catch (_) {} } } },
    { icon: "↺", label: "그래프 초기화", hint: "데이터소스 진입 뷰", onClick: () => _metaGraphLoadRoots() },
  ], x, y);
}

// graph-panel-resize: 상세 패널 폭을 드래그(및 ←/→ 키)로 조절 — CSS var(--meta-graph-detail-w) 갱신 + localStorage 영속.
//   핸들은 캔버스 오른쪽·패널 왼쪽 사이의 세로 바(#metadataGraphResizer)라, 왼쪽으로 끌면 패널이 넓어진다.
//   1fr 캔버스가 줄면 ResizeObserver(위)가 cy.resize()+fit 을 debounce 호출하므로 별도 라이브 리사이즈 불필요(놓을 때만 보강).
function _metaGraphInitResizer() {
  const handle = document.getElementById("metadataGraphResizer");
  const body = document.querySelector(".admin-meta-graph-body");
  const root = document.getElementById("metadataGraphView");
  if (!handle || !body || !root || handle._bound) return;
  handle._bound = true;
  const MIN = 240, CANVAS_MIN = 360;   // 패널 최소폭 / 캔버스 보존 최소폭
  const clampW = (w) => {
    const total = body.clientWidth || 0;
    const max = total > 0 ? Math.max(MIN, total - CANVAS_MIN - 16) : Math.max(MIN, w);
    return Math.round(Math.min(Math.max(w, MIN), max));
  };
  const applyW = (w) => { root.style.setProperty("--meta-graph-detail-w", clampW(w) + "px"); };
  const curW = () => {
    const v = getComputedStyle(root).getPropertyValue("--meta-graph-detail-w").trim();
    const n = parseInt(v, 10);
    if (isFinite(n) && n > 0) return n;
    const d = document.getElementById("metadataGraphDetail");
    return (d && d.clientWidth) ? d.clientWidth : 340;
  };
  const persist = () => { try { localStorage.setItem("metaGraphDetailW", String(curW())); } catch (_) {} };
  const refit = () => { if (_metaGraph.graph) { try { _metaGraph.graph.resize(); } catch (_) {} _metaGraphFitClamped(false); } };   // graph-initview: 클램프 fit(무-focus — 현재 위치 보존)
  // 저장된 폭 복원(있으면).
  try { const saved = parseInt(localStorage.getItem("metaGraphDetailW") || "", 10); if (isFinite(saved) && saved > 0) applyW(saved); } catch (_) {}
  // 리뷰 fix(MEDIUM-2): 창 크기 변화 시 현재 폭을 새 body 폭 기준으로 재-clamp — 넓은 화면에서 저장한 폭이
  //   좁은 화면에서 캔버스를 near-0 로 짓누르지 않게 한다(ResizeObserver 는 cy.resize 만 하고 폭 재적용 안 함).
  let _rwT = null;
  window.addEventListener("resize", () => {
    if (_rwT) clearTimeout(_rwT);
    _rwT = setTimeout(() => { applyW(curW()); }, 150);
  });
  let startX = 0, startW = 0;
  const onMove = (e) => { applyW(startW + (startX - e.clientX)); };   // 왼쪽으로 끌면 패널 넓어짐
  const endDrag = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", endDrag);
    document.removeEventListener("pointercancel", endDrag);   // 리뷰 fix(MEDIUM-1): 터치 중단·제스처 취소 시에도 정리
    handle.classList.remove("is-dragging");
    document.body.style.userSelect = "";
    persist(); refit();
  };
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    startX = e.clientX; startW = curW();
    handle.classList.add("is-dragging");
    document.body.style.userSelect = "none";
    try { handle.setPointerCapture(e.pointerId); } catch (_) {}   // 리뷰 fix(MEDIUM-1): 캡처로 out-of-window 이동·취소 확실 정리
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", endDrag);
    document.addEventListener("pointercancel", endDrag);
  });
  // 키보드 접근(WAI-ARIA separator): ← 넓게 / → 좁게, 24px 단위.
  handle.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    applyW(curW() + (e.key === "ArrowLeft" ? 24 : -24));
    persist(); refit();
  });
}

// 검색어 관련도 점수(0~1): exact name > prefix > name contains > fqn contains.
function _metaRelevance(name, fqn, ql) {
  name = (name || "").toLowerCase(); fqn = (fqn || "").toLowerCase();
  if (name === ql) return 1.0;
  if (name.startsWith(ql)) return 0.85;
  if (name.indexOf(ql) >= 0) return 0.65;
  if (fqn.indexOf(ql) >= 0) return 0.45;
  return 0.3;
}

// graph-navfilter(§54③): 검색이 순수 추가한 노드 중 사용자 미접촉(pristine)만 모델에서 회수 —
//   펼침(schemaExpanded/Loaded)·드래그(clusterOffset/nodePos)·확장(엣지 참조·컬럼 보유)된 것은 보존.
//   재검색 키스트로크마다 호출해 비매칭 카드의 누적을 막고, 클리어 시엔 검색 잔재만 걷어낸다.
function _metaSearchPrunePristine() {
  if (!_metaGraph.searchAdded.size) return;
  const referenced = new Set();
  _metaGraph.edges.forEach((e) => { referenced.add(e.source); referenced.add(e.target); });
  _metaGraph.searchAdded.forEach((k) => {
    const n = _metaGraph.nodes.get(k);
    if (!n) return;
    // 재검증 MINOR: Column 은 회수 제외 — colsByTable 불변식(Ingest 증가·Collapse 감소·Reset 초기화
    //   3경로 전용)을 prune 이 4번째 삭제 경로로 우회하면 flat-scope 에서 hasCols 가 영구 true 로 고착.
    if (n.label === "Column") return;
    if (n.label === "Schema") {
      // schemaLoaded 포함 — 펼쳤다 접은 카드는 모델 테이블이 남아(렌더 게이팅만) 카드 회수 시 고아가 된다.
      if (_metaGraph.schemaExpanded.has(k) || _metaGraph.schemaLoaded.has(k) || _metaGraph.clusterOffset.has(k)) return;
    } else {
      if (_metaGraph.nodePos.has(k) || referenced.has(k) || _metaGraph.expanded.has(k)
          || _metaGraph.routineExpanded.has(k) || _metaTableHasCols(k)) return;   // §54⑤ 패널: 파라미터 펼침도 사용자 접촉
    }
    _metaGraph.nodes.delete(k);
    _metaGraph.routineExpanded.delete(k);   // stale 키 정리(회수된 노드의 펼침 상태 잔존 방지)
  });
  _metaGraph.searchAdded.clear();
}

async function _metaGraphSearch(q) {
  if (!_metaGraph.graph) return;
  _metaGraph.lastQuery = q;
  if (!q) {
    // graph-navfilter(§54③): 검색어 클리어는 그래프 구성(펼침·배치·확장)을 보존한다 — 검색 잔재
    //   (pristine 카드·glow)만 걷어내고 제자리 rebuild. 초기 화면 복귀는 '그래프 초기화' 버튼 전용.
    //   §54③ 패널 MAJOR: 검색이 products 개요를 리셋하고 들어온 경우(base.mode=products)는 보존할
    //   사용자 구성이 없다 — 원 화면(제품 개요)으로 복귀. 중심 보기 base 는 칩 복원.
    if (_metaGraph.mode !== "search" && !_metaGraph.searchMatchNodes) return;   // 지울 검색 상태 없음 — no-op(base 소비 전, 재검증 MINOR)
    const base = _metaGraph._searchBase; _metaGraph._searchBase = null;
    const scopeNow = adminState.metadata.scopeKey || "common";
    const preserve = _metaGraph.mode !== "products" && !(base && base.mode === "products")
      && (_metaGraph.loadedScope || "common") === scopeNow && _metaGraph.nodes.size > 0;
    if (!preserve) { _metaGraphLoadRoots(); return; }
    _metaSearchPrunePristine();
    _metaGraph.searchMatch = null; _metaGraph.searchMatchTables = null;
    _metaGraph.searchMatchNodes = null; _metaGraph.searchCapped = false;
    if (_metaGraph.nodes.size === 0) { _metaGraphLoadRoots(); return; }   // 패널 MAJOR: 잔재 회수 후 빈 모델 — 허위 '유지' 방지
    _metaGraph.mode = (base && base.mode && base.mode !== "search") ? base.mode : "roots";   // 원 모드(neighbor 등) 복원
    _metaGraph.nodes.forEach((n) => { delete n.rel; });
    const seq0 = _metaGraph._opSeq;            // bump 없음 — in-flight 펼침·확장은 여전히 유효(additive 병존)
    await _metaG6Apply(false);                 // 카메라·배치 유지(fit 금지)
    if (seq0 !== _metaGraph._opSeq) return;
    if (base && base.focusName) {
      _metaGraphFocusChip(base.focusName);     // 패널 MAJOR: 중심 보기 부분 그래프가 '전체'로 위장하지 않게 칩 복원
      _metaGraphStatus("검색 해제 — 중심 보기 서브그래프 유지(전체는 칩의 '전체 보기' 또는 '초기화').");
    } else {
      _metaGraphStatus("검색 해제 — 그래프 구성(펼침·배치·확장)은 유지됩니다. 초기 화면은 '초기화' 버튼.");
    }
    return;
  }
  _metaGraphStatus("검색 중…");
  const scope = adminState.metadata.scopeKey || "common";
  const scopeParam = (scope && scope !== "common") ? `&scope=${encodeURIComponent(scope)}` : "";
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?q=${encodeURIComponent(q)}${scopeParam}`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "그래프 검색 실패");
    return;
  }
  if (q !== _metaGraph.lastQuery) return;
  // graph-navfilter(§54③): 같은 scope 의 기존 그래프가 있으면 리셋하지 않고 **additive overlay** —
  //   사용자 구성(펼침·드래그·확장) 위에 검색 하이라이트만 얹는다. mode 대입 전에 판정(아래서 "search" 로 바뀜).
  const preserve = _metaGraph.mode !== "products"
    && (_metaGraph.loadedScope || "common") === scope && _metaGraph.nodes.size > 0;
  // §54③ 패널 MAJOR: 검색 진입 직전 base 컨텍스트 기록(최초 키스트로크만) — 클리어 시 products 복귀·
  //   중심 보기 칩 복원의 근거. mode 가 이미 "search" 면 이전 키스트로크의 base 를 유지.
  if (_metaGraph.mode !== "search") {
    _metaGraph._searchBase = { mode: _metaGraph.mode, focusName: _metaGraph._focusName || null };
  }
  _metaGraph.mode = "search";
  if (typeof _metaGraphFocusChip === "function") _metaGraphFocusChip(null);   // 검색 컨텍스트로 전환 — 중심 보기 칩 해제
  if (preserve) _metaSearchPrunePristine();   // 직전 키스트로크의 pristine 추가분 회수(누적 방지)
  else _metaGraphResetModel();
  const seq = _metaGraph._opSeq;   // review LOW-CONF: 세대 캡처 — await 사이 scope 전환 시 tail(status) 폐기.
  // graph-initview 검색 = **스키마 카드 필터 뷰**(사용자 요청): 매칭 테이블을 스키마별로 집계해 카드를
  //   유지하고 badge 를 "매칭/전체" 로 표기(펼치지 않음). 카드 클릭 시 그 스키마를 펼쳐 매칭 테이블을 강조.
  //   (이전엔 매칭 스키마를 combo 로 auto-expand 해 카드·badge 가 사라졌음.)
  const matchBySchema = new Map();   // schemaKey -> Set(매칭 테이블 key)
  const matchTables = new Set();     // 매칭 테이블 key(펼침 시 크기 강조)
  const terms = [];                  // 매칭 GlossaryTerm/기타 + 스키마 미도출 Table/Column(카드 아닌 노드 — terms 클러스터로 표시)
  const addMatch = (sc, tk) => { if (!matchBySchema.has(sc)) matchBySchema.set(sc, new Set()); if (tk) { matchBySchema.get(sc).add(tk); matchTables.add(tk); } };
  (data.nodes || []).forEach((nd) => {
    if (!nd || !nd.key) return;
    if (nd.label === "Table") {
      const sc = _metaSchemaComboOf(nd);
      if (sc && sc !== _META_TERMS_COMBO) addMatch(sc, nd.key);
      else terms.push(nd);   // review MINOR: 스키마 세그먼트 없는 flat scope 테이블 — 소실 방지(terms 로 표시)
    } else if (nd.label === "Column") {
      const tk = _metaColParent(nd.key, nd.fqn);
      const sc = tk ? _metaCatParent(tk, tk.slice(tk.indexOf(":") + 1)) : null;
      if (sc && sc !== _META_TERMS_COMBO) addMatch(sc, tk);
      else terms.push(nd);
    } else if (nd.label === "Routine") {
      // graph-funcproc: 함수·프로시저 매칭 — 소속 스키마 카드는 표시하되 badge **카운트에는 미가산**
      // (§18.8 패널 MINOR: badge 분모 table_count 는 테이블 총계라 Routine 가산 시 N>M 모순).
      // 강조는 searchMatchTables 로 유지 — 카드 펼침 시 schema_tables 가 Routine 을 로드하고 ƒ/⚙ 칩이 커진다.
      const sc = _metaCatParent(nd.key, nd.fqn);
      if (sc && sc !== _META_TERMS_COMBO) { addMatch(sc, null); matchTables.add(nd.key); }
      else terms.push(nd);
    } else if (nd.label === "Schema") { addMatch(nd.key, null); }   // 스키마명 매칭 → 0 매칭이라도 카드 표시(0/전체)
    else terms.push(nd);
  });
  _metaGraph.searchMatch = matchBySchema;
  _metaGraph.searchMatchTables = matchTables;
  // feature-0016 §45: 직접 매칭 노드(테이블/컬럼/용어) key 집합 — 렌더 시 'match' 상태 soft glow 대상(너비 증가 대체).
  const matchNodes = new Set();
  (data.nodes || []).forEach((nd) => { if (nd && nd.key) matchNodes.add(nd.key); });
  _metaGraph.searchMatchNodes = matchNodes;
  // review MAJOR: search_nodes 는 cap(_META_SEARCH_CAP) 로 평면 절단하고 truncated 플래그가 없다 →
  //   응답이 cap 도달이면 스키마별 매칭 카운트는 부분값이므로 badge 에 '+'(≥) 로 표기해 오인 방지.
  const nRaw = (data.nodes || []).length;
  _metaGraph.searchCapped = nRaw >= _META_SEARCH_CAP;
  // 매칭 스키마를 카드로 ingest(전체 총계는 roots 캐시 schemaTotals). auto-expand 하지 않음(카드 유지).
  //   §54③: 신규 추가 key 를 searchAdded 로 추적 — 다음 검색/클리어 때 pristine 만 회수.
  matchBySchema.forEach((set, sc) => {
    const total = _metaGraph.schemaTotals ? _metaGraph.schemaTotals.get(sc) : null;
    const added = _metaGraphIngest([{ label: "Schema", key: sc, name: _metaComboName(sc), fqn: _metaComboName(sc), table_count: (typeof total === "number" ? total : null) }], []);
    (added || []).forEach((k) => _metaGraph.searchAdded.add(k));
  });
  if (terms.length) {
    const added = _metaGraphIngest(terms, []);
    (added || []).forEach((k) => _metaGraph.searchAdded.add(k));
  }
  // 유사도(rel) → 용어 칩 크기 가산. 백엔드 pg_trgm score 우선, 없으면 클라 휴리스틱.
  //   §54③: preserve 모델에는 기존 노드 수천 개가 있으므로 **매칭 노드에만** rel 부여(전역 부여 시
  //   비매칭 칩 폭 왜곡·상세 유사도 배지 오표시). 비-preserve(리셋) 모델은 카드+terms 뿐이라 동치.
  const ql = q.toLowerCase();
  _metaGraph.nodes.forEach((n) => {
    if (matchNodes.has(n.key)) n.rel = (typeof n.score === "number") ? n.score : _metaRelevance(n.name, n.fqn, ql);
    else delete n.rel;
  });
  await _metaG6Apply(preserve ? false : true);   // §54③: preserve 시 카메라·배치 유지
  if (seq !== _metaGraph._opSeq) return;   // await 사이 scope/roots 전환 — 이 검색의 tail(status) 폐기
  if (q !== _metaGraph.lastQuery) return;  // §54③ 패널 MINOR: 클리어는 _opSeq 무-bump — stale 검색 tail 은 lastQuery 로 폐기
  _metaGraphSyncAnalysisMarkers(scope);
  // §54③: preserve 시 첫 매칭 렌더 노드로 부드러운 팬(fit 없이) — 하이라이트 가시화.
  if (preserve && matchNodes.size) {
    const first = Array.from(matchNodes).find((k) => _metaRenderedIdFor(k));
    if (first) _metaGraphAnimateFocus(first, seq);
  }
  const nSchemas = matchBySchema.size;
  const capNote = _metaGraph.searchCapped ? " · 결과 상한(부분 카운트, 검색어를 좁혀 정확도↑)" : "";
  // §54② 패널 MINOR: 매칭에 Routine 이 있는데 ƒ/⚙ 표시 필터가 꺼져 있으면 비가시 원인 안내.
  const anyHiddenRoutineMatch = (data.nodes || []).some((nd) => nd && nd.label === "Routine"
    && _metaGraph.hiddenKinds.has((nd.routine_type === "function") ? "function" : "procedure"));   // 재검증 NIT: kind 별 대조(과잉 발화 방지)
  const hiddenNote = anyHiddenRoutineMatch
    ? " ※ 매칭된 함수/프로시저 일부는 표시 필터로 숨김 상태 — 툴바 ƒ/⚙ 토글을 켜세요." : "";
  if (!nRaw) _metaGraphStatus("검색 결과 없음.");
  else if (nSchemas === 0) _metaGraphStatus(`'${q}' — 용어·기타 ${terms.length}개 매칭(해당 스키마 테이블 없음).${capNote}${hiddenNote}`);
  else _metaGraphStatus(`'${q}' — 스키마 ${nSchemas}개 매칭. 카드 badge = 매칭/전체 테이블. 카드 클릭으로 펼쳐 매칭 테이블(앰버 글로우)을 확인.${capNote}${hiddenNote}`);
}

// 선택 강조: 모델 selected 갱신 + 이전/현재 노드 state 만 갱신(전체 rebuild 없이 가벼움).
function _metaGraphSetSelected(key) {
  const g = _metaGraph.graph;
  const prev = _metaGraph.selected;
  _metaGraph.selected = key || null;
  if (!g) return;
  // §57.6: 인접 집합을 **setElementState 이전에** 갱신 — 새 선택 노드의 즉시 상태(sig)가 구 fa 로
  //   계산돼 'dimmed+selected' 로 밝혀지지 않는 창(사용자 실측: 선택했는데 흐림)을 제거. rebuild 가
  //   busy 로 밀려도 클릭한 노드와 이전 노드의 상태 전환은 setElementState 로 즉시 반영된다.
  // reltrace-colnav(사용자 결정 2026-07-10): 하이라이트 기준 키는 _metaFocusKeyFor 로 해소 —
  //   모델 밖 컬럼(미펼침 테이블의 컬럼) 선택 시 소속 테이블로 폴백(상위 종속 객체 하이라이트).
  //   선택 상태(_metaGraph.selected)는 원 키(컬럼) 그대로. _metaG6Build 재산출과 동일 규칙(양쪽 일치).
  const _faKey = _metaFocusKeyFor(_metaGraph.selected);
  _metaGraph.focusAdj = _faKey ? _metaFocusAdjacency(_faKey) : null;
  // graph-perf-bg fix: _metaApplyState 경유 — busy 보존 + _stateCache signature 동기화(명령형 writer 가 캐시를 stale 로 남기지 않음).
  if (prev && prev !== key && _metaGraph.nodes.has(prev)) _metaApplyState(prev);
  if (key && _metaGraph.nodes.has(key)) _metaApplyState(key);
  // §57.8(의도 우선 재설계): 선택 전환은 **무조건 1회 전체 bake** — 사용자가 "무엇을 선택했는지"를
  //   보는 것이 최우선이므로, 전역 시각 상태(dim·엣지·라벨)는 이 bake 가 원자적으로 재구성한다.
  //   과거 (had||fa) 게이트 + busy 재시도 체인(12×500ms 포기)은 stale busy 하나로 전 경로가
  //   fail-closed 돼 dim 이 영구 고착됐다(사용자 실측 "무너진 상태 유지"). bake 는 직렬화·busy
  //   보존(§57.8 _metaG6Apply)이라 유예할 이유가 없다. 위 setElementState 는 즉시 피드백용.
  try { _metaG6Apply(false); } catch (_) {}
}

// 테이블 key 에 (모델상) 컬럼 노드가 있으면 true — 펼침 상태의 단일 소스.
//   graph-perf-bg: 전 노드 O(N) 선형 스캔(매 Table 클릭·토글마다 호출) → colsByTable 인덱스 O(1) 조회.
//   인덱스는 _metaGraphIngest(추가)·_metaGraphCollapse(제거)·_metaGraphResetModel(초기화) 세 경로에서만 갱신.
function _metaTableHasCols(key) {
  return (_metaGraph.colsByTable.get(key) || 0) > 0;
}

// 단일 클릭: 그래프 구조는 그대로 두고 상세 카드만 갱신(1-hop 으로 컬럼·직접관계·용어).
// graphux7(#1) + graph-navfilter(§54①): 상세 패널 방문 이력(뒤로/앞으로) — view-typed 엔트리
//   {v:"node"|"cluster"|"rel", k:key} 로 노드 상세뿐 아니라 클러스터 상세·관계 상세도 되짚는다.
const _META_HIST_CAP = 50;
function _metaGraphHistoryRecord(key, view) {
  if (!key || _metaGraph._histNav) return;              // 뒤로/앞으로 네비 중 재기록 금지
  const v = view || "node";
  const h = _metaGraph.detailHist;
  const cur = h[_metaGraph.detailHistIdx];
  if (cur && cur.k === key && cur.v === v) return;      // 같은 화면 연속 재선택 — 중복 억제
  h.splice(_metaGraph.detailHistIdx + 1);               // 앞으로 분기 절단(새 방문이 forward 이력을 덮음)
  h.push({ v, k: key });
  if (h.length > _META_HIST_CAP) h.shift();             // 상한 초과 시 오래된 앞부분 제거
  _metaGraph.detailHistIdx = h.length - 1;
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryGo(dir) {
  const ni = _metaGraph.detailHistIdx + dir;
  if (ni < 0 || ni >= _metaGraph.detailHist.length) return;
  _metaGraph.detailHistIdx = ni;
  const ent = _metaGraph.detailHist[ni];
  _metaGraph._histNav = true;                           // 각 진입 함수의 Record(첫 await 이전 동기 구간)가 재기록하지 않게
  try {
    // 클러스터 복원은 반드시 ById — Local 은 모델-로컬이라 중심보기(resetModel) 후 빈 목록을 렌더.
    if (ent.v === "cluster") _metaGraphShowClusterDetailById(ent.k);
    else if (ent.v === "rel") _metaGraphShowRelations(ent.k);
    else _metaGraphShowDetail(ent.k);
  } finally { _metaGraph._histNav = false; }
  // 카메라 재현(fire-and-forget) — 미렌더(접힘/모델 제거)면 skip, 패널은 API 재조회로 복원됨.
  if (_metaRenderedIdFor(ent.k)) {
    const seq = _metaGraph._opSeq;
    _metaGraphAnimateFocus(ent.k, seq);
  }
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryReset() {
  _metaGraph.detailHist = [];
  _metaGraph.detailHistIdx = -1;
  _metaGraph._histNav = false;
  _metaGraphHistoryUpdateUI();
}
function _metaGraphHistoryUpdateUI() {
  const nav = document.getElementById("metadataGraphDetailNav");
  if (!nav) return;
  const h = _metaGraph.detailHist, i = _metaGraph.detailHistIdx;
  if (h.length <= 1) { nav.hidden = true; return; }     // 0~1개면 네비 의미 없음 — 숨김
  nav.hidden = false;
  const back = document.getElementById("metaGraphDetailBack");
  const fwd = document.getElementById("metaGraphDetailFwd");
  const label = document.getElementById("metaGraphDetailNavLabel");
  if (back) back.disabled = i <= 0;
  if (fwd) fwd.disabled = i >= h.length - 1;
  if (label) label.textContent = `${i + 1}/${h.length}`;
}

async function _metaGraphShowDetail(key) {
  if (!_metaGraph.graph || !key) return;
  _metaGraph.lastDetailKey = key;
  _metaGraphHistoryRecord(key);   // graphux7(#1): 방문 이력 기록(뒤로/앞으로 네비 중이면 no-op).
  _metaGraphStatus("상세 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "상세 조회 실패");
    return;
  }
  _metaGraphSetSelected(key);
  const self = (data.nodes || []).find((x) => x.key === key) || { key, name: key };
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  const nb = Math.max(0, (data.nodes || []).length - 1);
  _metaGraphStatus(`상세: ${self.name || key} · 이웃 ${nb}개 (더블클릭 = 관계 확장 · 우클릭 = 상호작용 메뉴)`);
}

// graph-reltrace ②③: 관계 클릭 → **대상 테이블·컬럼으로 그래프 추적**.
//   상세 패널/관계 상세/AI 능동 분석 결과의 관계 행이 공통으로 호출한다. 대상 테이블을 이웃과 함께
//   화면에 가져오고(스키마 펼침·관계 엣지 로드), 컬럼을 전개해 **대상 컬럼을 강조+카메라 focus** 한다.
//   기존 "상대 노드 상세만 교체"(showDetail)와 달리 사용자가 연결을 실제 화면에서 따라가게 한다.
async function _metaGraphTraceRelation(targetKey) {
  if (!_metaGraph.graph || !targetKey) return;
  // review MINOR: 대상이 컬럼/테이블이 아닌 노드(용어 GlossaryTerm 등)면 추적(테이블·컬럼 강조)이
  //   의미 없으므로 상세 보기로 라우팅. "관계 상세" 의 연관 용어 행이 trace 로 넘어오던 오라우팅 해소.
  const tgtNode = _metaGraph.nodes.get(targetKey);
  if (tgtNode && tgtNode.label && tgtNode.label !== "Table" && tgtNode.label !== "Column") {
    return _metaGraphShowDetail(targetKey);
  }
  // review MINOR: 컬럼 판정은 **node label 우선**(세그먼트≥3 은 3-part fqn 테이블에서 오판 가능) —
  //   모델에 label 이 있으면 그것으로, 없으면(집계 대상 미로드) 세그먼트 수 휴리스틱 폴백.
  const idx = String(targetKey).indexOf(":");
  const segs = idx >= 0 ? String(targetKey).slice(idx + 1).split(".") : [];
  const looksColumn = tgtNode ? (tgtNode.label === "Column") : (segs.length >= 3);
  const tableKey = looksColumn ? (_metaColParent(targetKey, tgtNode && tgtNode.fqn) || targetKey) : targetKey;
  // 1) 대상 테이블을 이웃과 함께 화면에 가져오고 스키마 펼침 + 카메라 이동 (REFERENCES 엣지도 로드).
  await _metaGraphExpand(tableKey);
  // 2) 대상 테이블 컬럼 전개(펼침 전용) — 컬럼까지 추적 가능하게(이웃 응답에 컬럼이 이미 오면 no-op).
  if (!_metaTableHasCols(tableKey)) { try { await _metaGraphToggleColumns(tableKey); } catch (_) { /* graceful */ } }
  // 3) 대상 컬럼 강조 + 카메라 focus (렌더된 경우). 미렌더(컬럼 introspect 불가 등)면 테이블 강조 유지.
  const focusKey = (looksColumn && _metaRenderedIdFor(targetKey)) ? targetKey : tableKey;
  _metaGraphSetSelected(focusKey);
  const seq = _metaGraph._opSeq;
  try { await _metaGraphAnimateFocus(focusKey, seq); } catch (_) { /* graceful */ }
  const nm = (_metaGraph.nodes.get(focusKey) || {}).name || focusKey;
  _metaGraphStatus(`관계 추적 → ${nm} (대상 테이블·컬럼 강조).`);
}

// graphux7(#2): 관계 행 단일 클릭 = 카메라 이동만(상세 패널 유지). 대상이 렌더돼 있으면 그 노드로,
//   접힌 스키마면 그 스키마 카드로 카메라를 팬(+렌더된 경우 선택 강조). 상세 패널은 바꾸지 않는다 — 전환은 더블클릭.
// reltrace-colnav(사용자 요청 2026-07-10): 대상 컬럼이 **소속 테이블이 아직 펼쳐지지 않아 미렌더**여도
//   "화면에 없음" 오류로 죽지 않는다 — 소속 테이블(또는 접힌 스키마 카드)로 승격해 카메라가 그 위치를
//   바라보게 하고(펼치진 않음 — 펼침은 더블클릭), 선택 상태는 **대상 컬럼 키**로 둔다(펼쳐 렌더돼 있으면 컬럼
//   하이라이트, 미렌더면 _metaGraphSetSelected 가 하이라이트를 소속 테이블로 폴백 → 더블클릭 펼침 시 그 컬럼이
//   이어서 선택). 조상조차 미렌더(스키마 미로드·§67 뷰포트 컬링)일 때만 안내 메시지(오류 톤 아님 — 더블클릭 유도).
function _metaGraphPanToRelation(targetKey) {
  if (!_metaGraph.graph || !targetKey) return;
  const direct = _metaRenderedIdFor(targetKey);            // 렌더 노드, 접힌 스키마면 카드(SC:)
  const focusEl = direct || _metaRenderedAncestorFor(targetKey);   // 컬럼 미렌더 시 소속 테이블/스키마 카드로 승격
  if (!focusEl) { _metaGraphStatus("대상이 아직 화면에 로드되지 않았습니다 — 더블클릭하면 펼쳐 상세로 전환합니다."); return; }
  // 선택은 대상(컬럼/테이블) 키 기준. (a) 자기 자신이 렌더됐거나 (b) 미렌더 컬럼이 소속 테이블/카드로 승격된 경우
  //   대상 키를 선택 — 펼쳐 렌더돼 있으면 노드 하이라이트, 미렌더면 선택 상태만 기록 + 하이라이트는 소속 테이블
  //   폴백(_metaGraphSetSelected). 접힌 스키마 카드(SC:)로만 승격된 경우(대상=스키마)는 기존대로 선택 없이 팬만.
  const renderedSelf = _metaGraph.renderedIds && _metaGraph.renderedIds.has(targetKey);
  if (renderedSelf || !direct) _metaGraphSetSelected(targetKey);
  const seq = _metaGraph._opSeq;
  _metaGraphAnimateFocus(focusEl, seq);   // 승격된 렌더 요소(노드/카드) 내부 해소 후 카메라 팬
  const nm = (_metaGraph.nodes.get(targetKey) || {}).name || _metaKeyDisplayNode(targetKey).name || targetKey;
  _metaGraphStatus(direct
    ? `→ ${nm} 로 카메라 이동 (더블클릭 = 상세 패널 전환).`
    : `→ ${nm} 소속 테이블로 카메라 이동 · 선택됨 (더블클릭 = 펼쳐 상세 전환).`);
}
// graphux7(#2): 관계 행 클릭 라우팅 — 단일=카메라 이동만, 더블=상세 전환(+대상을 화면에 가져오기).
//   짧은 타이머(260ms)로 단일/더블 구분: 더블클릭이면 예약된 단일(카메라) 취소 후 전환만 실행.
//   키보드(Enter/Space)=상세 전환(commit — 키보드는 '더블' 표현이 어려워 실질 네비게이션을 기본으로).
function _metaGraphBindRelRow(r, key) {
  if (!r || !key) return;
  let timer = null;
  r.addEventListener("click", (ev) => {
    if (ev) ev.stopPropagation();
    if (timer) { clearTimeout(timer); timer = null; }
    timer = setTimeout(() => { timer = null; _metaGraphPanToRelation(key); }, 260);
  });
  r.addEventListener("dblclick", (ev) => {
    if (ev) ev.stopPropagation();
    if (timer) { clearTimeout(timer); timer = null; }
    _metaGraphTraceRelation(key);
  });
  r.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); _metaGraphTraceRelation(key); }
  });
}
// graph-reltrace ②③: 컨테이너 내 `.amgr-trace[data-trace]` 행에 클릭/키보드 바인딩(공용, graphux7#2 단일/더블 라우팅).
function _metaGraphBindTraceRows(el) {
  if (!el) return;
  el.querySelectorAll(".amgr-trace[data-trace]").forEach((r) => {
    _metaGraphBindRelRow(r, r.getAttribute("data-trace"));
  });
}

// reldedup(graph-detail): _metaGraphRelTraceRowsHTML 제거 — 유일 소비처였던 AI 박스 '연결 관계 추적'
//   flat 목록이 상단 컬럼 섹션과 중복이라 삭제되면서 이 헬퍼도 orphan 이 됐다. 컬럼별·방향별 추적 행은
//   _metaGraphRenderDetail 의 relRow/dirGroup 이 담당한다(더 풍부: 방향 그룹·의미 툴팁).

// 테이블 단일 클릭 = **자신의 컬럼 인라인 펼침(펼침 전용)**. 이미 펼쳐졌으면 no-op(버그① — 클릭으론 안 접힘).
//   접힘: "−" 컨트롤(_metaGraphCollapse). 그래프 컬럼(HAS_COLUMN) 없으면 information_schema 즉석조회(introspect).
async function _metaGraphToggleColumns(key) {
  if (!_metaGraph.graph || !key) return;
  const node = _metaGraph.nodes.get(key);
  if (!node || node.label !== "Table") return;
  if (_metaTableHasCols(key)) return;   // 이미 펼침 — 클릭으로 접지 않음(접기는 "−" 컨트롤). O(1) 인덱스.
  // graph-perf-bg: 논블로킹 — busy 상태를 먼저 페인트(과거 dead-frozen 구간 제거)한 뒤 무거운 fetch·재구성.
  //   seq 토큰을 await(fetch·yield) 경계마다 대조해 그 사이 다른 조작이 시작됐으면 폐기(stale 렌더 방지).
  const seq = ++_metaGraph._opSeq;
  const nm = node.name || key;
  _metaGraphStatus("컬럼 조회 중…");
  _metaSetBusy(key, true, seq);
  await _metaYieldPaint();
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }   // 폐기 — busy 소유 op 일 때만 해제(후속 op 가 rebuild 없이 끝나도 busy 잔류 방지)
  try {
    let data;
    try { data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`); }
    catch (_) { data = { nodes: [], edges: [] }; }
    if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
    const respHasCols = (data.edges || []).some((e) => e && e.type === "HAS_COLUMN" && e.source === key);
    if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
    let note = "";
    if (!respHasCols && !_metaGraph.introspected.has(key)) {
      try {
        const col = await apiFetch(`/api/admin/metadata/graph/columns?node=${encodeURIComponent(key)}`);
        if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
        if (col && col.introspected && (col.nodes || []).length) {
          _metaGraph.introspected.add(key);
          data.nodes = (data.nodes || []).concat(col.nodes);
          data.edges = (data.edges || []).concat(col.edges || []);
        } else if (col && !col.introspected && col.reason) {
          note = ` (${col.reason})`;
        }
      } catch (_) { /* graceful */ }
    }
    // 이 테이블 소속 컬럼만(이웃 테이블 컬럼 제외).
    const colNodes = (data.nodes || []).filter((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
    _metaGraphIngest(colNodes, []);
    if (colNodes.length > 0) {
      _metaGraph.expanded.add(key);
      await _metaG6Apply(false);   // fit=false — 제자리 펼침(버그② — 카메라 점프·재확산 없음).
      _metaSetBusy(key, false, seq);   // §57.8: busy 는 bake 로 보존 — 소유 op 가 직접 해제
      _metaGraphStatus(`${nm} 컬럼 ${colNodes.length}개 펼침 — "−" 버튼으로 접기`);
    } else {
      _metaSetBusy(key, false, seq);   // rebuild 없는 경로 — busy 직접 해제(소유 op)
      _metaGraphStatus(`${nm} — 펼칠 컬럼 없음${note}`);
    }
  } catch (err) {
    _metaSetBusy(key, false, seq);
    _metaGraphStatus("컬럼 펼침 오류: " + ((err && err.message) || err));
  }
}

// graph-initview: 스키마 카드 → combo 펼침(per-schema lazy 로드). 반환 상태로 후속(클러스터 상세) 게이팅.
//   "expanded"(펼침 완료) | "already"(이미 펼침) | "empty"(테이블 0) | "failed"(로드 실패) | "stale"(세대 폐기) | "blocked".
//   opts.seq: 부모 op(LoadRoots silent) 세대 상속 — 자체 bump 없이 그 세대로 stale 판정.
//   사용자 클릭 경로는 새 op 세대(++_opSeq)로 시작해 in-flight 이전 조작을 폐기(graph-perf-bg 패턴).
async function _metaGraphExpandSchema(key, opts) {
  if (!_metaGraph.graph || !key) return "blocked";
  const silent = !!(opts && opts.silent);
  // 2차 검증 fix(V-B): scope 전환 fetch 대기 중 화면에 남은 이전 scope 카드 클릭 차단 — 현재 scope 소속만 진행.
  const cidx = key.indexOf(":");
  const kscope = cidx >= 0 ? key.slice(0, cidx) : "";
  if (!kscope || kscope !== (adminState.metadata.scopeKey || "")) return "blocked";
  let sn = _metaGraph.nodes.get(key);
  // 1차 리뷰 fix(MAJOR-1): 검색/이웃 자동펼침 combo 는 Schema 노드 없이 만들어질 수 있다(응답이 테이블만
  // 반환) — 접은 뒤 카드 재클릭이 죽지 않게 Schema 노드를 합성 삽입(위 scope 가드 통과 시에만).
  if (!sn) {
    sn = { key, label: "Schema", name: _metaComboName(key), fqn: _metaComboName(key) };
    _metaGraph.nodes.set(key, sn);
  }
  if (sn.label !== "Schema") return "blocked";
  if (_metaGraph.schemaExpanded.has(key)) return "already";   // 클릭으로 접지 않음(접기는 "−")
  if (_metaGraph.schemaLoading.has(key)) return "blocked";    // 1차 리뷰 fix(MINOR-4): 카드 연타 이중 fetch 차단
  const seq = (opts && opts.seq != null) ? opts.seq : ++_metaGraph._opSeq;
  const nm = _metaComboName(key);
  let note = "";
  let freshResp = false;
  if (!_metaGraph.schemaLoaded.has(key)) {
    _metaGraph.schemaLoading.add(key);
    if (!silent) {
      _metaGraphStatus(`${nm}: 테이블 로딩…`);
      _metaSetBusy(key, true, seq);   // 카드(SC:)에 busy 표시 — _metaApplyState 가 렌더드 id 로 매핑
      await _metaYieldPaint();
      if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); _metaGraph.schemaLoading.delete(key); return "stale"; }
    }
    let data;
    try {
      data = await apiFetch(`/api/admin/metadata/graph?scope=${encodeURIComponent(kscope)}&schema=${encodeURIComponent(key)}`);
    } catch (err) {
      _metaGraph.schemaLoading.delete(key);
      _metaSetBusy(key, false, seq);
      if (!silent && seq === _metaGraph._opSeq) _metaGraphStatus((err && err.message) || "스키마 테이블 로드 실패");
      return "failed";
    }
    _metaGraph.schemaLoading.delete(key);
    // 2차 검증 fix(V-A): await 사이 다른 reset/조작이 세대를 올렸으면 이 응답은 stale — ingest 없이 폐기
    // (이전 scope 응답이 새 모델에 병합되는 교차 스코프 오염을 원천 차단).
    if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return "stale"; }
    _metaGraphIngest(data.nodes || [], data.edges || []);
    if (data.truncated) { _metaGraph.schemaTruncated.add(key); note = " · 표시 상한 도달 — 나머지는 검색으로 탐색"; }
    // 1차 리뷰 fix(MINOR-3, 혼합버전): 구 백엔드는 ?schema= 를 몰라 scope_roots(mode!=schema_tables)로 응답 —
    // 이때 loaded 마킹하면 cap 밖 스키마가 영구 펼침 불능. 정식 응답에만 마킹(아래 cnt>0 조건과 결합).
    freshResp = (data.mode === "schema_tables");
  }
  let cnt = 0;
  // graph-funcproc(§18.8 패널 MAJOR): Routine 도 콘텐츠 — 함수·프로시저만 있는 스키마(테이블 0)가
  // '빈 스키마' 로 오판돼 영구 펼침 불능(Routine 도달 불가)이 되지 않게 카운트에 포함.
  _metaGraph.nodes.forEach((x) => { if ((x.label === "Table" || x.label === "Routine") && _metaCatParent(x.key, x.fqn) === key) cnt += 1; });
  // 2차 검증 fix(V-F): 테이블 확보 시에만 loaded 굳힘 — 빈 스키마는 re-sync 후 재클릭이 다시 조회.
  if (freshResp && cnt > 0) _metaGraph.schemaLoaded.add(key);
  if (cnt === 0) {
    _metaSetBusy(key, false, seq);
    if (!silent && seq === _metaGraph._opSeq) _metaGraphStatus(`${nm}: 빈 스키마(표시할 테이블·함수 없음)${note}`);
    return "empty";
  }
  _metaGraph.schemaExpanded.add(key);
  if (silent) return "expanded";   // 호출측(LoadRoots)이 apply+fit — 이중 렌더 방지
  await _metaG6Apply(false);       // 제자리 원칙(ADR-004 ②) — 전체 fit 없이.
  _metaSetBusy(key, false, seq);   // §57.8: busy 는 bake 로 보존 — 소유 op 가 직접 해제
  try { await _metaGraph.graph.focusElement(key, false); } catch (_) {}   // shelf 재배치 대비 시야 고정(무애니)
  _metaGraphStatus(`${nm}: 테이블·함수 ${cnt}개 펼침 — "−" 로 접기, 테이블 클릭=컬럼${note}`);
  return "expanded";
}

// graph-initview: 스키마 combo "−" 접기 — 카드로 복귀(모델 유지, 렌더 게이팅만 해제 → 재펼침 무-refetch).
function _metaGraphCollapseSchema(key) {
  if (!_metaGraph.graph || !key) return;
  if (!_metaGraph.schemaExpanded.has(key)) return;
  _metaGraph.schemaExpanded.delete(key);
  _metaG6Apply(false);
  _metaGraphStatus(`'${_metaComboName(key)}' 스키마를 접었습니다 — 카드를 클릭하면 다시 펼쳐집니다.`);
}

// graph-initview: 카드 클릭 경로용 클러스터 상세 — 방금 lazy 로드된 모델 데이터로 로컬 렌더(추가 fetch 0,
// 상태줄 미접촉 — 펼침 완료 메시지 보존). combo:click 은 기존 API 기반 상세 유지. 2차 검증 fix(V-G):
// cap 절단 스키마는 카드 배지의 실 카운트(table_count)를 총계로 표기해 배지↔패널 모순 제거.
function _metaGraphShowClusterDetailLocal(comboId) {
  if (!comboId) return;
  _metaGraph.lastDetailKey = comboId;
  _metaGraphHistoryRecord(comboId, "cluster");   // §54①: 복원은 Go 가 ById(API+모델 폴백)로 수행.
  const nm = _metaComboName(comboId);
  const tables = [];
  let childCols = 0;
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n);
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  tables.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const snode = _metaGraph.nodes.get(comboId);
  const total = (snode && typeof snode.table_count === "number" && snode.table_count > tables.length)
    ? snode.table_count : null;
  const truncated = _metaGraph.schemaTruncated.has(comboId);
  _metaGraphRenderClusterDetail(nm, nm, tables, tables.length, childCols, total, truncated, comboId);
}

// "−" 컨트롤 접기 — 이 테이블의 컬럼 노드(+containment 엣지) 모델에서 제거 + 재조회 재허용.
//   graph-rel-layout(§18.8 패널 MAJOR): **REFERENCES 는 보존** — 관계 데이터는 배치 순서(_metaRelAdjacency)와
//   접힌 테이블 간 관계 표시(graph-reltrace renderEndpoint 승격)의 입력이라, 접기 제스처가 지우면 (a) 전면
//   재셔플(펼침-불변 계약 위반) (b) 관계선 소실이 재펼침(ToggleColumns 는 엣지 미재조회)으로도 복원 불가.
function _metaGraphCollapse(key) {
  if (!_metaGraph.graph || !key) return;
  const node = _metaGraph.nodes.get(key);
  const nm = (node && node.name) || key;
  const toDel = [];
  _metaGraph.nodes.forEach((n) => { if (n.label === "Column" && _metaColParent(n.key, n.fqn) === key) toDel.push(n.key); });
  if (!toDel.length) return;
  const delSet = new Set(toDel);
  toDel.forEach((k) => _metaGraph.nodes.delete(k));
  _metaGraph.edges.forEach((e, id) => { if (e.type !== "REFERENCES" && (delSet.has(e.source) || delSet.has(e.target))) _metaGraph.edges.delete(id); });
  _metaGraph.expanded.delete(key);
  _metaGraph.colsByTable.delete(key);   // graph-perf-bg: 컬럼 전부 제거 → 인덱스 카운트 해제(O(1) hasCols 정합).
  if (_metaGraph.introspected) _metaGraph.introspected.delete(key);
  _metaG6Apply(false);
  _metaGraphStatus(`'${nm}' 테이블 컬럼을 접었습니다 — 테이블을 클릭하면 다시 펼쳐집니다.`);
}

// 더블 클릭: 이웃(관계) 그래프로 확장. depth=N-hop 이웃을 모델에 병합.
//   depthOverride: 컨텍스트 메뉴 hop chip 의 1회성 깊이 — 툴바 select 는 건드리지 않는다(review).
async function _metaGraphExpand(key, depthOverride) {
  if (!_metaGraph.graph || !key) return;
  _metaGraph.lastDetailKey = key;
  const depthSel = document.getElementById("metadataGraphDepth");
  const depth = depthOverride || (depthSel ? depthSel.value : "2");
  // graph-perf-bg: 논블로킹 — busy 페인트 후 무거운 이웃 조회·재구성. seq 토큰으로 stale 폐기.
  const seq = ++_metaGraph._opSeq;
  _metaGraphStatus("이웃 조회 중…");
  _metaSetBusy(key, true, seq);
  // graph-dblclick-latency: 앵커는 이미 렌더돼 있으므로 카메라 팬을 fetch·rebuild 를 기다리지 않고 **즉시** 시작(fire-and-forget).
  //   적응형 follow 라 재빌드로 앵커가 이동해도 최종 위치로 수렴 — 더블클릭↔팬 시작 사이의 ~350ms 텀 제거. seq 로 폐기.
  _metaGraphAnimateFocus(key, seq);
  await _metaYieldPaint();
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=${encodeURIComponent(depth)}`);
  } catch (err) {
    _metaSetBusy(key, false, seq);
    _metaGraphStatus((err && err.message) || "이웃 조회 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
  // 미분석 테이블은 그래프에 컬럼(HAS_COLUMN)이 없어 즉석조회(introspect) 병합.
  let introspectNote = "";
  const selfNode = (data.nodes || []).find((x) => x.key === key);
  const respHasCols = (data.edges || []).some((e) => e && e.type === "HAS_COLUMN" && e.source === key);
  if (!_metaGraph.introspected) _metaGraph.introspected = new Set();
  const anchorHasCols = _metaTableHasCols(key);
  if (selfNode && selfNode.label === "Table" && !respHasCols && !anchorHasCols && !_metaGraph.introspected.has(key)) {
    try {
      const col = await apiFetch(`/api/admin/metadata/graph/columns?node=${encodeURIComponent(key)}`);
      if (seq !== _metaGraph._opSeq) { _metaSetBusy(key, false, seq); return; }
      if (col && col.introspected && (col.nodes || []).length) {
        _metaGraph.introspected.add(key);
        data.nodes = (data.nodes || []).concat(col.nodes);
        data.edges = (data.edges || []).concat(col.edges || []);
        introspectNote = ` · 컬럼 ${col.nodes.length}개 즉석조회(introspect)`;
      } else if (col && !col.introspected && col.reason) {
        introspectNote = ` · 컬럼 없음: ${col.reason}`;
      }
    } catch (_) { /* graceful */ }
  }
  _metaGraph.mode = "neighbor";
  _metaGraph.lastQuery = "";
  _metaGraph.nodes.forEach((n) => { delete n.rel; });   // 이웃 탐색 진입 — 검색 유사도 크기 해제
  _metaGraphIngest(data.nodes || [], data.edges || []);
  // graph-initview: 이웃 응답 테이블/컬럼/함수의 스키마 자동 펼침(카드 게이팅에서 이웃이 숨지 않게) + 앵커 스키마.
  //   graph-funcproc(§18.8 패널 MINOR): Routine 포함 — 접힌 타 스키마의 Routine 이웃·ROUTINE_USES 엣지 비가시 방지.
  (data.nodes || []).forEach((nd) => {
    if (nd && (nd.label === "Table" || nd.label === "Column" || nd.label === "Routine")) {
      const sc = _metaCatParent(nd.key, nd.fqn);
      if (sc) _metaGraph.schemaExpanded.add(sc);
    }
  });
  {
    const an = _metaGraph.nodes.get(key);
    if (an) {
      const sc = _metaSchemaComboOf(an);
      if (sc && sc !== _META_TERMS_COMBO) _metaGraph.schemaExpanded.add(sc);
    }
  }
  const anchorCols = (data.nodes || []).some((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
  if (anchorCols) _metaGraph.expanded.add(key);
  // graph-initview(A3): 이웃 확장은 전체-fit 대신 앵커 중심 focus. graph-dblclick-cam2: manual rAF tween 으로 부드럽게.
  //   graph-dblclick-latency: 그 tween 을 위(busy 직후)에서 이미 fire-and-forget 으로 시작함 — 적응형 follow 라 이 rebuild 로
  //   앵커가 이동해도 자동 수렴. 여기서 재호출 불필요(중복 tween 방지).
  await _metaG6Apply(false);   // (진행 중인 follow tween 이 새 위치로 이어서 수렴)
  _metaSetBusy(key, false, seq);   // §57.8: busy 는 bake 로 보존 — 소유 op 가 직접 해제
  // graph-rel-layout(§18.8 패널 MINOR): fetch(이웃+introspect) 합계가 tween MAXMS(1.2s)를 넘으면 follow tween 이
  //   앵커 '구 위치'에 수렴·종료한 뒤 rebuild 가 일어난다 — 관계 재배치로 앵커가 다른 shelf 행으로 원거리 이동
  //   가능하므로, tween 이 이미 죽었으면 무애니 focusElement 1회로 시야 보정(살아 있으면 adaptive follow 가 수렴).
  if (_metaGraph._focusLive !== seq) {
    try { const fel = _metaRenderedIdFor(key); if (fel) await _metaGraph.graph.focusElement(fel, false); } catch (_) {}
  }
  _metaGraphSyncAnalysisMarkers(key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  _metaGraphSetSelected(key);
  const self = selfNode || { key, name: key };
  _metaGraphHistoryRecord(key, "node");   // §54①: seq 가드 뒤 성공-기반 기록(실패/스테일 확장 미기록).
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  _metaGraphStatus(`노드 ${(data.nodes || []).length} · 관계 ${(data.edges || []).length}${introspectNote}`);
}

// graph-ctxmenu: "이 노드 중심으로 보기" — 모델을 리셋하고 앵커의 N-hop 이웃만 남긴다.
//   expand(기존 화면에 병합·누적)와 달리 화면을 앵커 중심 서브그래프로 정리해, 스키마를 모르는
//   사용자가 관심 노드의 연관 관계만 집중해 보게 한다. 분석 마커는 서버 상태에서 재적용.
async function _metaGraphFocus(key) {
  _metaGraph._searchBase = null;   // §54③ 재검증 MINOR: 중심 보기 = 새 컨텍스트 — stale 검색 base 폐기
  if (!_metaGraph.graph || !key) return;
  const depthSel = document.getElementById("metadataGraphDepth");
  const depth = depthSel ? depthSel.value : "2";
  _metaGraph.mode = "neighbor";
  _metaGraph.lastQuery = "";
  _metaGraph.lastDetailKey = key;
  const si = document.getElementById("metadataGraphSearch");
  if (si) si.value = "";   // review: 검색어 잔존 시 focus 서브그래프와 상태 불일치
  // graph-perf-bg 규약 정합: reset 경로는 resetModel(_opSeq 증가) 직후 세대 캡처 → await 후 대조.
  //   fetch 를 reset 앞에 두면 fetch 동안 발생한 다른 reset 화면을 이 continuation 이 되돌린다(stale-render).
  _metaGraphResetModel();
  const seq = _metaGraph._opSeq;
  _metaGraphStatus("중심 보기 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=${encodeURIComponent(depth)}`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "중심 보기 조회 실패");
    return;
  }
  if (seq !== _metaGraph._opSeq) return;   // await 사이 다른 reset(loadRoots/search/scope) — stale 폐기
  _metaGraphIngest(data.nodes || [], data.edges || []);
  const anchorCols = (data.nodes || []).some((x) => x && x.label === "Column" && _metaColParent(x.key, x.fqn) === key);
  if (anchorCols) _metaGraph.expanded.add(key);
  await _metaG6Apply(true);
  _metaGraphSyncAnalysisMarkers(key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  _metaGraphSetSelected(key);
  const self = (data.nodes || []).find((x) => x.key === key) || { key, name: key };
  _metaGraphHistoryRecord(key, "node");   // §54①: seq 가드 뒤 성공-기반 기록(중심보기).
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || []);
  const nm = (_metaGraph.nodes.get(key) || {}).name || key;
  _metaGraphFocusChip(nm);   // review MAJOR-3: 부분 그래프임을 지속 표시 + '전체 보기' 복귀
  _metaGraphStatus(`${nm} 중심 ${depth}-hop — 노드 ${(data.nodes || []).length} · 관계 ${(data.edges || []).length} ('전체 보기'로 복귀)`);
}

// review MAJOR-3: 중심 보기 지속 표시 칩 — 캔버스 좌상단에 "🎯 중심 보기: <노드>" + "✕ 전체 보기"(roots 복귀).
//   name=null 이면 제거. roots 로드·검색 진입 시 자동 해제(전체/검색 컨텍스트로 전환됨).
function _metaGraphFocusChip(name) {
  _metaGraph._focusName = name || null;   // §54③ 패널: 중심 보기 상태 미러(검색→클리어 시 칩 복원용)
  const canvas = document.getElementById("metadataGraphCanvas");
  if (!canvas) return;
  let chip = document.getElementById("metaGraphFocusChip");
  if (!name) { if (chip) chip.remove(); return; }
  if (!chip) {
    chip = document.createElement("div");
    chip.id = "metaGraphFocusChip";
    chip.className = "amgr-focus-chip";
    canvas.appendChild(chip);
  }
  chip.replaceChildren();
  const t = document.createElement("span");
  t.textContent = `🎯 중심 보기: ${name}`;
  chip.appendChild(t);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "✕ 전체 보기";
  btn.title = "중심 보기를 끝내고 데이터소스 전체 그래프로 복귀합니다";
  btn.addEventListener("click", () => _metaGraphLoadRoots());
  chip.appendChild(btn);
}

// feature-0016 ERD-card: Column 의 소속 Table (scope:...fqn 에서 마지막 세그먼트 제거). 미상 시 null.
function _metaColParent(key, fqn) {
  if (!key) return null;
  const idx = key.indexOf(":");
  if (idx < 0) return null;
  const scope = key.slice(0, idx);
  const f = fqn || key.slice(idx + 1);
  if (!f) return null;
  const parts = f.split(".");
  if (parts.length < 2) return null;      // 최소 table.column
  return scope + ":" + parts.slice(0, -1).join(".");   // 마지막(컬럼) 세그먼트 제거 → 테이블 fqn
}

// reltrace-tabledetail(review): 모델에 없는 관계 끝점(컬럼)의 표시용 노드 파생 — scope 접두 제거한 fqn +
//   leaf 명. schema_tables 는 REFERENCES 끝점 Column 노드를 nodes 에 싣지 않아, 모델-병합 관계행이
//   raw scoped key(`scope:db.t.c`)로 뜨던 UX 저하를 해소(테이블-레벨/컬럼-레벨 읽기 쉬운 이름).
function _metaKeyDisplayNode(key) {
  const s = String(key || "");
  const idx = s.indexOf(":");
  const fqn = idx >= 0 ? s.slice(idx + 1) : s;
  const segs = fqn.split(".");
  const label = segs.length >= 3 ? "Column" : (segs.length === 2 ? "Table" : "Schema");
  return { key, label, fqn, name: segs[segs.length - 1] || fqn };
}

// API nodes/edges → 모델(_metaGraph.nodes/edges Map) 병합. 반환: 새로 추가된 노드 key 배열.
//   HAS_TABLE/HAS_COLUMN 은 containment(컬럼 fqn 으로 부모 도출)라 엣지로 저장하지 않는다.
function _metaGraphIngest(nodes, edges) {
  const added = [];
  (nodes || []).forEach((n) => {
    if (!n || !n.key) return;
    if (n.label === "Schema") {
      const ex = _metaGraph.nodes.get(n.key);
      if (!ex) {
        _metaGraph.nodes.set(n.key, { key: n.key, label: "Schema", name: n.name || n.fqn || n.key, fqn: n.fqn || "",
          table_count: (typeof n.table_count === "number") ? n.table_count : null });
        added.push(n.key);   // §54③ 패널 MAJOR: 카드 미반환 시 searchAdded 가 항상 비어 pristine 회수가 dead code
      } else if (typeof n.table_count === "number") { ex.table_count = n.table_count; }   // graph-initview: 카드 배지
      return;
    }
    const ord = (typeof n.ordinal === "number" && isFinite(n.ordinal)) ? n.ordinal : null;
    const existing = _metaGraph.nodes.get(n.key);
    const rec = existing || { key: n.key };
    rec.label = n.label || rec.label || "Node";
    rec.name = n.name || n.fqn || rec.name || n.key;
    rec.fqn = n.fqn || rec.fqn || "";
    rec.description = (n.description != null) ? n.description : (rec.description || "");
    rec.source = n.source || rec.source || "";
    if (ord != null) rec.ordinal = ord;
    if (typeof n.score === "number") rec.score = n.score;
    // graph-funcproc(ADR-016): 함수·프로시저 속성 보존(칩 접두 ƒ/⚙ + 상세 파라미터 표시).
    if (n.routine_type) rec.routine_type = n.routine_type;
    if (n.params != null && n.params !== "") rec.params = n.params;
    // graph-product-cat(§43): Product/Datasource 부가 필드 보존(제품 라벨 개수 · datasource scope drill).
    if (n.scope_key != null) rec.scope_key = n.scope_key;
    if (typeof n.datasource_count === "number") rec.datasource_count = n.datasource_count;
    // Phase C(semantic-embed): 의미 클러스터 id/라벨 보존 → _metaSimGroups 가 be: 그룹으로 소비(affix 폴백).
    if (n.cluster_id != null) rec.cluster_id = n.cluster_id;
    if (n.cluster_label != null) rec.cluster_label = n.cluster_label;
    if (!existing) {
      _metaGraph.nodes.set(n.key, rec); added.push(n.key);
      // graph-perf-bg: 새 Column 노드면 소속 테이블의 colsByTable 카운트 증가(_metaTableHasCols O(1) 단일소스).
      if (rec.label === "Column") {
        const tk = _metaColParent(rec.key, rec.fqn);
        if (tk) _metaGraph.colsByTable.set(tk, (_metaGraph.colsByTable.get(tk) || 0) + 1);
      }
    }
  });
  (edges || []).forEach((e) => {
    if (!e || !e.source || !e.target) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_ROUTINE") return;   // containment
    const id = `${e.source}|${e.type}|${e.target}`;
    if (_metaGraph.edges.has(id)) return;
    _metaGraph.edges.set(id, { id, source: e.source, target: e.target, type: e.type || "",
      status: e.status || "", edge_source: e.edge_source || "",
      cardinality: e.cardinality || "",   // reltrace-tabledetail(review): 모델-병합 관계행의 [cardinality] 배지 보존
      relation_type: e.relation_type || "",   // graph-funcproc: ROUTINE_USES read/write(+유사어 관계형)
      cross_ds: (e.cross_ds != null && e.cross_ds !== "") ? 1 : 0,   // crossds-rel: 교차DB 엣지 표식(빌드 스타일/배지)
      // §57: SCHEMA_REF(스키마-쌍 집계) count 계열 보존 — 카드간 연결선 굵기/라벨의 데이터 소스.
      count: (e.count != null && e.count !== "") ? Number(e.count) : "",
      ref_count: (e.ref_count != null && e.ref_count !== "") ? Number(e.ref_count) : "",
      use_count: (e.use_count != null && e.use_count !== "") ? Number(e.use_count) : "",
      weight: (e.weight != null && e.weight !== "") ? Number(e.weight) : "" });
  });
  return added;
}

// 컬럼 정렬 비교자(모델 객체): ordinal 숫자 우선(미상=MAX), 동률 name.
function _metaGraphColCmp(a, b) {
  const na = (typeof a.ordinal === "number" && isFinite(a.ordinal)) ? a.ordinal : Number.MAX_SAFE_INTEGER;
  const nb = (typeof b.ordinal === "number" && isFinite(b.ordinal)) ? b.ordinal : Number.MAX_SAFE_INTEGER;
  if (na !== nb) return na - nb;
  return String(a.name || "").localeCompare(String(b.name || ""));
}

function _metaGraphRenderDetailEmpty() {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  el.innerHTML = '<div class="admin-detail-empty"><p>검색 후 노드를 클릭하면 해당 항목의 <strong>설명·컬럼·관계·연관 용어</strong>를 한 곳에서 봅니다.</p><p class="admin-meta-detail-note">노드를 <strong>우클릭</strong>하면 상세 보기·관계 상세·관계 확장(1~3-hop)·중심 보기 등 상호작용 메뉴가 열립니다.</p></div>';
}

// feature-0016: 관계 엣지의 신뢰 상태 배지 — FK 는 무표시, 추정(candidate)/신뢰(trusted) 구분.
// "이 연결이 정말 올바른지" 를 사람이 한눈에 판단하도록 weight 를 함께 노출.
function _metaEdgeTrustBadge(e) {
  if (!e || e.edge_source === "fk_introspect") return "";
  const w = (e.weight != null && e.weight !== "") ? Number(e.weight) : null;
  const ws = (w != null && !isNaN(w)) ? " w=" + w.toFixed(2) : "";
  if (e.status === "candidate") {
    return ` <span class="admin-meta-graph-trust admin-meta-graph-trust-candidate" title="검증 전 추정 관계 — 사용/프로브로 강화·감쇠">추정${ws}</span>`;
  }
  if (e.status === "trusted") {
    return ` <span class="admin-meta-graph-trust admin-meta-graph-trust-trusted" title="검증된 신뢰 관계">신뢰${ws}</span>`;
  }
  return "";
}

// reldetail-colexpand ④: 관계 hover 툴팁용 **의미 분석** 텍스트(즉시 조합 — LLM 지연 없음).
//   방향(참조함/참조받음)·연결 컬럼·근거(대화학습/FK/추정)·신뢰도를 해석해 "이 관계가 무엇을
//   뜻하는지" 를 문장으로 설명한다. dir: "out"(self 가 상대를 참조) | "in"(상대가 self 를 참조).
//   selfEndFqn/otherFqn 은 표시용 fqn(scope 접두 제거). native title 속성값으로 쓰여 다중 줄로 표시.
function _metaRelSemanticTip(e, dir, selfEndFqn, otherFqn) {
  const src = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "미상";
  const w = (e.weight != null && e.weight !== "") ? Number(e.weight) : null;
  const wPct = (w != null && !isNaN(w)) ? Math.round(w * 100) + "%" : null;
  const trust = e.status === "trusted"
    ? "검증된 신뢰 관계"
    : (e.status === "candidate"
        ? ("추정 관계" + (wPct ? " (신뢰도 " + wPct + " — 실사용·프로브로 강화·감쇠)" : ""))
        : (e.edge_source === "fk_introspect" ? "FK 스키마 선언 관계" : "관계"));
  // 방향 문장: 물리적 참조 방향을 자연어로.
  const arrowSent = dir === "out"
    ? (selfEndFqn + " 이(가) " + otherFqn + " 을(를) 참조합니다.")
    : (otherFqn + " 이(가) " + selfEndFqn + " 을(를) 참조합니다.");
  // 근거별 의미 해석.
  const meaningBy = {
    fk_introspect: "데이터베이스에 선언된 외래키(FK)로, 두 테이블 행이 이 컬럼으로 확정 연결됩니다.",
    conversation: "사용자 대화의 실제 JOIN 질의에서 학습된 연결 — 실무에서 함께 조회되는 관계입니다.",
    inferred: "컬럼 명명 규칙으로 추론된 암묵 관계 — 실데이터 겹침 프로브로 신뢰도가 조정됩니다.",
    llm_insight: "AI 인사이트가 제안한 연관 관계입니다.",
    manual: "관리자가 수동 등록한 관계입니다.",
  };
  const meaning = meaningBy[e.edge_source] || "두 컬럼이 연관됩니다.";
  const card = e.cardinality ? ("\n관계 형태(cardinality): " + e.cardinality) : "";
  return "관계 의미 분석\n" + arrowSent + "\n근거: " + src + " · " + trust + card + "\n" + meaning;
}

// 통합 엔티티 카드 — 클릭 노드의 이웃을 카테고리(컬럼·관계·용어)로 묶어 표시.
function _metaGraphRenderDetail(self, nodes, edges) {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  // 항목1: 이 노드가 검색 결과라 그래프에 rel(유사도)이 실려 있으면 상세 헤더에 % 명시.
  const selfScopeKey = (self.key && self.key.indexOf(":") >= 0)
    ? self.key.slice(0, self.key.indexOf(":")) : (adminState.metadata.scopeKey || "common");
  let relPct = null;
  try {
    const gn = _metaGraph.nodes.get(self.key);
    // 검색 컨텍스트(lastQuery 활성)일 때만 유사도 배지 — 확장/리셋 후 stale 배지 방지.
    if (_metaGraph.lastQuery && gn && typeof gn.rel === "number") relPct = Math.round(gn.rel * 100);
  } catch (_) {}
  const byKey = {};
  (nodes || []).forEach((n) => { if (n && n.key) byKey[n.key] = n; });
  // counter 노드명: fetch(byKey) → 모델(_metaGraph.nodes) → key 파생(scope 접두 제거 fqn) 순 폴백.
  //   raw scoped key 노출 방지(review LOW) — 모델에 없는 병합 끝점도 읽기 쉬운 fqn 으로 표시.
  const nm = (k) => (byKey[k] && (byKey[k].fqn || byKey[k].name)) || ((_metaGraph.nodes.get(k) || {}).fqn) || ((_metaGraph.nodes.get(k) || {}).name) || _metaKeyDisplayNode(k).fqn || k;
  const selfKey = self.key;
  // 컬럼(HAS_COLUMN out), 관계(REFERENCES), 용어(GlossaryTerm), 부모 스키마(HAS_TABLE in)
  const columns = [], refs = [], terms = [], routineUses = [];
  const refSeen = new Set();
  (edges || []).forEach((e) => {
    if (!e) return;
    if (e.type === "HAS_COLUMN" && e.source === selfKey && byKey[e.target]) columns.push(byKey[e.target]);
    if (e.type === "REFERENCES") { refs.push(e); refSeen.add((e.source || "") + "|" + (e.target || "")); }
    if (e.type === "DESCRIBES" && byKey[e.source] && byKey[e.source].label === "GlossaryTerm") terms.push(byKey[e.source]);
    // graph-funcproc(ADR-016): 함수·프로시저 ↔ 테이블 사용 관계 — Routine self=사용 테이블 / Table self=사용 루틴.
    if (e.type === "ROUTINE_USES" && (e.source === selfKey || e.target === selfKey)) routineUses.push(e);
  });
  (nodes || []).forEach((n) => { if (n && n.label === "GlossaryTerm" && n.key !== selfKey && !terms.includes(n)) terms.push(n); });
  // graph-reltrace(tabledetail): 테이블 단일클릭 상세는 depth=1 이라 컬럼의 REFERENCES(테이블 기준
  //   2-hop)가 fetch 에 없어 "관계" 섹션이 비었다. 관계는 스키마 펼침 시 이미 모델(_metaGraph.edges)에
  //   로드돼 있으므로, self(테이블이면 자기 컬럼 포함)에 닿는 REFERENCES 를 모델에서 병합한다(dedup).
  //   컬럼 단일클릭(depth=1 에 REFERENCES 있음)은 fetch 로 이미 채워지고 여기서 dedup 로 중복 방지.
  {
    const isSelfEnd = (k) => k === selfKey || _metaColParent(k, (byKey[k] || {}).fqn || (_metaGraph.nodes.get(k) || {}).fqn) === selfKey;
    _metaGraph.edges.forEach((e) => {
      if (!e || e.type !== "REFERENCES" || e.status === "broken") return;
      if (!isSelfEnd(e.source) && !isSelfEnd(e.target)) return;
      const id = (e.source || "") + "|" + (e.target || "");
      if (refSeen.has(id)) return;
      refSeen.add(id); refs.push(e);
    });
  }

  // graph-reltrace(review MAJOR): 관계 행 data-trace 속성값(노드 키)에 쓰이므로 따옴표까지 이스케이프
  //   (DB 식별자에 인용부호 가능 — 속성 탈출 방어).
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || self.key)}</strong>${relPct != null ? ` <span class="admin-meta-graph-relbadge" title="검색어 유사도(pg_trgm)">유사도 ${relPct}%</span>` : ""} <button type="button" class="amgr-link" id="metaGraphRelBtn" title="이 노드의 관계를 방향·신뢰도·근거별로 자세히 봅니다 (노드 우클릭 메뉴에서도 열림)">🔗 관계 상세</button> <button type="button" class="amgr-link" id="metaGraphFocusSelBtn" style="margin-left:0" title="선택한 이 노드로 그래프 카메라를 이동합니다(구조·선택 유지, 팬만).">🎯 이 노드로 이동</button></div>`);
  if (self.fqn) parts.push(`<div class="admin-meta-graph-fqn">${esc(self.fqn)}</div>`);
  if (self.description) parts.push(`<p class="admin-meta-graph-desc">${esc(self.description)}</p>`);
  else parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">(설명 없음 — 해당 서브탭에서 추가)</p>`);
  // graph-funcproc(ADR-016): 함수·프로시저 상세 — 유형 + introspect 된 파라미터 시그니처.
  //   graph-navfilter(§54⑤): 파라미터를 수평 한 줄 대신 **수직 목록**으로(컬럼 리스트 amgr-collist 관례 재사용).
  if (self.label === "Routine") {
    const mn = _metaGraph.nodes.get(selfKey) || {};
    const rt = self.routine_type || mn.routine_type || "";
    const rparams = self.params || mn.params || "";
    const plist = _metaRoutineParamList({ params: rparams });
    parts.push(`<div class="admin-meta-graph-sec"><h4>${_metaRoutineIcon(rt)} ${esc(_metaRoutineKo(rt))} · 파라미터 (${plist.length})</h4>` +
      (plist.length
        ? `<ul class="amgr-collist">${plist.map((p) => `<li class="amgr-col amgr-col-plain"><code>${esc(p)}</code></li>`).join("")}</ul>`
        : `<p class="admin-meta-graph-desc admin-meta-graph-muted">파라미터 없음</p>`) + `</div>`);
  }
  // reldetail-colexpand ①②③: 관계를 **소속 컬럼별**로 그룹화하고, 각 컬럼 안에서 참조함(→)/참조받음(←)
  //   을 분리·개수 표기. 관계 있는 컬럼은 아코디언(클릭 시 펼침)으로 관계 행을 노출한다.
  //   self 측 끝점(테이블이면 자기 컬럼, 컬럼이면 자신)을 기준으로 방향을 정한다.
  const selfIsColumn = (self.label === "Column");
  const selfColKey = (k) => {   // 엣지 끝점 k 가 self 소속이면 그 self측 컬럼 키, 아니면 null
    if (selfIsColumn) return (k === selfKey) ? selfKey : null;
    // 테이블 self: 끝점이 self 테이블의 컬럼이면 그 컬럼 키.
    if (k === selfKey) return null;   // 테이블 자신은 컬럼 아님(REFERENCES 끝점은 항상 컬럼)
    return (_metaColParent(k, (byKey[k] || {}).fqn || (_metaGraph.nodes.get(k) || {}).fqn) === selfKey) ? k : null;
  };
  // colKey -> { out:[{e,other}], in:[{e,other}] }
  const colRel = new Map();
  let totOut = 0, totIn = 0;
  const addRel = (colKey, dir, e, other) => {
    if (!colRel.has(colKey)) colRel.set(colKey, { out: [], in: [] });
    colRel.get(colKey)[dir].push({ e, other });
    if (dir === "out") totOut += 1; else totIn += 1;
  };
  refs.forEach((e) => {
    const sc = selfColKey(e.source), tc = selfColKey(e.target);
    // review MAJOR: intra-table self-FK(양끝이 모두 self 컬럼, 예: employees.manager_id→employees.id)는
    //   source 컬럼의 참조함(→)과 target 컬럼의 참조받음(←)을 **둘 다** 기록해야 방향별 개수가 정확하다
    //   (else-if 로 out 만 잡으면 참조받음이 누락·totIn 저계상). sc===tc(컬럼 자기참조)면 out 만(중복 방지).
    if (sc) addRel(sc, "out", e, e.target);        // self 컬럼이 source → 참조함
    if (tc && tc !== sc) addRel(tc, "in", e, e.source);   // self 컬럼이 target → 참조받음
    // sc·tc 모두 falsy = self 무관(모델 병합 방어) → 무시.
  });

  const relRow = (item, dir) => {   // 추적 가능 관계 행(툴팁 = 의미 분석)
    const { e, other } = item;
    const arrow = dir === "out" ? "→" : "←";
    const selfEndFqn = dir === "out" ? nm(e.source) : nm(e.target);
    const otherFqn = nm(other);
    const tip = _metaRelSemanticTip(e, dir, selfEndFqn, otherFqn);
    return `<li class="amgr-row amgr-trace" data-trace="${esc(other)}" role="button" tabindex="0" ` +
      `title="${esc(tip)}">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span> <code>${esc(otherFqn)}</code>` +
      `${e.cardinality ? " [" + esc(e.cardinality) + "]" : ""}` +
      `${e.edge_source && e.edge_source !== "fk_introspect" ? " <span class=\"admin-meta-graph-muted\">(" + esc(_META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source) + ")</span>" : ""}` +
      `${_metaEdgeTrustBadge(e)} <span class="amgr-tracehint">🔎 추적</span></div></li>`;
  };
  const dirGroup = (list, dir) => {   // 방향 그룹(참조함/참조받음) + 개수
    if (!list.length) return "";
    const label = dir === "out" ? "참조함" : "참조받음";
    const arrow = dir === "out" ? "→" : "←";
    return `<div class="amgr-dir"><div class="amgr-dir-head"><span class="amgr-arrow">${arrow}</span> ${label} (${list.length})</div>` +
      `<ul class="amgr-list">${list.map((it) => relRow(it, dir)).join("")}</ul></div>`;
  };

  if (columns.length || selfIsColumn) {
    // 전체 관계 요약(방향별 개수).
    const relSummary = (totOut + totIn) > 0
      ? ` <span class="admin-meta-graph-relbadge" title="이 노드의 관계 방향별 개수">관계 ${totOut + totIn} · 참조함 ${totOut} · 참조받음 ${totIn}</span>`
      : "";
    if (selfIsColumn) {
      // 컬럼 상세: 컬럼 자신의 관계를 방향별로 바로 표시(아코디언 불필요).
      const cr = colRel.get(selfKey) || { out: [], in: [] };
      parts.push(`<div class="admin-meta-graph-sec"><h4>관계${relSummary}</h4>`);
      if (cr.out.length || cr.in.length) {
        parts.push(`<p class="admin-meta-detail-note">행 hover 시 관계 의미, 클릭 시 대상 추적.</p>`);
        parts.push(dirGroup(cr.out, "out"));
        parts.push(dirGroup(cr.in, "in"));
      } else {
        parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다.</p>`);
      }
      parts.push(`</div>`);
    } else {
      // 테이블 상세: 컬럼 목록 — 관계 있는 컬럼은 아코디언(클릭 펼침).
      parts.push(`<div class="admin-meta-graph-sec"><h4>컬럼 (${columns.length})${relSummary}</h4>`);
      parts.push(`<p class="admin-meta-detail-note">컬럼을 클릭하면 선택되어 상세로 전환되고 그래프에서 강조됩니다. 관계가 있는 컬럼(🔗)은 캐럿(▸)으로 참조함/참조받음 관계를 그 자리에서 펼칠 수 있습니다. 관계 hover=의미, 클릭=대상 추적.</p><ul class="amgr-collist">`);
      columns.slice(0, 80).forEach((c) => {
        const cr = colRel.get(c.key);
        const nOut = cr ? cr.out.length : 0, nIn = cr ? cr.in.length : 0;
        if (!cr || (nOut + nIn) === 0) {
          parts.push(`<li class="amgr-col amgr-col-plain"><button type="button" class="amgr-col-select" data-col="${esc(c.key)}" aria-label="${esc(c.name)} 컬럼 선택" title="컬럼 선택 — 상세로 전환하고 그래프에서 강조"><code>${esc(c.name)}</code>${c.description ? " <span class=\"admin-meta-graph-muted\">— " + esc(c.description) + "</span>" : ""}</button></li>`);
          return;
        }
        parts.push(
          `<li class="amgr-col amgr-col-rel">` +
          `<div class="amgr-col-head">` +
          `<button type="button" class="amgr-col-caret" aria-expanded="false" data-coltoggle="${esc(c.key)}" aria-controls="amgr-colbody-${esc(c.key)}" title="참조 관계 토글" aria-label="참조 관계 토글"><span class="amgr-caret">▸</span></button>` +
          `<button type="button" class="amgr-col-select" data-col="${esc(c.key)}" aria-label="${esc(c.name)} 컬럼 선택" title="컬럼 선택 — 상세로 전환하고 그래프에서 강조">` +
          `🔗 <code>${esc(c.name)}</code>` +
          `<span class="amgr-col-relcount" title="참조함 ${nOut} · 참조받음 ${nIn}">→${nOut} ←${nIn}</span></button>` +
          `</div>` +
          `<div class="amgr-col-body" id="amgr-colbody-${esc(c.key)}" data-colbody="${esc(c.key)}" hidden>${dirGroup(cr.out, "out")}${dirGroup(cr.in, "in")}</div>` +
          `</li>`
        );
      });
      parts.push(`</ul></div>`);
    }
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul>`);
    terms.slice(0, 30).forEach((t) => parts.push(`<li><strong>${esc(t.name)}</strong>${t.description ? " — " + esc(t.description) : ""}</li>`));
    parts.push(`</ul></div>`);
  }
  // graph-funcproc(ADR-016): ROUTINE_USES — Routine 상세엔 "사용 테이블", Table 상세엔 "사용하는 함수·프로시저".
  //   graph-rw-group(사용자 요구): 사용(참조) 관계를 읽기/쓰기(relation_type)로 **그룹 분리**한다 —
  //   평면 목록 + 항목별 읽기/쓰기 꼬리표 대신, 읽기/쓰기 소그룹 헤더(개수)로 묶어 데이터 흐름을
  //   한눈에 구분한다(REFERENCES 방향 그룹 dirGroup 과 동일한 amgr-dir 스타일 재사용). relation_type
  //   "write"=루틴→테이블(씀), 그 외("read"·미상)=테이블→루틴(읽음, 기존 kindKo 기본값과 정합).
  //   각 그룹 30건 상한 + 초과분 "… 외 N건" 명시(기존 combined 30 무음 절단 개선).
  if (routineUses.length) {
    const isRoutineSelf = self.label === "Routine";
    const rtRow = (e) => {
      const other = e.source === selfKey ? e.target : e.source;
      const on = byKey[other] || _metaGraph.nodes.get(other) || {};
      const disp = on.label === "Routine"
        ? `${_metaRoutineIcon(on.routine_type)} ${on.name || nm(other)}` : nm(other);
      return `<li><button type="button" class="amgr-link" data-rtuse="${esc(other)}" title="상세 보기">${esc(disp)}</button></li>`;
    };
    const rtGroup = (list, label) => {   // 읽기/쓰기 소그룹(개수 + 30건 상한 + 초과 명시)
      if (!list.length) return "";
      const rows = list.slice(0, 30).map(rtRow).join("");
      // 초과행은 항목(amgr-link 버튼, 비-박스)과 시각 정합하도록 amgr-row 박스 없이 muted 텍스트 li (적대리뷰 NIT2).
      const more = list.length > 30
        ? `<li class="admin-meta-graph-muted amgr-more">… 외 ${list.length - 30}건</li>` : "";
      return `<div class="amgr-dir"><div class="amgr-dir-head">${label} (${list.length})</div>` +
        `<ul class="amgr-list">${rows}${more}</ul></div>`;
    };
    const rtWrites = routineUses.filter((e) => e.relation_type === "write");
    const rtReads = routineUses.filter((e) => e.relation_type !== "write");
    parts.push(`<div class="admin-meta-graph-sec"><h4>${isRoutineSelf ? "사용 테이블" : "사용하는 함수·프로시저"} (${routineUses.length}) <span class="admin-meta-graph-muted">· 읽기 ${rtReads.length} · 쓰기 ${rtWrites.length}</span></h4>`);
    parts.push(`<p class="admin-meta-detail-note">${isRoutineSelf ? "이 함수·프로시저가 사용하는 테이블을" : "이 테이블을 사용하는 함수·프로시저를"} 읽기/쓰기로 나눠 표시합니다. 행 클릭 = 대상 상세 + 카메라 이동.</p>`);
    parts.push(rtGroup(rtReads, "읽기"));
    parts.push(rtGroup(rtWrites, "쓰기"));
    parts.push(`</div>`);
  }
  // 항목2: AI 능동 분석 섹션 — 버튼으로 트리거(백그라운드 재귀), box 에 진행/결과 렌더.
  //   graph-funcproc(ADR-017, REQ ⑤): 버튼 hover 시 지침 입력 popover(툴팁형) — 입력하면 LLM 이
  //   자율 판단해 분석에 반영. 입력 없이 클릭하면 기존과 동일(지침 없는 분석).
  parts.push(`<div class="admin-meta-graph-sec admin-meta-graph-ai" id="metaGraphAiSec">`);
  parts.push(`<div class="admin-meta-graph-ai-head"><h4>AI 능동 분석</h4><button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiBtn" title="hover: 분석 지침 입력">✨ 능동 분석</button></div>`);
  parts.push(`<div class="admin-meta-ai-pop" id="metaGraphAiPop" hidden>` +
    `<label for="metaGraphAiPrompt">분석 지침 (선택, ≤400자)</label>` +
    `<textarea id="metaGraphAiPrompt" rows="2" maxlength="400" placeholder="예: 결제 흐름 관점에서 연관 테이블 위주로 분석"></textarea>` +
    `<div class="admin-meta-ai-pop-foot"><span class="admin-meta-graph-muted">지침은 AI가 자율 판단해 분석 내용·탐색 방향에 반영합니다.</span>` +
    `<button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiPopGo">✨ 분석 시작</button></div></div>`);
  parts.push(`<div class="admin-meta-graph-ai-box" id="metaGraphAiBox"><span class="admin-meta-graph-muted">이 노드에서 시작해 관련 노드를 AI가 재귀적으로 분석합니다(백그라운드).</span></div>`);
  parts.push(`</div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // 버튼 바인딩(+hover 지침 popover) + 기존 분석 결과가 있으면 즉시 로드.
  _metaGraphBindAiPopover(self.key, selfScopeKey);
  // graph-focus-selected: 상세 패널의 선택 노드로 카메라만 팬한다(그래프 구조·선택 상태 불변 —
  //   _metaGraphPanToRelation 패턴 재사용). 렌더 안 된 노드(접힌 스키마 등)면 안내만 하고 팬 skip.
  const focusSelBtn = document.getElementById("metaGraphFocusSelBtn");
  if (focusSelBtn) focusSelBtn.addEventListener("click", () => {
    const key = self.key;
    if (!_metaGraph.graph || !key) return;
    const rel = _metaRenderedIdFor(key);   // 렌더 노드, 접힌 스키마면 카드(SC:)
    if (!rel) { _metaGraphStatus("이 노드가 현재 화면에 없습니다 — 더블클릭하면 펼쳐 상세로 전환합니다."); return; }
    const seq = _metaGraph._opSeq;
    _metaGraphAnimateFocus(key, seq);       // key→렌더 요소 내부 해소 후 카메라 팬(+판독 줌 클램프)
    const nm = (_metaGraph.nodes.get(key) || {}).name || self.name || key;
    _metaGraphStatus(`→ ${nm} 로 카메라 이동.`);
  });
  const relBtn = document.getElementById("metaGraphRelBtn");
  if (relBtn) relBtn.addEventListener("click", () => _metaGraphShowRelations(self.key));
  // graph-funcproc: 사용 테이블/사용 루틴 행 클릭 → 대상 상세로 이동.
  // graph-rtuse-camera(사용자 요구): 클릭 시 상세 전환에 더해 **카메라도 대상 노드로 이동**한다
  //   (REFERENCES 관계 행의 _metaGraphPanToRelation 재사용). 대상이 렌더돼 있으면 그 노드로 팬+선택,
  //   접힌 스키마 등 미렌더면 팬 없이 안내만(graceful). pan 을 먼저(동기 카메라·선택) 호출하고 상세
  //   전환(async)을 이어 호출 — 상세 재렌더가 이 버튼을 교체하기 전에 카메라 이동이 예약된다.
  el.querySelectorAll("[data-rtuse]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.getAttribute("data-rtuse");
      if (!k) return;
      _metaGraphPanToRelation(k);   // + 카메라 이동(신규)
      _metaGraphShowDetail(k);      // 상세 패널 전환(기존)
    });
  });
  _metaGraphBindTraceRows(el);   // graph-reltrace ②: 관계 행 클릭 → 대상 추적
  // graph-detail-colsel: 상세 패널 컬럼 클릭 → 캔버스의 컬럼 노드 클릭과 동일한 선택.
  //   _metaGraphShowDetail 재사용 — 선택 상태(_metaGraph.selected) 세팅 + 그래프 강조 재베이크 +
  //   상세를 그 컬럼 뷰로 전환. plain·관계 컬럼 공통. data-col = 컬럼 노드 키.
  el.querySelectorAll(".amgr-col-select[data-col]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const k = btn.getAttribute("data-col");
      if (k) _metaGraphShowDetail(k);
    });
  });
  // reldetail-colexpand ①: 컬럼 아코디언 토글 — 캐럿 클릭 시 그 컬럼의 관계 펼침/접힘(선택과 분리).
  //   body 는 캐럿의 조상 li 내 .amgr-col-body 로 찾는다(키의 CSS 특수문자 셀렉터 이스케이프 회피).
  el.querySelectorAll(".amgr-col-caret[data-coltoggle]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const li = btn.closest(".amgr-col-rel");
      const body = li ? li.querySelector(".amgr-col-body") : null;
      const open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      const caret = btn.querySelector(".amgr-caret");
      if (caret) caret.textContent = open ? "▸" : "▾";
      if (body) body.hidden = open;
    });
  });
  _metaGraphLoadNodeAnalysis(self.key);
}

// graph-ctxmenu: 관계 근거(edge_source)·타입 한글 라벨 — 스키마 미숙지 사용자용 신뢰 판단 보조.
const _META_EDGE_SOURCE_KO = {
  fk_introspect: "FK 스키마 선언", inferred: "명명 규칙 추정",
  conversation: "대화 JOIN 학습", llm_insight: "AI 인사이트", manual: "수동 등록",
};
const _META_EDGE_TYPE_KO = {
  REFERENCES: "참조", DESCRIBES: "용어 설명", RELATED_TERM: "유사어",
  USES: "사용", HAS_SCHEMA: "소속", HAS_TABLE: "소속", HAS_COLUMN: "소속",
  HAS_ROUTINE: "소속", ROUTINE_USES: "테이블 사용",   // graph-funcproc(ADR-016)
};

// graph-ctxmenu: 관계 상세 패널 — 선택 노드의 1-hop 관계를 **방향별**(참조함→/참조받음←/연관 용어/
//   주변 관계)로 그룹해 신뢰도(추정/신뢰 + weight)·근거(edge_source)·상대 노드 설명과 함께 나열한다.
//   행 클릭 = 상대 노드 상세로 이동. self 판정은 노드 자신 + (테이블 관점) 자기 컬럼 포함 —
//   컬럼 단위 FK 도 테이블 관계로 묶여 보인다.
async function _metaGraphShowRelations(key) {
  if (!key) return;
  _metaGraph.lastDetailKey = key;
  _metaGraphHistoryRecord(key, "rel");   // §54①: 첫 await 이전(동기 구간) — Go 재기록은 _histNav 가 차단.
  _metaGraphStatus("관계 상세 조회 중…");
  let data;
  try {
    data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(key)}&depth=1`);
  } catch (err) {
    _metaGraphStatus((err && err.message) || "관계 상세 조회 실패");
    return;
  }
  _metaGraphSetSelected(key);
  // graph-reltrace(tabledetail): 테이블 depth=1 은 컬럼 REFERENCES(2-hop) 미포함 → 모델에서 self
  //   (자기 컬럼 포함)에 닿는 REFERENCES 를 병합해 "관계 상세" 도 테이블 관계를 표시(dedup).
  const mNodes = (data.nodes || []).slice();
  const mEdges = (data.edges || []).slice();
  {
    const seen = new Set(mEdges.map((e) => (e.source || "") + "|" + (e.type || "") + "|" + (e.target || "")));
    const nodeKeys = new Set(mNodes.map((n) => n && n.key));
    const isSelfEnd = (k) => k === key || _metaColParent(k, (_metaGraph.nodes.get(k) || {}).fqn) === key;
    _metaGraph.edges.forEach((e) => {
      if (!e || e.type !== "REFERENCES" || e.status === "broken") return;
      if (!isSelfEnd(e.source) && !isSelfEnd(e.target)) return;
      const id = (e.source || "") + "|REFERENCES|" + (e.target || "");
      if (seen.has(id)) return;
      seen.add(id); mEdges.push(e);
      // 병합 엣지의 상대 노드 보강: 모델에 있으면 모델 노드, 없으면(schema_tables 는 REFERENCES 끝점
      //   Column 노드를 안 실음) key 파생 노드로 — raw scoped key 표시·조인컬럼 주석 소실 방지(review LOW).
      [e.source, e.target].forEach((k) => {
        if (!k || nodeKeys.has(k)) return;
        nodeKeys.add(k);
        mNodes.push(_metaGraph.nodes.has(k) ? _metaGraph.nodes.get(k) : _metaKeyDisplayNode(k));
      });
    });
  }
  _metaGraphRenderRelations(key, mNodes, mEdges);
}

function _metaGraphRenderRelations(key, nodes, edges) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const byKey = {};
  (nodes || []).forEach((n) => { if (n && n.key) byKey[n.key] = n; });
  const self = byKey[key] || _metaGraph.nodes.get(key) || { key, name: key, label: "" };
  const nm = (k) => (byKey[k] && (byKey[k].fqn || byKey[k].name)) || k;
  // self 측 판정: 자신 또는 (테이블이면) 자기 소속 컬럼.
  const isSelf = (k) => {
    if (!k) return false;
    if (k === key) return true;
    const nd = byKey[k];
    return _metaColParent(k, nd && nd.fqn) === key;
  };
  const out = [], inn = [], around = [], terms = [];
  const termSeen = new Set();
  (edges || []).forEach((e) => {
    if (!e || !e.type) return;
    if (e.type === "HAS_TABLE" || e.type === "HAS_COLUMN" || e.type === "HAS_SCHEMA" || e.type === "HAS_ROUTINE") return;   // containment 제외(graph-funcproc: 소속 스키마도)
    const sSelf = isSelf(e.source), tSelf = isSelf(e.target);
    if (!sSelf && !tSelf) { around.push(e); return; }   // review: self 무관(이웃-이웃)은 term 이라도 주변 관계
    const other = sSelf ? e.target : e.source;
    const on = byKey[other];
    if ((e.type === "DESCRIBES" || e.type === "RELATED_TERM") && on && on.label === "GlossaryTerm") {
      if (!termSeen.has(other)) { termSeen.add(other); terms.push({ e, node: on }); }
      return;
    }
    if (sSelf) { out.push(e); return; }
    inn.push(e);
  });
  // review MAJOR-1: 앵커 측 조인 컬럼 표기 — 컬럼 단위 FK 에서 "어느 컬럼으로 JOIN 되는가"를 행에 노출.
  //   out: `colname → 상대` · in: `상대 → colname`. 같은 대상으로 가는 FK 2개도 로컬 컬럼으로 구분된다.
  // graph-category(§55 B): 관계 큐레이션 버튼 — REFERENCES 행에 신뢰 승격(✓)·파단(✕). 권한
  //   metadata.table.manage(kb.ingest.manual 묶음 함의) 보유자만. 크로스-DS candidate 는 프로브 검증이
  //   불가해 이 승격이 유일한 신뢰 경로(ADR-019) — trusted 는 승격 버튼 생략(파단만).
  const canCurate = (typeof can === "function") && (can("metadata.table.manage") || can("kb.ingest.manual"));
  const curateBtns = (e) => {
    if (!canCurate || e.type !== "REFERENCES" || !e.source || !e.target) return "";
    const b = [];
    if (e.status !== "trusted") b.push(`<button type="button" class="amgr-cur amgr-cur-trust" data-cur="trust" data-src="${esc(e.source)}" data-tgt="${esc(e.target)}" title="이 관계를 신뢰(trusted)로 승격 — AI 답변 컨텍스트에 주입됩니다">✓ 신뢰</button>`);
    b.push(`<button type="button" class="amgr-cur amgr-cur-break" data-cur="break" data-src="${esc(e.source)}" data-tgt="${esc(e.target)}" title="이 관계를 파단(broken) 처리 — 그래프·AI 컨텍스트에서 제거됩니다">✕ 파단</button>`);
    return `<span class="amgr-curate">${b.join("")}</span>`;
  };
  const row = (e, otherKey, selfEndKey, arrow) => {
    const on = byKey[otherKey] || {};
    const selfEnd = (selfEndKey && selfEndKey !== key) ? (byKey[selfEndKey] || null) : null;
    const localName = selfEnd ? (selfEnd.name || String(selfEndKey).split(".").pop()) : "";
    const srcKo = _META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source || "";
    const typeKo = _META_EDGE_TYPE_KO[e.type] || e.type || "";
    const counter = `<code>${esc(on.fqn || on.name || otherKey)}</code>`;
    const main = arrow === "→"
      ? `${localName ? `<code>${esc(localName)}</code> <span class="amgr-arrow">→</span> ` : ""}${counter}`
      : `${counter}${localName ? ` <span class="amgr-arrow">→</span> <code>${esc(localName)}</code>` : ""}`;
    return `<li class="amgr-row" data-key="${esc(otherKey)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span>${main}` +
      `${e.cardinality ? ` <span class="admin-meta-graph-muted">[${esc(e.cardinality)}]</span>` : ""}${_metaEdgeTrustBadge(e)}${curateBtns(e)}</div>` +
      `<div class="amgr-sub admin-meta-graph-muted">${esc(typeKo)}${srcKo ? " · 근거: " + esc(srcKo) : ""}${on.description ? " — " + esc(on.description) : ""}</div></li>`;
  };
  // review: 60/30건 절단 시 "… 외 N건" 명시(헤더 카운트와 행 수의 침묵 불일치 방지).
  const moreRow = (n) => `<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${n}건 (그래프에 펼치기로 확인)</div></li>`;
  // review: REFERENCES 외 타입이 섞이면 "참조" 대신 중립 라벨.
  const dirLabel = (list, refLabel, neutral) => (list.every((e) => e.type === "REFERENCES") ? refLabel : neutral);
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || key)}</strong> <span class="admin-meta-graph-relbadge">관계 상세</span></div>`);
  if (self.fqn) parts.push(`<div class="admin-meta-graph-fqn">${esc(self.fqn)}</div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">이 노드가 맺은 관계를 방향별로 봅니다 — 참조함 ${out.length} · 참조받음 ${inn.length} · 연관 용어 ${terms.length}${around.length ? ` · 주변 관계 ${around.length}` : ""}. 행을 클릭하면 상대 노드 상세로 이동합니다.</p>`);
  if (out.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>→ ${dirLabel(out, "참조함", "나가는 관계")} (${out.length})</h4><ul class="amgr-list">`);
    out.slice(0, 60).forEach((e) => parts.push(row(e, e.target, e.source, "→")));
    if (out.length > 60) parts.push(moreRow(out.length - 60));
    parts.push(`</ul></div>`);
  }
  if (inn.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>← ${dirLabel(inn, "참조받음", "들어오는 관계")} (${inn.length})</h4><ul class="amgr-list">`);
    inn.slice(0, 60).forEach((e) => parts.push(row(e, e.source, e.target, "←")));
    if (inn.length > 60) parts.push(moreRow(inn.length - 60));
    parts.push(`</ul></div>`);
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul class="amgr-list">`);
    terms.slice(0, 30).forEach(({ e, node }) => {
      parts.push(`<li class="amgr-row" data-key="${esc(node.key)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
        `<div class="amgr-main"><span class="amgr-arrow">◈</span><strong>${esc(node.name || node.key)}</strong></div>` +
        `<div class="amgr-sub admin-meta-graph-muted">${esc(_META_EDGE_TYPE_KO[e.type] || e.type)}${node.description ? " — " + esc(node.description) : ""}</div></li>`);
    });
    if (terms.length > 30) parts.push(moreRow(terms.length - 30));
    parts.push(`</ul></div>`);
  }
  if (around.length) {
    // 앵커에 직접 닿지 않는 이웃-이웃 관계 — 맥락 참고용으로만 접어서 나열(비클릭).
    parts.push(`<div class="admin-meta-graph-sec"><h4>주변 관계 (${around.length})</h4><ul class="amgr-list">`);
    around.slice(0, 20).forEach((e) => parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted"><code>${esc(nm(e.source))}</code> → <code>${esc(nm(e.target))}</code>${_metaEdgeTrustBadge(e)}</div></li>`));
    if (around.length > 20) parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${around.length - 20}건 (관계 확장으로 그래프에서 확인)</div></li>`);
    parts.push(`</ul></div>`);
  }
  if (!out.length && !inn.length && !terms.length) {
    parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다 — FK 미선언 스키마일 수 있습니다. AI 능동 분석·대화 사용이 쌓이면 추정(점선) 관계가 나타납니다.</p>`);
  }
  parts.push(`<div class="amgr-actions"><button type="button" class="btn-secondary" id="amgrExpandBtn" title="이 노드의 이웃을 그래프 화면에 펼칩니다">🕸 그래프에 펼치기</button><button type="button" class="btn-secondary" id="amgrDetailBtn">📋 상세 보기</button></div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  el.querySelectorAll(".amgr-row[data-key]").forEach((r) => {
    // graphux7(#2): 단일=카메라 이동만(상세 유지), 더블=상세 전환(+대상 테이블·컬럼 강조).
    _metaGraphBindRelRow(r, r.getAttribute("data-key"));
  });
  // graph-category(§55 B): 큐레이션 버튼 — 행 클릭(카메라 이동)과 분리(stopPropagation).
  el.querySelectorAll("button.amgr-cur").forEach((b) => {
    b.addEventListener("click", (ev) => {
      ev.stopPropagation(); ev.preventDefault();
      _metaGraphCurateRelation(b.getAttribute("data-cur"), b.getAttribute("data-src"), b.getAttribute("data-tgt"), key);
    });
  });
  const eb = document.getElementById("amgrExpandBtn");
  if (eb) eb.addEventListener("click", () => _metaGraphExpand(key));
  const db = document.getElementById("amgrDetailBtn");
  if (db) db.addEventListener("click", () => _metaGraphShowDetail(key));
  _metaGraphStatus(`관계 상세: ${self.name || key} — 참조함 ${out.length} · 참조받음 ${inn.length} · 용어 ${terms.length}`);
}

// graph-category(§55 A): 카테고리(제품) 밴드 상세 — 제품 정보 + 멤버 스키마(DB) 목록. 행 클릭 = 그 스키마
//   클러스터 상세로 이동. 다제품 스키마는 전 제품을 뱃지로 노출(배정은 대표 제품 — 헤더와 정합).
function _metaGraphShowCategoryDetail(catKey) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el || !catKey) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const label = _metaGraph.catLabelOf.get(catKey) || (catKey === "PC:__none__" ? "미분류" : catKey);
  const members = _metaGraph.catMembers.get(catKey) || [];
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:#8a5a1f">카테고리</span><strong>🗂 ${esc(label)}</strong> <span class="admin-meta-graph-relbadge">제품 카테고리</span></div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">${catKey === "PC:__none__"
    ? "어느 제품의 접근 DB 로도 등록되지 않은 스키마(DB) 묶음입니다. 관리 콘솔 > 제품 > 접근 DB 에 등록하면 해당 제품 카테고리로 배치됩니다."
    : "이 제품의 접근 DB 로 등록된 스키마(DB) 묶음입니다. 헤더 칩 드래그로 밴드 전체 이동, − / + 로 접기/펼치기."}</p>`);
  parts.push(`<div class="admin-meta-graph-sec"><h4>스키마(DB) ${members.length}개</h4><ul class="amgr-list">`);
  members.forEach((cid) => {
    const nm = _metaComboName(cid);
    const plist = _metaGraph.schemaProducts.get(String(nm).toLowerCase()) || [];
    const extras = plist.length > 1 ? ` <span class="admin-meta-graph-muted">(제품 ${plist.map((p) => esc(p.name)).join(", ")})</span>` : "";
    const cnt = _metaGraph.schemaTotals.get(cid);
    parts.push(`<li class="amgr-row" data-cid="${esc(cid)}" role="button" tabindex="0" title="클릭 = 이 스키마 클러스터 상세">` +
      `<div class="amgr-main"><span class="amgr-arrow">▦</span><strong>${esc(nm)}</strong>${typeof cnt === "number" ? ` <span class="admin-meta-graph-muted">· 테이블 ${cnt}</span>` : ""}${extras}</div></li>`);
  });
  parts.push(`</ul></div></div>`);
  el.innerHTML = parts.join("");
  el.querySelectorAll(".amgr-row[data-cid]").forEach((r) => {
    r.addEventListener("click", () => _metaGraphShowClusterDetailById(r.getAttribute("data-cid")));
  });
  _metaGraphStatus(`카테고리: ${label} — 스키마 ${members.length}개`);
}

// graph-category(§55 B): 관계 사람 큐레이션 — 신뢰 승격(trust) / 파단(break). 관계 상세 패널의 행 버튼이
//   호출한다. 성공 시 모델 로컬 반영(trust=status 승급 · break=엣지 제거) + 재렌더. 크로스-DS 후보는
//   프로브 검증 불가라 이 승격이 유일한 신뢰 경로(→ AI 컨텍스트 주입 대상 전환).
async function _metaGraphCurateRelation(action, src, tgt, anchorKey) {
  if (!src || !tgt || (action !== "trust" && action !== "break")) return;
  const label = action === "trust" ? "신뢰 승격" : "파단";
  const nmOf = (k) => { const n = _metaGraph.nodes.get(k); return (n && (n.fqn || n.name)) || k; };
  if (!window.confirm(`이 관계를 ${label} 처리할까요?\n\n${nmOf(src)}\n→ ${nmOf(tgt)}\n\n${action === "trust"
    ? "신뢰(trusted)로 승격되어 AI 답변 컨텍스트에 주입됩니다."
    : "파단(broken) 처리되어 그래프와 AI 컨텍스트에서 제거됩니다."}`)) return;
  _metaGraphStatus(`관계 ${label} 처리 중…`);
  try {
    await apiFetch(`/api/admin/metadata/graph/relationship/curate`, {
      method: "POST", body: JSON.stringify({ action, src, tgt }) });
  } catch (err) {
    _metaGraphStatus((err && err.message) || `관계 ${label} 실패`);
    return;
  }
  // 모델 로컬 반영(다음 로드/이웃확장과도 멱등 — 서버 SSOT 가 정본).
  const toDelete = [];
  _metaGraph.edges.forEach((e, eid) => {
    if (!e || e.type !== "REFERENCES") return;
    const fwd = (e.source === src && e.target === tgt), rev = (e.source === tgt && e.target === src);
    if (!fwd && !rev) return;
    if (action === "trust") { e.status = "trusted"; e.weight = 1.0; }
    else toDelete.push(eid);
  });
  toDelete.forEach((eid) => _metaGraph.edges.delete(eid));
  await _metaG6Apply(false);
  _metaGraphStatus(`관계 ${label} 완료`);
  if (anchorKey) _metaGraphShowRelations(anchorKey);   // 패널 재렌더(뱃지/버튼 갱신)
}

// graph-funcproc(ADR-017, REQ ⑤): 'AI 능동 분석' hover 지침 popover — 툴팁형 입력창.
//   graph-dataflow(UX 재요청): **버튼(또는 popover 자체) hover / 버튼 focus 시에만** 표시한다.
//   이전엔 섹션(제목·결과 box 포함) 전체 hover 로 열려 "버튼 외 UI hover 에도 지침 UI 가 뜨는" 이슈가 있었음 —
//   버튼+popover 로만 트리거를 좁혔다. 버튼→툴팁 이동 중 닫힘은 250ms 지연 hide 로 흡수. Esc 로 닫기.
//   '분석 시작'(또는 지침 입력 후 메인 버튼) → 지침과 함께 분석 트리거. 지침은 세션 내 보존(재열람 prefill).
function _metaGraphBindAiPopover(key, scope) {
  const btn = document.getElementById("metaGraphAiBtn");
  const pop = document.getElementById("metaGraphAiPop");
  const ta = document.getElementById("metaGraphAiPrompt");
  const go = document.getElementById("metaGraphAiPopGo");
  if (!btn) return;
  const promptVal = () => (ta && typeof ta.value === "string" ? ta.value.trim().slice(0, 400) : "");
  const start = () => {
    const p = promptVal();
    _metaGraph.aiPrompt = p;
    if (pop) pop.hidden = true;
    _metaGraphAnalyze(key, scope, p);
  };
  btn.addEventListener("click", start);
  if (!pop || !ta || !go) return;   // popover 마크업 부재(비정상) — 버튼 단독 동작 보존
  if (_metaGraph.aiPrompt) ta.value = _metaGraph.aiPrompt;
  let hideT = null;
  // funcproc-esc-hotfix(PB-0008 라이브 적발): Esc 가 pop 을 닫고 btn.focus() 로 포커스를 돌려주는데,
  // btn 의 focus-show 가 즉시 재열고 show() 가 blur 경로의 hide 타이머까지 취소해 **popover 고착**.
  // Esc 직후 짧은 창(300ms) 동안 show 를 억제해 닫힘을 확정한다(focus 복귀는 유지 — a11y).
  let escClosing = false;
  // graph-dataflow: 툴팁을 viewport 기준 position:fixed 로 띄운다 — 상세 패널(.admin-meta-graph-detail)이
  //   overflow-y:auto 라 in-container absolute 는 하단에서 잘린다(조상 체인 transform 없음 확인 → fixed 유효).
  //   버튼 rect 기준으로 아래(뷰포트 하단 넘치면 위로 flip)·우측 정렬하고, 스크롤/리사이즈 시 재배치한다.
  //   reflow 는 pop 이 DOM 에서 사라지면(상세 재렌더) 자기 리스너를 제거해 누수 방지(self-heal).
  const position = () => {
    const r = btn.getBoundingClientRect();
    const gap = 6;
    const ph = pop.offsetHeight || 120, pw = pop.offsetWidth || 300;
    let top = r.bottom + gap;
    if (top + ph > window.innerHeight - 8) top = Math.max(8, r.top - gap - ph);   // 아래 넘침 → 위로 flip
    let left = r.right - pw;                                                       // 버튼 오른쪽 끝에 정렬
    if (left < 8) left = 8;
    if (left + pw > window.innerWidth - 8) left = Math.max(8, window.innerWidth - 8 - pw);
    pop.style.top = top + "px"; pop.style.left = left + "px"; pop.style.right = "auto";
  };
  const reflow = () => {
    if (!document.body.contains(pop)) { stopTrack(); return; }   // 상세 재렌더로 stale — self-cleanup
    if (!pop.hidden) position();
  };
  const startTrack = () => { window.addEventListener("scroll", reflow, true); window.addEventListener("resize", reflow); };
  function stopTrack() { window.removeEventListener("scroll", reflow, true); window.removeEventListener("resize", reflow); }
  const doHide = () => { pop.hidden = true; stopTrack(); };
  const show = () => {
    if (escClosing) return;
    if (hideT) { clearTimeout(hideT); hideT = null; }
    pop.hidden = false;
    position();       // 표시 직후 버튼 기준 좌표 산정(offsetHeight 확정 위해 un-hide 후)
    startTrack();
  };
  const hideSoon = () => {
    if (hideT) clearTimeout(hideT);
    hideT = setTimeout(() => { if (document.activeElement !== ta) doHide(); }, 250);
  };
  btn.addEventListener("mouseenter", show);
  btn.addEventListener("focus", show);
  btn.addEventListener("mouseleave", hideSoon);
  // 버튼→툴팁 이동 시 유지: popover 자체 hover 는 show, 이탈은 hideSoon(250ms). 섹션(제목·결과 box)
  //   hover 는 더 이상 트리거하지 않는다 — 버튼 외 UI hover 시 지침 UI 가 뜨던 이슈 해소.
  pop.addEventListener("mouseenter", show);
  pop.addEventListener("mouseleave", hideSoon);
  ta.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      escClosing = true;
      doHide();   // graph-dataflow F2: 숨김+scroll/resize 리스너 해제(누수 방지) — pop.hidden=true 단독 대체
      try { btn.focus(); } catch (_) {}
      setTimeout(() => { escClosing = false; }, 300);
    }
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); start(); }
  });
  ta.addEventListener("blur", hideSoon);
  go.addEventListener("click", start);
}

// 항목2: 선택 노드에 대한 AI 능동 분석 트리거(POST → run 생성) + 진행 폴링 시작.
//   prompt(ADR-017): hover popover 로 입력한 사용자 지침(선택) — run 에 저장돼 LLM 이 자율 반영.
async function _metaGraphAnalyze(key, scope, prompt) {
  if (!key) return;
  const box = document.getElementById("metaGraphAiBox");
  const sc = scope || (key.indexOf(":") >= 0 ? key.slice(0, key.indexOf(":")) : (adminState.metadata.scopeKey || "common"));
  // graphux7(#4): 중복 큐잉 방어(프론트 1차) — 같은 노드 POST 가 이미 in-flight 면 재요청 안 함(연타 동시 POST
  //   경합 차단; 백엔드 lease-dedup 이 방금 만든 run 을 아직 못 보는 창을 프론트에서 먼저 막는다). 상호작용은 유지.
  if (_metaGraph._analyzePending.has(key)) {
    if (box) box.innerHTML = '<span class="admin-meta-graph-muted">이미 요청을 처리 중입니다 — 중복 요청을 방지합니다. 잠시만 기다려 주세요.</span>';
    return;
  }
  _metaGraph._analyzePending.add(key);
  if (box) box.innerHTML = '<span class="admin-meta-graph-muted">AI 능동 분석 요청 중…</span>';
  const body = { node_key: key, scope_key: sc };
  const p = (typeof prompt === "string") ? prompt.trim().slice(0, 400) : "";
  if (p) body.prompt = p;
  let res;
  try {
    res = await apiFetch(`/api/admin/metadata/graph/analyze`, {
      method: "POST", body: JSON.stringify(body),
    });
  } catch (err) {
    if (box) box.innerHTML = `<span class="admin-meta-graph-muted">시작 실패: ${(err && err.message) || "오류"}</span>`;
    return;
  } finally {
    _metaGraph._analyzePending.delete(key);   // 이 노드 POST 완료(성공/실패) — in-flight 해제. 이후 중복 차단은 백엔드 lease-dedup(reused).
  }
  if (res && res.run_id) {
    // graphux7(#4): 백엔드가 검증한 결과(reused) 로 사용자 메시지를 분기 — 새 큐잉 vs 이미 진행 중을 명확히 구분.
    const reused = !!res.reused;
    // graphux5-progress: 진행 패널을 즉시 표시(닫힘 상태 해제) — 이후 폴링이 상세를 라이브 갱신.
    const panel = document.getElementById("metadataGraphProgress");
    if (panel) {
      delete panel.dataset.dismissed; panel.style.display = "";
      panel.innerHTML = reused
        ? '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">이미 진행 중 — 새로 큐잉하지 않고 기존 분석 현황을 표시합니다.</span></div>'
        : '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">시작 중… 관련 노드를 재귀 탐색합니다.</span></div>';
    }
    if (box) {
      if (reused) {
        const pr = res.progress || {};
        const prTxt = (typeof pr.done === "number" && typeof pr.enqueued === "number") ? ` (진행 ${pr.done}/${pr.enqueued})` : "";
        box.innerHTML = `<span class="admin-meta-graph-muted">이미 이 노드의 AI 능동 분석이 진행 중입니다${prTxt} — 중복 큐잉하지 않고 진행 현황을 위 패널에서 갱신합니다.</span>`;
      } else {
        box.innerHTML = '<span class="admin-meta-graph-muted">분석 중(백그라운드)… 진행 현황은 위 진행 패널에서 확인하세요.</span>';
      }
    }
    _metaGraphPollRun(res.run_id, key);
  }
}

// routine-dbanalysis(§53): DB(스키마) 단위 AI 능동 분석 — dry_run 집계 → confirm(비용 가시화) →
//   실행 → 기존 run 진행 패널(_metaGraphPollRun) 연동. 시드는 미분석 테이블만(only_missing, cap 은
//   백엔드 AGENT_NODE_ANALYSIS_SCHEMA_CAP). reused/noop 은 노드 분석과 동일 parity 안내.
async function _metaGraphAnalyzeSchema(schemaKey) {
  if (!schemaKey) return;
  const nm = _metaComboName(schemaKey);
  if (_metaGraph._analyzePending.has(schemaKey)) {   // 연타 동시 POST 차단(노드 분석과 동일 가드)
    // §18.8 MINOR: 대형 스키마 dry_run 지연 중 재클릭이 무반응이면 기능이 죽은 것처럼 보임 — 노드 경로 parity 피드백.
    _metaGraphStatus(`${nm}: 이미 요청을 처리 중입니다 — 중복 요청을 방지합니다. 잠시만 기다려 주세요.`);
    return;
  }
  _metaGraph._analyzePending.add(schemaKey);
  // §18.8 MAJOR: 사용자가 진행 패널을 ✕ 로 닫은 뒤(dataset.dismissed) 같은 run 을 재트리거하면 안내는
  //   "진행 패널에서 갱신" 을 약속하는데 _metaGraphRenderProgress 가 dismissed run 을 조기 반환해 패널이
  //   영원히 안 뜸 — 노드 분석 경로(delete panel.dataset.dismissed) parity 로 폴 시작 직전 해제.
  //   즉시 head 를 렌더해 첫 폴 tick 전까지 직전 run 의 stale 내용이 보이는 창도 봉인(노드 경로 parity).
  const revealProgress = (reused) => {
    const panel = document.getElementById("metadataGraphProgress");
    if (!panel) return;
    delete panel.dataset.dismissed; panel.style.display = "";
    panel.innerHTML = reused
      ? '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">이미 진행 중 — 새로 큐잉하지 않고 기존 분석 현황을 표시합니다.</span></div>'
      : '<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">시작 중… 스키마 시드 항목(테이블·함수·프로시저)을 분석합니다(추가 확장 없음).</span></div>';
  };
  try {
    let dry;
    try {
      dry = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
        method: "POST", body: JSON.stringify({ schema_key: schemaKey, dry_run: true }),
      });
    } catch (err) {
      _metaGraphStatus(`${nm}: DB 단위 분석 대상 조회 실패 — ${(err && err.message) || "오류"}`);
      return;
    }
    if (dry && dry.reused && dry.run_id) {
      // §18.8 MINOR: 이미 진행 중이면 confirm 을 띄우지 않는다 — "이번 실행 N개" 승인 후 실제 POST 가
      //   reused(신규 큐잉 0)로 끝나는 허위 승인 차단(백엔드 dry_run 이 running run 을 먼저 감지).
      const pr = dry.progress || {};
      _metaGraphStatus(`${nm}: 이미 DB 단위 분석 진행 중 (진행 ${pr.done || 0}/${pr.enqueued || 0}) — 중복 큐잉하지 않고 진행 패널에서 갱신합니다.`);
      revealProgress(true);
      _metaGraphPollRun(dry.run_id, null);
      return;
    }
    if (!dry || !dry.planned) {
      _metaGraphStatus(`${nm}: 분석 대상 없음 — 테이블 ${dry ? (dry.total_tables || 0) : 0}개 · 함수/프로시저 ${dry ? (dry.total_routines || 0) : 0}개 전부 분석 완료(또는 대상 없음)`);
      return;
    }
    const cappedTxt = dry.capped ? `\n※ 상한 적용: 미분석 ${dry.missing}개 중 이번 실행 ${dry.planned}개 — 완료 후 재실행하면 이어서 분석합니다.` : "";
    if (!window.confirm(`'${nm}' DB 전체 AI 능동 분석을 시작합니다.\n\n테이블 ${dry.total_tables}개 · 함수/프로시저 ${dry.total_routines || 0}개 · 미분석 ${dry.missing}개 · 이번 실행 ${dry.planned}개${cappedTxt}\n\n이번 실행 대상 ${dry.planned}개 항목(테이블·함수·프로시저)마다 LLM 분석이 수행됩니다(백그라운드). 진행할까요?`)) return;
    let res;
    try {
      res = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
        method: "POST", body: JSON.stringify({ schema_key: schemaKey }),
      });
    } catch (err) {
      _metaGraphStatus(`${nm}: DB 단위 분석 시작 실패 — ${(err && err.message) || "오류"}`);
      return;
    }
    if (!res) return;
    if (res.reused) {
      const pr = res.progress || {};
      _metaGraphStatus(`${nm}: 이미 DB 단위 분석 진행 중 (진행 ${pr.done || 0}/${pr.enqueued || 0}) — 중복 큐잉하지 않고 진행 패널에서 갱신합니다.`);
      if (res.run_id) { revealProgress(true); _metaGraphPollRun(res.run_id, null); }
      return;
    }
    if (res.status === "noop" || !res.run_id) {
      _metaGraphStatus(`${nm}: 분석 대상 없음(이미 전부 분석 완료).`);
      return;
    }
    _metaGraphStatus(`${nm}: DB 전체 AI 능동 분석 시작 — 테이블 ${res.planned}개 (백그라운드, 진행은 우측 패널)`);
    revealProgress();
    _metaGraphPollRun(res.run_id, null);
  } finally {
    _metaGraph._analyzePending.delete(schemaKey);
  }
}

// run 진행률을 폴링하며 완료 노드에 그래프 마커 표시 + 초점 노드 분석 완료 시 결과 로드.
function _metaGraphPollRun(runId, focusKey) {
  if (!runId) return;
  _metaGraph.activeRunId = runId;   // fix(low): 최신 run 만 유효 — 재분석 시 이전 폴 루프 무효화(중복 방지)
  let tries = 0;
  const tick = async () => {
    if (_metaGraph.activeRunId !== runId) return;   // 다른 run 이 시작됨 → 이 루프 종료
    tries += 1;
    let st;
    try { st = await apiFetch(`/api/admin/metadata/graph/analyze?run_id=${encodeURIComponent(runId)}`); }
    catch (_) {
      // fix(medium): 일시 오류/네트워크/일시 5xx 로 폴이 영구 중단되지 않게 재시도(bounded).
      if (tries < 240 && _metaGraph.activeRunId === runId) setTimeout(tick, 2500);
      else _metaGraphMarkRunning([], []);   // review fix: 재시도 소진 시 주황 마커 정리(무한 '분석중' 방지)
      return;
    }
    if (!st) {
      if (tries < 240 && _metaGraph.activeRunId === runId) setTimeout(tick, 2500);
      else _metaGraphMarkRunning([], []);
      return;
    }
    // graphux5-progress: 그래프 마커(완료/분석중) + 진행 패널은 노드 선택과 무관하게 항상 갱신(화면 라이브).
    _metaGraphMarkAnalyzed(st.done_keys || [], st.roles || null);   // node-role-viz: 완료 즉시 역할 칩 색 라이브 반영
    _metaGraphMarkRunning(st.running_keys || [], st.done_keys || []);
    _metaGraphRenderProgress(st);
    const done = st.done || 0, total = st.enqueued || 0, failed = st.failed || 0;
    const onFocus = (_metaGraph.lastDetailKey === focusKey);
    // 초점 노드가 완료되면 상세 패널의 분석문도 로드(노드 상세는 여전히 개별 표시).
    if (onFocus && (st.done_keys || []).indexOf(focusKey) >= 0) _metaGraphLoadNodeAnalysis(focusKey);
    _metaGraphStatus(`AI 능동 분석: ${done}/${total} 완료${failed ? " · 실패 " + failed : ""} (${st.status})`);
    if (st.status === "running") {
      if (tries < 240) { setTimeout(tick, 2500); }
      else {
        // review fix: 캡 도달(여전히 running) — 폴 중단 시 주황 마커 잔존 방지 + 안내(백그라운드는 계속).
        _metaGraphMarkRunning([], st.done_keys || []);
        _metaGraphStatus(`AI 능동 분석: ${done}/${total} — 폴링 시간초과(백그라운드 계속). 노드 재클릭으로 최신 확인.`);
        _metaGraph.activeRunId = null;
      }
    } else {
      _metaGraphMarkRunning([], st.done_keys || []);   // 종료(done/failed) 시 주황 '분석중' 마커 정리
      if (onFocus) _metaGraphLoadNodeAnalysis(focusKey);
    }
  };
  setTimeout(tick, 1500);
}

// 현재 렌더된 노드에 마커/선택 state 재적용(전체 rebuild 없이 — 위치 불변).
// graph-perf-bg: 변화분만 적용(마지막 적용 signature 와 대조) — 폴(2.5s) 마다 전 노드 개별 setElementState 하던 stutter 제거.
// graph-expand-perf fix(프리즈): G6 v5 setElementState 는 건당 ~50ms(실측). 변화 노드가 많으면 per-node 루프가 수 초
//   메인스레드 프리즈를 낸다(200노드=10s). 그래서 변화 노드가 THRESHOLD 초과면 per-node 대신 **단일 setData rebuild**
//   (_metaG6Apply 가 data.states 로 전 상태를 한 번에 bake, ~80–200ms 상수)로 폴백한다. rebuild 는 캐시를 새 sig 로
//   채우므로(위 _metaG6Apply) 재귀·재적용 없음. 소수 변화는 per-node 유지(rebuild flicker 회피).
//   graph-expand-perf fix(폴 tick 이중 refresh): 한 폴 tick 이 _metaGraphMarkAnalyzed + _metaGraphMarkRunning 로 refresh 를
//   연속 2회 부르고 syncMarkers 등과도 겹친다 → 각기 rebuild 를 던지면 tick 당 2× rebuild + in-flight setData/draw 재진입.
//   rAF 로 coalesce: 같은 프레임의 다중 호출을 1회 실행으로 병합(양쪽 set 갱신 후 한 번만 반영). 폴 간격(2.5s) ≫ rebuild(~200ms)라 프레임 간 중첩 없음.
function _metaGraphRefreshStates() {
  if (_metaGraph._refreshScheduled) return;
  _metaGraph._refreshScheduled = true;
  const run = () => { _metaGraph._refreshScheduled = false; _metaGraphRefreshStatesNow(); };
  if (typeof window !== "undefined" && window.requestAnimationFrame) window.requestAnimationFrame(run);
  else setTimeout(run, 0);
}
function _metaGraphRefreshStatesNow() {
  const g = _metaGraph.graph;
  if (!g) return;
  const cache = _metaGraph._stateCache;
  const changed = [];
  let roleChanged = false;   // node-role-viz: 역할 도착/변경은 칩 색·라벨(bake 스타일)이라 setElementState 불가 → rebuild 강제
  _metaGraph.nodes.forEach((n) => {
    const st = _metaStateSig(n.key);   // busy 포함 signature — 폴 tick 이 fetch 창 도중 busy 를 지우지 않도록 보존
    const sig = _metaCacheSig(n.key);  // node-role-viz: 역할 suffix 포함 비교
    const prev = cache.get(n.key);
    if (prev !== sig) {
      changed.push({ key: n.key, st, sig });
      if (_metaSigRole(prev) !== _metaSigRole(sig)) roleChanged = true;
    }
  });
  if (!changed.length) return;   // 변화 없음 — 즉시 반환(폴 tick 의 대다수, rebuild 직후 no-op)
  const REBUILD_THRESHOLD = 4;   // per-node ~50ms/개 → 4개 초과면 rebuild(~200ms)가 저렴 + 프리즈 상한
  if (roleChanged || changed.length > REBUILD_THRESHOLD) {
    // §57.8: busy 는 bake states 로 보존되므로 rebuild 유예 불필요 — 폴 승격은 항상 수행(마지막
    //   회수 경로; 과거 busy 게이트는 stale busy 시 영구 미회수 = dim 고착의 한 축이었다).
    _metaG6Apply(false);   // setData 가 전 노드 상태 bake + _stateCache populate(카메라 유지, fit=false). fire-and-forget.
    return;
  }
  const apply = () => {
    // graph-expand-perf(freeze) + graph-initview 병합: 변화분(changed)만 순회하되, graph-initview 의
    //   _metaRenderedIdFor(카드 매핑·미렌더 skip) + Promise-wrap setElementState(async reject 무해화)를 유지.
    changed.forEach(({ key, st, sig }) => {
      cache.set(key, sig);
      const el = _metaRenderedIdFor(key);   // graph-initview: 카드 매핑 + 미렌더 skip
      if (!el) return;
      try { Promise.resolve(g.setElementState(el, st)).catch(() => {}); } catch (_) {}
    });
  };
  try {
    if (typeof g.startBatch === "function") { g.startBatch(); try { apply(); } finally { g.endBatch(); } }
    else apply();
  } catch (_) { try { apply(); } catch (_2) {} }
}

// AI 분석 중(running) 노드 주황 점선 마커. done 은 제외.
function _metaGraphMarkRunning(runningKeys, doneKeys) {
  const done = new Set(doneKeys || []);
  _metaGraph.running = new Set((runningKeys || []).filter((k) => !done.has(k)));
  _metaGraphRefreshStates();
}

// graphux5-progress: AI 능동 분석 진행 현황을 상단 패널에 라이브 렌더. 노드 선택과 무관하게 항상 갱신하고,
//   단순 %가 아니라 **어떤 항목(테이블/컬럼/스키마/용어)이 어느 상태(분석중/완료/대기)인지 상세**를 보여준다.
function _metaGraphRenderProgress(st) {
  const panel = document.getElementById("metadataGraphProgress");
  if (!panel || !st) return;
  if (panel.dataset.dismissed && panel.dataset.dismissed === st.run_id) return;   // 사용자가 이 run 패널을 닫음
  panel.style.display = "";   // fix(세션 독립): 재개 폴 경로(버튼 미경유)에서도 패널을 표시 — 초기 display:none 해제
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const jobs = st.jobs || [];
  const done = st.done || 0, enq = st.enqueued || 0, failed = st.failed || 0;
  const running = jobs.filter((j) => j.status === "running");
  const pending = Math.max(0, enq - done - failed - running.length);
  const pct = enq ? Math.round((done / enq) * 100) : 0;
  const ko = (l) => _META_LABEL_KO[l] || l || "노드";
  const statusKo = st.status === "running" ? "진행 중" : st.status === "done" ? "완료" : st.status === "failed" ? "실패" : (st.status || "");
  const stCls = { running: "ampg-st-running", done: "ampg-st-done", failed: "ampg-st-failed" }[st.status] || "";   // review fix: 값을 class 속성에 직접 보간하지 않음
  // node-role-viz: 완료 항목에 AI 분류 역할(아이콘+라벨) 병기 — 진행 패널에서도 역할이 즉시 읽히게.
  const roleTag = (j) => (j.role && _META_ROLE[j.role]) ? ` <span class="admin-meta-graph-muted">${_META_ROLE[j.role].icon} ${esc(_META_ROLE[j.role].ko)}</span>` : "";
  const item = (j, cls, ic) => `<li class="ampg-item ${cls}">${ic} <span class="ampg-lbl">${esc(ko(j.node_label))}</span> <span class="ampg-nm">${esc(j.node_name || j.node_key || "")}</span>${roleTag(j)}<span class="admin-meta-graph-muted"> · 깊이 ${j.depth}</span></li>`;
  const rows = [];
  running.forEach((j) => rows.push(item(j, "ampg-running", "⏳")));
  jobs.filter((j) => j.status === "done").slice(0, 12).forEach((j) => rows.push(item(j, "ampg-done", "✅")));
  jobs.filter((j) => j.status === "failed").slice(0, 4).forEach((j) => rows.push(item(j, "ampg-fail", "⚠️")));
  // routine-dbanalysis(§53 MINOR): 스키마 run 은 고정 시드·재귀 0 이 비용 계약 — "재귀 탐색 중" 카피가
  //   confirm("이번 실행 N개") 직후 무한 fan-out 오해를 부르므로 root_label 로 분기.
  //   (root_label=Schema 재귀 run 은 UI 비도달 — Schema 루트는 analyze-schema 경로만 생성한다.)
  if (pending > 0) rows.push(`<li class="ampg-item admin-meta-graph-muted">⋯ 대기 ${pending}개 (${st.root_label === "Schema" ? "시드 항목 대기 — 추가 확장 없음" : "관련 노드 재귀 탐색 중"})</li>`);
  const parts = [];
  parts.push(`<div class="ampg-head"><strong>🔎 AI 능동 분석</strong> <span class="admin-meta-graph-muted">${esc(st.root_name || st.root_key || "")}</span> <span class="ampg-status ${stCls}">${statusKo}</span><button type="button" class="ampg-close" id="metaGraphProgClose" title="닫기" aria-label="진행 패널 닫기">✕</button></div>`);
  parts.push(`<div class="ampg-bar" title="${done}/${enq}"><div class="ampg-bar-fill" style="width:${pct}%"></div></div>`);
  parts.push(`<div class="ampg-counts">완료 <b>${done}</b> · 분석중 <b>${running.length}</b> · 대기 <b>${pending}</b>${failed ? ` · 실패 <b>${failed}</b>` : ""} <span class="admin-meta-graph-muted">/ 예약 ${enq}${st.node_budget ? ` (상한 ${st.node_budget})` : ""}</span></div>`);
  parts.push(`<ul class="ampg-list">${rows.join("") || '<li class="admin-meta-graph-muted">준비 중…</li>'}</ul>`);
  panel.innerHTML = parts.join("");
  const cb = document.getElementById("metaGraphProgClose");
  if (cb) cb.addEventListener("click", () => { panel.style.display = "none"; panel.dataset.dismissed = st.run_id || "1"; });
}

// 완료 노드 키에 분석 마커(보라). 세션 set 에 기억(rebuild 시 유지).
// node-role-viz: roles({key:role})가 오면 역할 표식도 병합 — refreshStates 가 역할 변화를 감지해 rebuild 로 칩 색/아이콘 반영.
function _metaGraphMarkAnalyzed(keys, roles) {
  (keys || []).forEach((k) => _metaGraph.analyzed.add(k));
  if (roles) Object.keys(roles).forEach((k) => { if (roles[k] && _META_ROLE[roles[k]]) _metaGraph.roles.set(k, roles[k]); });
  _metaGraphRefreshStates();
}

// 항목1: 스코프 내 이미 분석된/진행중 노드 마커를 그래프 로드/검색/확장 직후 **일괄** 적용 —
//   노드를 개별 클릭하지 않아도 렌더 시점에 '분석됨'(보라)·'분석중'(주황) 표식이 나타나게 한다.
//   기존엔 세션 로컬 set(_metaGraph.analyzed/running)이 현재 세션 폴 run 에서만 채워져, 새로고침/재진입 시
//   DB 에 저장된 분석 상태가 클릭 전까지 반영되지 않던 근본 원인 수정. 활성 폴의 running set 은 덮어쓰지
//   않도록 additive 로만 적용(clear 안 함).
async function _metaGraphSyncAnalysisMarkers(scope) {
  if (!_metaGraph.graph) return;
  const sc = scope || adminState.metadata.scopeKey || "common";
  if (!sc || sc === "common") return;
  let res;
  try { res = await apiFetch(`/api/admin/metadata/graph/analyze/status?scope=${encodeURIComponent(sc)}`); }
  catch (_) { return; }
  if (!res) return;
  (res.done_keys || []).forEach((k) => _metaGraph.analyzed.add(k));
  const doneSet = new Set(res.done_keys || []);
  (res.running_keys || []).forEach((k) => { if (!doneSet.has(k)) _metaGraph.running.add(k); });
  // node-role-viz: DB 에 저장된 역할 분류를 렌더 시점에 일괄 적용(새로고침/재진입에도 칩 색·아이콘 복원).
  const roles = res.roles || {};
  Object.keys(roles).forEach((k) => { if (roles[k] && _META_ROLE[roles[k]]) _metaGraph.roles.set(k, roles[k]); });
  _metaGraphRefreshStates();
}

// 스키마 클러스터(combo) 상세 — 스키마명·포함 테이블 목록·개수. combo:click 진입.
async function _metaGraphShowClusterDetailById(comboId) {
  if (!_metaGraph.graph || !comboId) return;
  if (comboId === _META_TERMS_COMBO) { _metaGraphStatus("용어·기타 클러스터"); return; }
  _metaGraph.lastDetailKey = comboId;
  _metaGraphHistoryRecord(comboId, "cluster");   // §54①: terms 가드 뒤·첫 await 이전(동기 구간).
  const schemaName = _metaComboName(comboId);
  _metaGraphStatus("클러스터 상세 조회 중…");
  let data = null;
  try { data = await apiFetch(`/api/admin/metadata/graph?node=${encodeURIComponent(comboId)}&depth=1`); }
  catch (_) { data = null; }
  let tables = [];
  if (data) {
    const byKey = {};
    (data.nodes || []).forEach((nd) => { if (nd && nd.key) byKey[nd.key] = nd; });
    (data.edges || []).forEach((e) => { if (e && e.type === "HAS_TABLE" && e.source === comboId && byKey[e.target]) tables.push(byKey[e.target]); });
    if (!tables.length) (data.nodes || []).forEach((nd) => { if (nd && nd.label === "Table" && nd.key !== comboId) tables.push(nd); });
  }
  // API 가 비면 모델에 로드된 이 스키마 테이블로 폴백.
  let childTables = 0, childCols = 0;
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) childTables += 1;
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  if (!tables.length) _metaGraph.nodes.forEach((n) => { if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n); });
  _metaGraphRenderClusterDetail(schemaName, schemaName, tables, childTables, childCols, null, false, comboId);
  _metaGraphStatus(`클러스터: ${schemaName} · 테이블 ${tables.length || childTables}개`);
}

// 항목2: 클러스터 상세 카드 렌더(우측 상세 패널 body). 노드 상세(_metaGraphRenderDetail)와 동일 컨테이너를 교체.
function _metaGraphRenderClusterDetail(name, fqn, tables, childTables, childCols, totalOverride, truncated, comboId) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // graph-initview(V-G): cap 절단 시 실 총계(table_count) 우선 — 카드 배지와 패널 수치 모순 방지.
  const nTables = (totalOverride != null) ? totalOverride : ((tables && tables.length) || childTables || 0);
  const truncNote = (truncated || (totalOverride != null && tables && totalOverride > tables.length))
    ? ` (그래프에는 ${tables && tables.length ? tables.length : 0}개만 표시 — 상한)` : "";
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  // graphux7(#7): 펼쳐진 스키마면 상세 패널(항상 화면 내 aside)에 전용 '접기' 버튼 — 캔버스 combo 우상단
  //   "−" 컨트롤은 큰 스키마에서 뷰포트 밖으로 벗어나 접근 불가하던 문제 해소. 패널 body 클릭으로 접히지 않게
  //   접기는 이 버튼(및 기존 "−"/우클릭 메뉴)로만 트리거.
  const _canCollapse = comboId && _metaGraph.schemaExpanded && _metaGraph.schemaExpanded.has(comboId);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR.Schema}">스키마 클러스터</span><strong>${esc(name)}</strong>${_canCollapse ? ` <button type="button" class="amgr-link" id="metaGraphClusterCollapseBtn" title="이 스키마를 카드로 접습니다(그래프에서 축소)">▦ 접기</button>` : ""}${comboId && comboId !== _META_TERMS_COMBO ? ` <button type="button" class="amgr-link" id="metaGraphClusterAnalyzeBtn" title="이 DB(스키마)의 미분석 항목(테이블·함수·프로시저) 전체를 AI 능동 분석합니다 — 실행 전 대상 수를 확인합니다">✨ DB 전체 AI 능동 분석</button>` : ""}</div>`);
  if (fqn && fqn !== name) parts.push(`<div class="admin-meta-graph-fqn">${esc(fqn)}</div>`);
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">이 스키마 클러스터에 속한 테이블 ${nTables}개${truncNote}${childCols ? ` · 표시된 컬럼 ${childCols}개` : ""}. 테이블 노드를 클릭하면 컬럼·관계·용어 상세를 봅니다.</p>`);
  if (tables && tables.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>테이블 (${tables.length})</h4><ul class="amgr-cluster-tables">`);
    // role-cluster-prefix: AI 능동 분석 완료 테이블은 역할 칩을 접두사로, 미분석은 동일 폭 빈 슬롯(라벨 좌측 정렬 유지 — 뒤틀림 방지).
    const rowHTML = (t) => {
      const role = _metaRoleOf(t.key);
      const prefix = role ? _metaRoleChipHTML(role, esc, true) : `<span class="amgr-role-chip amgr-role-chip-sm amgr-role-none" aria-hidden="true"></span>`;
      return `<li><button type="button" class="amgr-ct-row" data-node-key="${esc(t.key)}" title="클릭하면 이 테이블 노드를 선택합니다">${prefix}<code>${esc(t.name || t.fqn || "")}</code>${t.description ? `<span class="amgr-ct-desc"> — ${esc(t.description)}</span>` : ""}</button></li>`;
    };
    // graph-simgroups: 캔버스와 동일한 유사 속성 그룹으로 목록도 구획(헤딩 행) — 2그룹 이상일 때만. 실패 시 평면 폴백.
    let sgs = null;
    try {
      const tbk = new Map(tables.map((t) => [t.key, t]));
      sgs = _metaSimGroups("panel:" + String(name), tables, _metaRelAdjacency(tbk));
    } catch (_) { sgs = null; }
    if (sgs && sgs.length >= 2) {
      // §18.8 패널: 그룹 헤딩은 목록의 실제 구획 의미(장식 아님) → aria-hidden 금지. role="group"+aria-label
      //   로 보조기기에 "그룹명·개수"를 노출. 80행 캡은 그룹 경계에서만 끊고 절단 표식을 남긴다(개수 모순 방지).
      let emitted = 0;
      sgs.forEach((sg) => {
        if (emitted >= 80) return;
        const shown = Math.min(sg.tables.length, 80 - emitted);
        const trunc = shown < sg.tables.length ? ` <span class="amgr-ct-group-trunc">(${shown}/${sg.n})</span>` : "";
        parts.push(`<li class="amgr-ct-group" role="group" aria-label="${esc(sg.label)} 그룹 · 테이블 ${sg.n}개"><span class="amgr-ct-group-label">${esc(sg.label)}</span><span class="amgr-ct-group-n">${sg.n}</span>${trunc}</li>`);
        sg.tables.slice(0, shown).forEach((t) => { parts.push(rowHTML(t)); emitted++; });
      });
    } else {
      tables.slice(0, 80).forEach((t) => parts.push(rowHTML(t)));
    }
    parts.push(`</ul></div>`);
  }
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // graphux7(#7): 전용 접기 버튼 바인딩 — 이 스키마를 카드로 축소(항상 화면 내 상세 패널에서 접근).
  const _collapseBtn = document.getElementById("metaGraphClusterCollapseBtn");
  if (_collapseBtn && comboId) _collapseBtn.addEventListener("click", () => _metaGraphCollapseSchema(comboId));
  // routine-dbanalysis(§53): DB 단위 능동 분석 버튼 — 컨텍스트 메뉴와 동일 핸들러(확인창에 대상 수 표시).
  const _schemaAiBtn = document.getElementById("metaGraphClusterAnalyzeBtn");
  if (_schemaAiBtn && comboId) _schemaAiBtn.addEventListener("click", () => _metaGraphAnalyzeSchema(comboId));
  // role-cluster-prefix: 테이블 행 클릭 → 해당 노드 선택(_metaGraphShowDetail = 하이라이트 setSelected + 상세 렌더) + 렌더돼 있으면 카메라 focus.
  el.querySelectorAll(".amgr-ct-row[data-node-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.getAttribute("data-node-key");
      if (!k) return;
      _metaGraphShowDetail(k);
      const g = _metaGraph.graph, rel = _metaRenderedIdFor(k);
      if (g && rel && typeof g.focusElement === "function") { try { Promise.resolve(g.focusElement(rel, false)).catch(() => {}); } catch (_) {} }
    });
  });
}

// 노드의 최신 분석 상태/결과를 조회해 AI box 에 렌더(상세 패널 진입 시 + 폴링 완료 시).
async function _metaGraphLoadNodeAnalysis(key) {
  const box = document.getElementById("metaGraphAiBox");
  if (!box || !key) return;
  let res;
  try { res = await apiFetch(`/api/admin/metadata/graph/analyze/node?node=${encodeURIComponent(key)}`); }
  catch (_) { return; }
  if (!res) return;
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (res.status === "done" && res.analysis) {
    const roleObj = (res.role && _META_ROLE[res.role]) ? _META_ROLE[res.role] : null;
    _metaGraphMarkAnalyzed([key], roleObj ? { [key]: res.role } : null);
    const a = res.analysis;
    const rows = [];
    // node-role-viz: AI 분류 역할 칩 — 그래프 칩 색과 동일 색/아이콘으로 상세 패널에서도 역할을 명시.
    if (roleObj) rows.push(`<p><span class="admin-meta-graph-badge" style="background:${roleObj.color}${roleObj.dark ? ";color:#161b22" : ""}">${roleObj.icon} ${esc(roleObj.ko)}</span> <span class="admin-meta-graph-muted">AI 분류 테이블 역할</span></p>`);
    if (a.summary) rows.push(`<p class="admin-meta-graph-ai-summary">${esc(a.summary)}</p>`);
    if (a.relationships) rows.push(`<p><strong>관계</strong> — ${esc(a.relationships)}</p>`);
    if (a.usage) rows.push(`<p><strong>활용</strong> — ${esc(a.usage)}</p>`);
    if (a.caveats) rows.push(`<p class="admin-meta-graph-muted"><strong>주의</strong> — ${esc(a.caveats)}</p>`);
    // reldedup(graph-detail): 'AI 능동 분석' 박스의 '연결 관계 추적' flat 목록을 제거했다.
    //   그 목록은 상단 '컬럼 > 참조함/참조받음' 섹션(_metaGraphRenderDetail)과 **동일한 모델
    //   REFERENCES 를 동일한 추적 행·신뢰 배지·클릭 동작**으로 재렌더해 역할·작동이 완전히 중복됐다
    //   (사용자 확인). 추적 가능한 관계는 컬럼별·방향별로 더 풍부한 상단 섹션에 일원화하고, AI 박스는
    //   고유 가치인 역할 칩 + prose(요약·관계·활용·주의)만 유지한다.
    // graph-funcproc(REQ ④): '↻ 재분석' 버튼 제거 — 섹션 헤더의 '✨ 능동 분석' 재실행으로 충분(UX 중복).
    box.innerHTML = rows.join("") || '<span class="admin-meta-graph-muted">분석 결과 없음.</span>';
  } else if (res.status === "pending" || res.status === "running") {
    box.innerHTML = '<span class="admin-meta-graph-muted">분석 진행 중(백그라운드)… 진행 현황은 위 진행 패널에서 확인하세요.</span>';
    // graphux5 fix(세션 독립): 이 노드가 (다른 탭/세션·새로고침으로) 활성 폴이 없는 진행 중 run 에 속하면
    //   그 run 을 폴링 재개해 **어느 화면에서도** 진행 패널·주황 마커·진행률이 나타나게 한다. 이미 그 run 을
    //   폴링 중이면 재개하지 않음(중복 방지). run 이 done/failed 로 끝나면 폴이 자연 종료.
    if (res.run_id && _metaGraph.activeRunId !== res.run_id) {
      const panel = document.getElementById("metadataGraphProgress");
      if (panel) delete panel.dataset.dismissed;
      _metaGraphPollRun(res.run_id, key);
    }
  } else if (res.status === "failed") {
    box.innerHTML = '<span class="admin-meta-graph-muted">이 노드 분석 실패. 재시도하려면 능동 분석을 다시 눌러 주세요.</span>';
  }
  // status === 'none' → 기본 안내 유지(버튼으로 시작).
}

// 폼 값 수집 — 체크박스는 boolean, 그 외는 trim 된 문자열. (number 변환은 _metaSubmitForm 에서.)

// admin.js(tab-switch) 소비 진입점 — export surface(census: 정확히 4).
export { _metaShowGraph, _metaGraphLoadRoots, _metaRoleLegendTips, _metaGraph };
