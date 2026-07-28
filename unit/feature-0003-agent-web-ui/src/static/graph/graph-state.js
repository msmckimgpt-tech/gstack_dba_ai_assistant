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
  groupInfo: new Map(),       // graph-content-category: groupKey -> {label, n, schema} (우클릭 컨텐츠 카테고리 메뉴 헤더용 — 매 build 재구성)
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
  detailHist: [],             // 방문 스택 — {v:"node"|"cluster"|"rel", k:key, scroll?:number} (오래된 앞 → 최근 뒤)
  detailHistIdx: -1,          // 현재 위치 인덱스(-1=비어 있음)
  _histNav: false,            // 뒤로/앞으로 네비게이션 진행 중 플래그(Record 억제 — show 동기 접두부 한정)
  // graph-detail-scroll: 상세 패널 스크롤 위치 보존(뒤로/앞으로). detailHist[i].scroll 에 이력 항목별 scrollTop
  //   스냅샷을 저장·복원. _histNavBusy=네비 렌더 in-flight(캡처 스킵으로 연타 시 오정합 방지 — _histNav 와
  //   분리: _histNav 는 Record 억제만, 이 플래그는 스크롤 캡처만 게이팅). _pendingDetailScroll=복원 목표
  //   {key,top} — 노드 상세 AI 박스(_metaGraphLoadNodeAnalysis)가 async 로 높이를 키운 뒤 1회 재적용용.
  _histNavBusy: false,
  _pendingDetailScroll: null,
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
  // detail-db-groups(사용자 요구 2026-07-27): 상세 패널의 **관련 노드 목록**(사용 함수·프로시저, 참조함/
  //   참조받음)을 소속 DB(스키마 클러스터 = _metaCatParent) 단위로 묶고 접기/펼치기 한다. 여기엔 사용자가
  //   **명시적으로 조작한** 그룹만 기록한다(key=DB 그룹 key `scope:db`, val=true 펼침 / false 접힘).
  //   미기록 그룹은 기본 규칙(선택 노드와 같은 DB=펼침 · 다른 DB=접힘)을 따른다 — Set 은 "접힘" 만 담을 수
  //   있어 기본-접힘+사용자-펼침 기억을 표현하지 못하므로 Map 을 쓴다. DB key 기준이라 노드 상세↔관계 상세
  //   전환 간에도 사용자의 펼침 의도가 유지된다(세션 한정, 리로드 초기화).
  panelDbGroupState: new Map(),
  // graph-catcluster-scroll(사용자 요청 2026-07-28): 캔버스에서 컨텐츠 카테고리(sim-group) 클러스터를 선택하면
  //   그 선택이 여는 '스키마 클러스터' 상세 목록에서 같은 카테고리 헤딩 위치로 패널을 스크롤한다. 연타/빠른
  //   재선택 시 rAF 안의 stale 스크롤이 최신 선택을 덮지 않게 하는 세대 토큰(_opSeq 와 동형 — 패널 스크롤 전용).
  _panelFocusSeq: 0,
  panelGroupCollapsed: new Set(),  // graph-funcproc(cluster-detail-collapse): 클러스터 상세 패널에서 접힌 컨텐츠 카테고리 그룹 key(sg.key="panel:"+name+""+fam). 같은 클러스터 재렌더 간 접힘 유지(세션 한정, 리로드 초기화).
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
// label-lod(20260728T1604, 사용자 리포트 2026-07-28 "과도한 줌아웃 시 글자가 깨짐"): 라벨은 화면 실효 크기가
//   작아질수록 GPU 다운샘플 aliasing 으로 붕괴한다(노이즈·모아레·팬 중 반짝임). PixiJS v8 BitmapText 의
//   dynamic font 는 글리프를 **항상 100px**(baseRenderedFontSize, overrideSize=true)로 굽고 fontSize/100
//   으로 축소해 그리므로, fontSize 12 라벨은 zoom 0.1·DPR 2 에서 텍스처 대비 ~1/42 축소 = 사실상 임의 점
//   샘플링이다(아틀라스는 mipmap 부재 — PixiJS v8.19 dynamic font 에는 이를 켜는 유효한 seam 이 없다.
//   사후에 autoGenerateMipmaps/mipLevelCount 를 세워도 GL 텍스처·샘플러가 이미 굳어 렌더 결과 픽셀 차이 0
//   임을 실측했다 — 2026-07-28 PB-0008). Text 폴백도 fontSize×labelRes(≤4)라 ~1/20 로 같은 기전이다.
//   판독 불가 크기의 라벨은 정보를 주지 않고 노이즈와 draw call 만 남기므로 **방출하지 않는다**
//   (정보 손실 0 — 어차피 못 읽는다. 확대하면 그대로 복귀).
//   임계는 화면 CSS px: fontSize(model px) × zoom = 화면 px. dpr 은 곱하지 않는다(판독성은 CSS px 기준).
const _META_LABEL_MIN_PX = 5;          // 본문 라벨(테이블·컬럼·루틴·파라미터·용어·접기 컨트롤·엣지 count)
const _META_LABEL_HEADER_MIN_PX = 3.2; // 헤더·카드(카테고리 밴드·스키마 클러스터/카드·컨텐츠 그룹·제품 개요)
//   — 개요에서 "여기가 어디인가"를 주는 소수의 큰 라벨이라 본문보다 오래 유지한다.
const _META_LABEL_HDR_KINDS = new Set(["cat-hd", "schema-card", "group-hd", "schema", "product", "datasource"]);
// 라벨 LOD 밴드 — 임계를 교차할 때만 rebuild 하도록(_lodBand 훅) 줌을 "억제 경계 폰트 크기"로 양자화한다.
//   MIN/zoom = 이 줌에서 억제되는 폰트 크기의 상한(이 값 미만 폰트가 억제) → 실제 억제 집합이 바뀌는
//   지점에서만 밴드 문자열이 바뀐다. **양끝을 실사용 라벨 폰트 범위로 클램프**해야 무의미한 rebuild 가 없다:
//     · 하한 9 (실사용 최소 폰트, graph-roleviz count 라벨) — 경계가 9 이하면 억제 대상이 아예 없으므로
//       zoom 1.0 과 0.9 는 같은 상태다. 클램프가 없으면 통상 줌 휠 조작마다 밴드가 바뀌어 rebuild 가 걸린다.
//     · 상한 24 (실사용 최대 폰트 15 + 여유) — 그 위는 전부 "전량 억제" 동일 상태. 클램프가 없으면 극단
//       줌아웃에서 휠 한 칸마다 rebuild 가 걸린다.
//   **STEP=0.5 (반포인트) 격자에 올린다 — 정수 ceil 은 소수 폰트의 임계 교차를 놓친다**(codex P2):
//   라벨 폰트에는 정수뿐 아니라 `10.5`(컨텐츠 그룹 헤더)·`11.5`(제품 개요) 같은 반포인트 값이 있다.
//   `ceil(MIN/z)` 는 정수 경계에서만 값이 바뀌므로, 예컨대 헤더 하한 3.2 와 10.5px 의 교차점
//   z*=3.2/10.5≈0.30476 을 지나도 밴드가 그대로다(0.3048→11, 0.3040→11) → rebuild 가 걸리지 않아
//   **10.5px 헤더가 판독 하한 밑에서 계속 렌더된다**(다른 밴드가 우연히 바뀔 때까지). 반포인트 격자
//   `ceil(MIN/z / STEP) * STEP` 는 0.5 의 배수인 모든 실사용 폰트에 대해 억제 집합 변화와 1:1 대응한다
//   (같은 예: 0.3048→10.5, 0.3040→11 로 갈라진다). 런타임 계산 폰트(스키마 카드 `_cardLF`/`_cardBF`)는
//   `Math.round` 정수라 반포인트 격자가 정수 격자를 포함하므로 함께 커버된다.
const _META_LABEL_FONT_LO = 9, _META_LABEL_FONT_HI = 24, _META_LABEL_FONT_STEP = 0.5;
// ─────────────────────────────────────────────────────────────────────────────
// hdr-label-fit(사용자 요청 2026-07-28): **위계 헤더 라벨을 클러스터 범위만큼 확장**한다.
//   문제 — 컨텐츠 카테고리 헤더(group-hd)는 폰트가 10.5 **고정**이라 박스 폭이 248px 든 920px 든
//   똑같이 zoom 3.2/10.5≈0.305 에서 억제됐다. 박스 크기라는 정보가 이미 있는데 폰트가 그걸 쓰지 않았다.
//   위계 한 단계 위 제품 카테고리 밴드(cat-hd, 12 고정)도 동형.
//
//   해법 = **(a) 화면 하한 역보정 + (b) 박스 fit** 의 하한 결합(지도학·트리맵 표준의 합성):
//     (a) `want = base / z` — 줌아웃해도 **화면상 base 크기를 유지**한다. 지도 라벨(Mapbox·deck.gl)의
//         screen-space 관례이며, 본 코드베이스에도 §85 `edgeScreenScale = 1/zoom` 선례가 있다.
//     (b) `fit = 가용폭 / (글자수 × 폭계수)` — 라벨이 **자기 박스를 절대 넘지 않게** 상한을 건다.
//         트리맵 fit-to-box(`font = min(w/4, h/2)` 류)와 같은 발상. 이 상한이 있어야 극단 줌아웃에서
//         헤더들이 서로 겹쳐 폭발하지 않는다(지도는 이 문제를 라벨 충돌 컬링으로 푸는데, 박스 상한은
//         그 복잡도 없이 같은 목적을 달성한다 — 범위를 넘지 않으면 이웃과도 겹치지 않는다).
//   `min(want, fit)` 를 취하고 **[base, HI] 로 클램프**한다. 결과:
//     · 줌인(z ≥ 1)은 `base` 그대로 — 부풀지 않는다(§86 "줌인은 화면 고정" 결정과 정합).
//     · 줌아웃은 박스가 허용하는 한 화면 크기 유지 → 2열(472px) 이상 클러스터는 zoom 하한(0.05)까지
//       사실상 사라지지 않고, 1열(248px)도 억제 시점이 0.305 → ~0.156 으로 2배 늦어진다.
//   위계 크기 = 멤버 수라 "면적이 곧 위계"라는 지도학의 통상 경고(넓다고 중요한 게 아니다)는 여기선
//   해당하지 않는다 — 박스가 큰 클러스터는 실제로 테이블이 많다.
// world 폰트 상한 — **줌 하한에서 파생**한다. `base/z` 역보정은 이 상한에 닿는 순간부터 화면 크기가
//   감쇠하기 시작하므로(그 아래는 `MAX × z`), 상한이 곧 "어디까지 base 크기로 보이는가"를 정한다:
//   화면 크기가 base 로 유지되는 구간 = `z > base / MAX`.
//   상한을 `헤더 판독 하한 / zoomRange 하한`(graph-initview A2 의 0.05)으로 잡으면 **줌 전 구간에서
//   위계 헤더가 판독 하한 이상**이고, 실측 "전체 조망" 줌(라이브 136 스키마 = 0.2524)이 감쇠 구간이
//   아니라 **base 크기 유지 구간**에 들어온다(상한 26 이면 0.2524 에서 이미 6.6px 로 감쇠 — 사용자
//   요구 "줌 아웃 시에도 상대적으로 명확하게"를 만족하지 못한다).
//   칩이 커지는 비용은 박스 fit 상한이 흡수한다 — 좁은 박스(1열 248px)는 fit 이 ~22.6 에서 잡으므로
//   상한을 올려도 그 클러스터의 칩은 커지지 않는다(개선은 범위가 큰 클러스터에만 붙는다 = 사용자 의도).
const _META_HDR_FIT_ZOOM_FLOOR = 0.05;   // graph-core.js `zoomRange: [0.05, 4]` 와 동기 — 변경 시 함께 조정
const _META_HDR_FIT_MAX = Math.ceil(_META_LABEL_HEADER_MIN_PX / _META_HDR_FIT_ZOOM_FLOOR);   // = 64
const _META_HDR_FIT_CHARW = 0.686;   // 글자 1개 폭 / 폰트 크기 — 기존 추정계수(10.5→7.2 · 12→8.2)의 공통값
const _META_HDR_FIT_PAD = 26;        // 칩 내부 좌우 pad + 컨트롤 자리
// 헤더 폰트 파생 — 순수 함수(zoom·박스폭·글자수만 의존). 라벨 LOD(_metaApplyLabelLod)는 이 결과를
//   `st.labelFontSize` 로 그대로 읽으므로 억제 판정이 자동으로 늦어진다(별도 결합 불필요).
function _metaHdrFitFont(baseFont, boxW, textLen, zoom) {
  const base = (typeof baseFont === "number" && isFinite(baseFont) && baseFont > 0) ? baseFont : 10.5;
  const z = (typeof zoom === "number" && isFinite(zoom) && zoom > 0) ? zoom : 1;
  if (z >= 1) return base;   // 줌인·기본 배율 — 종전 그대로(회귀 0)
  const avail = Math.max(0, (typeof boxW === "number" && isFinite(boxW) ? boxW : 0) - _META_HDR_FIT_PAD);
  const n = Math.max(1, (typeof textLen === "number" && isFinite(textLen)) ? textLen : 1);
  const fit = avail / (n * _META_HDR_FIT_CHARW);
  return Math.max(base, Math.min(base / z, fit, _META_HDR_FIT_MAX));
}
// 헤더 폰트 반동 밴드 — 폰트가 `base/z` 로 **연속** 변하는데 rebuild 는 밴드 전이에서만 걸리므로,
//   억제 밴드만으로는 폰트가 stale 해져 화면 크기가 드리프트한다(역보정이 무의미해진다). 그래서
//   역보정 배율을 **25% 승법 스텝**으로 양자화해 밴드에 합류시킨다 — §85 가 엣지 굵기 재페인트에
//   채택한 것과 같은 허용 오차(줌 변화 ≈25% 초과 시 갱신)라, 화면 크기 드리프트가 ≤25% 로 유계다.
//   `z >= 1` 구간은 폰트가 base 고정이라 스텝을 0 으로 접어 통상 줌에서 무의미한 rebuild 를 막는다.
//   **상한 클램프 필수** — `base/z` 가 `_META_HDR_FIT_MAX` 를 넘는 순간부터 폰트는 `min(fit, MAX)` 로
//   z 와 무관해지므로, 그 뒤로도 스텝이 계속 늘면 **아무 변화 없는 rebuild** 가 극단 줌아웃 휠마다 걸린다
//   (신규 테스트 없이 넣었을 때 기존 F3·F7 '무의미 rebuild 차단' 이 실제로 깨졌다 — 실측 확인).
//   상한은 실사용 최소 base(group-hd 10.5)에서 파생해 상수 변경에 자동 추종한다. `MAX` 를 줌 하한에서
//   파생하도록 올린 결과 스텝 상한도 5 → 9 로 늘었다 — 줌아웃 전 구간에 걸쳐 rebuild 경계가 최대 9개라는
//   뜻이며, 억제 밴드(_META_LABEL_FONT_STEP 격자)가 이미 그 구간에서 바뀌므로 **증분 경계는 9개보다 적다**.
//   허용 오차(화면 크기 드리프트 ≤25%)는 §85 가 엣지 재페인트에 채택한 값과 동일하다.
const _META_HDR_FIT_STEP_RATIO = 1.25;
const _META_HDR_FIT_BASE_MIN = 10.5;   // 실사용 최소 헤더 base — 이 base 가 가장 늦게 MAX 에 닿는다
const _META_HDR_FIT_STEP_CAP = Math.ceil(
  Math.log(_META_HDR_FIT_MAX / _META_HDR_FIT_BASE_MIN) / Math.log(_META_HDR_FIT_STEP_RATIO));
function _metaHdrFitBandOf(zoom) {
  const z = (typeof zoom === "number" && isFinite(zoom) && zoom > 0) ? zoom : 1;
  if (z >= 1) return 0;
  return Math.min(_META_HDR_FIT_STEP_CAP,
    Math.round(Math.log(1 / z) / Math.log(_META_HDR_FIT_STEP_RATIO)));
}
// **확장 가능한 위계 헤더가 없으면 반동 성분을 밴드에서 뺀다**(codex P2, 2026-07-28): `/h` 를 무조건 붙이면
//   위계 헤더를 **아예 방출하지 않는 경로**에서도 줌 전이마다 full `setData`/draw rebuild 가 걸린다 —
//   `products` 모드는 `_metaG6Build()` 가 헤더 방출 전에 `_metaG6BuildProducts()` 로 빠지므로 1→0.89→0.71→0.57
//   같은 전이가 전부 헛 rebuild 다. 박스가 좁아 `fit ≤ base` 인 헤더만 있는 경우도 폰트가 z-무관이라 같다.
//   게이트는 **z-독립**이어야 한다 — "지금 확장됐나"로 판정하면 zoom 1(전부 base)에서 게이트가 닫혀 줌아웃
//   시작 rebuild 가 영구히 안 걸리는 self-lock 이 된다. 그래서 방출 시점에 **"이 박스가 base 보다 큰 폰트를
//   담을 수 있는가"(fit > base, 줌 무관)** 를 세어 둔다.
// 방출 시점 계수기 — `fit > base` 인(=확장 여력이 있는) 헤더를 센다. 줌을 인자로 받지 않는 것이 핵심:
//   게이트가 z-독립이어야 self-lock 이 없다. build 시작 시 0 으로 리셋하고 각 헤더 방출에서 호출한다.
function _metaHdrFitReset() { _metaGraph._hdrFitScalable = 0; }
function _metaHdrFitNote(baseFont, boxW, textLen) {
  const base = (typeof baseFont === "number" && isFinite(baseFont) && baseFont > 0) ? baseFont : 10.5;
  const avail = Math.max(0, (typeof boxW === "number" && isFinite(boxW) ? boxW : 0) - _META_HDR_FIT_PAD);
  const n = Math.max(1, (typeof textLen === "number" && isFinite(textLen)) ? textLen : 1);
  if (avail / (n * _META_HDR_FIT_CHARW) > base) {
    _metaGraph._hdrFitScalable = (_metaGraph._hdrFitScalable || 0) + 1;
  }
}
function _metaHdrFitScalable() {
  const n = _metaGraph._hdrFitScalable;
  return (typeof n === "number" && n > 0);
}
function _metaLabelBandOf(zoom) {
  const z = (typeof zoom === "number" && isFinite(zoom) && zoom > 0) ? zoom : 1;
  const S = _META_LABEL_FONT_STEP;
  const q = (minPx) => Math.min(_META_LABEL_FONT_HI,
    Math.max(_META_LABEL_FONT_LO, Math.ceil((minPx / z) / S) * S));
  const hdr = _metaHdrFitScalable() ? ("/h" + _metaHdrFitBandOf(z)) : "";
  return q(_META_LABEL_MIN_PX) + "/" + q(_META_LABEL_HEADER_MIN_PX) + hdr;
}
// graph-perf(사용자 요청 2026-07-28 "성능 비용을 차후에 관측할 수 있는 구조"): 프론트 그래프 렌더 비용을
//   브라우저 콘솔·PB-0008 relay·헤드리스에서 동일하게 읽는 단일 관측 지점. 계측 전용(동작 분기 없음)이라
//   fail-soft — 전역 접근 실패(비브라우저 vm)면 로컬 객체를 돌려주고 조용히 버린다.
function _metaPerf() {
  const w = (typeof window !== "undefined") ? window : null;
  if (!w) return { label: {}, render: {} };
  if (!w.__META_GRAPH_PERF) w.__META_GRAPH_PERF = { label: {}, render: {} };
  return w.__META_GRAPH_PERF;
}
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


export { _META_AGG_ZOOM, _META_COL_LOD_MIN, _META_COL_LOD_ZOOM, _META_CULL_MARGIN, _META_CULL_MIN, _META_DIM_OPACITY, _META_EDGE_LOD_MIN, _META_EDGE_LOD_ZOOM, _META_HDR_FIT_MAX, _META_LABEL_HDR_KINDS, _META_LABEL_HEADER_MIN_PX, _META_LABEL_MIN_PX, _META_MIN_READ_ZOOM, _META_SEARCH_CAP, _META_TERMS_COMBO, _metaComboName, _metaGraph, _metaHdrFitBandOf, _metaHdrFitFont, _metaHdrFitNote, _metaHdrFitReset, _metaHdrFitScalable, _metaLabelBandOf, _metaNatSort, _metaPerf, _metaSchemaComboOf, _METLAY, _METtype, _METZ };
