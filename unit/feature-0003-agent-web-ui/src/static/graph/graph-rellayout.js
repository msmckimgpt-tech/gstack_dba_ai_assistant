// ITEM-09 batch3 — graph.js L631~L785 pure move: graph-rel-layout: 관계 기반 배치 pre-pass.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { _metaGraph, _metaNatSort } from "./graph-state.js?v=dev";
import { _metaColParent } from "./graph-ctxmenu.js?v=dev";

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


export { _metaRelAdjacency, _metaRelOrderAll, _metaRelSchemaOrder };
