// ITEM-09 batch3 — graph.js L786~L1027 pure move: graph-simgroups: 유사 속성 그룹.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { _META_TERMS_COMBO, _metaComboName, _metaGraph, _metaNatSort } from "./graph-state.js?v=dev";
import { _META_ROLE, _metaRoleOf } from "./graph-roleviz.js?v=dev";
import { _metaRelOrderAll, _metaRelSchemaOrder } from "./graph-rellayout.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)

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


export { _META_GROUP_TINTS, _metaCatAssign, _metaSimGroups, _metaStableSeq };
