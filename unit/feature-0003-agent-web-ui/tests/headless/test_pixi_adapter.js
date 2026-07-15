// feature-0016 §78 Phase B — SceneAdapter 순수 로직 격리검증 (node vm, Pixi 무의존).
//   카메라 변환 수학·fit·커서줌·대시 세그먼트·노드/combo bbox·hit-grid·scene diff.
//   렌더 자체(Pixi WebGL)는 win-browser 실증(TEST §78); 여기선 엔진 무관 계약을 잠근다.
// 사용: node test_pixi_adapter.js <graph-renderer-pixi.js path 또는 sed-번들 path>
"use strict";
const fs = require("fs");
const vm = require("vm");

const path = process.argv[2] || require("path").resolve(__dirname, "../../src/static/graph/graph-renderer-pixi.js");
let src = fs.readFileSync(path, "utf8");
// ES module → vm: export 접두 제거 + PixiAdapterPure 를 sandbox 로 노출.
src = src.replace(/^export const /m, "const ")
         .replace(/^export class /gm, "class ")
         .replace(/^export function /gm, "function ")
         .replace(/^export \{[^}]*\};?/gm, "");
const sandbox = { window: undefined, performance: { now: () => 0 }, module: {}, console };
vm.createContext(sandbox);
vm.runInContext(src + "\nthis.__Pure = PixiAdapterPure;\nthis.__Adapter = PixiGraphAdapter;", sandbox, { filename: "adapter.js" });
const Pure = sandbox.__Pure;
const Adapter = sandbox.__Adapter;

let pass = 0, fail = 0;
const approx = (a, b, e) => Math.abs(a - b) <= (e || 1e-6);
function ok(cond, name) { if (cond) { pass++; console.log("PASS " + name); } else { fail++; console.log("FAIL " + name); } }

// ── 카메라 변환 (model↔screen 왕복) ──
const cam = { zoom: 2, x: 100, y: 50 };
{
  const [sx, sy] = Pure.modelToScreen(10, 20, cam);      // 10*2+100=120, 20*2+50=90
  ok(sx === 120 && sy === 90, "T1 modelToScreen");
  const [mx, my] = Pure.screenToModel(120, 90, cam);
  ok(approx(mx, 10) && approx(my, 20), "T1 screenToModel 왕복");
}

// ── clampZoom ──
ok(Pure.clampZoom(10, [0.05, 4]) === 4 && Pure.clampZoom(0.01, [0.05, 4]) === 0.05, "T2 clampZoom 범위");

// ── fitCamera: bounds 를 뷰포트에 중앙 정합 ──
{
  const c = Pure.fitCamera({ x: 0, y: 0, w: 1000, h: 500 }, { w: 800, h: 600 }, { pad: 0, range: [0.05, 4] });
  ok(approx(c.zoom, 0.8), "T3 fit zoom = min(800/1000,600/500)=0.8");
  // 콘텐츠 중심(500,250)이 뷰포트 중심(400,300)에 오도록 pan
  ok(approx(500 * c.zoom + c.x, 400) && approx(250 * c.zoom + c.y, 300), "T3 fit 중앙정합");
  const c2 = Pure.fitCamera({ x: 0, y: 0, w: 10000, h: 10000 }, { w: 800, h: 600 }, { range: [0.05, 4], minReadZoom: 0.55 });
  ok(c2.zoom === 0.55, "T3 minReadZoom 클램프");
  ok(Pure.fitCamera(null, { w: 800, h: 600 }).zoom === 1, "T3 빈 bounds 폴백");
}

// ── zoomAroundCursor: 커서 아래 model 점이 화면 고정 ──
{
  const c0 = { zoom: 1, x: 0, y: 0 };
  const cur = { x: 300, y: 200 };
  const before = Pure.screenToModel(cur.x, cur.y, c0);
  const c1 = Pure.zoomAroundCursor(c0, 2, cur, [0.05, 4]);
  const after = Pure.modelToScreen(before[0], before[1], c1);
  ok(approx(after[0], cur.x) && approx(after[1], cur.y), "T4 커서고정 줌");
  ok(approx(c1.zoom, 2), "T4 줌 배율 적용");
}

// ── dashSegments: 총 on 길이 ≈ len*on/(on+off), 세그먼트 시작 단조증가 ──
{
  const segs = Pure.dashSegments(0, 0, 100, 0, [6, 4]);
  ok(segs.length >= 9 && segs.length <= 11, "T5 대시 세그먼트 수(100/10≈10)");
  let onLen = 0; for (const s of segs) onLen += Math.hypot(s[2] - s[0], s[3] - s[1]);
  ok(onLen > 55 && onLen < 65, "T5 on 총길이≈60% (100*6/10)");
  ok(segs[0][0] === 0 && segs[segs.length - 1][2] <= 100.001, "T5 경계 내");
}

// ── nodeBBox: rect 중심·circle 지름 ──
{
  const rb = Pure.nodeBBox({ type: "rect", style: { x: 100, y: 100, size: [150, 24] } });
  ok(rb.x === 25 && rb.y === 88 && rb.w === 150 && rb.h === 24, "T6 rect bbox(중심기준)");
  const cb = Pure.nodeBBox({ type: "circle", style: { x: 50, y: 50, size: 11 } });
  ok(approx(cb.x, 44.5) && approx(cb.w, 11), "T6 circle bbox(지름)");
}

// ── comboBBox: 자식 union + padding (auto-fit 대체) ──
{
  const nodes = [
    { id: "a", type: "rect", combo: "S1", style: { x: 100, y: 100, size: [150, 24] } },
    { id: "b", type: "rect", combo: "S1", style: { x: 100, y: 200, size: [150, 24] } },
    { id: "z", type: "rect", combo: "OTHER", style: { x: 999, y: 999, size: [150, 24] } },
  ];
  const bb = Pure.comboBBox("S1", nodes, [30, 16, 14, 16]);
  ok(bb !== null, "T7 combo bbox 존재");
  ok(bb.x === 25 - 16 && bb.y === 88 - 30, "T7 combo padding 좌상");
  ok(Pure.comboBBox("NONE", nodes) === null, "T7 자식없는 combo=null(무시)");
}

// ── contentBounds: 전체 union ──
{
  const built = { nodes: [{ id: "n", type: "rect", style: { x: 0, y: 0, size: [100, 40] } }], combos: [], edges: [] };
  const b = Pure.contentBounds(built);
  ok(b.x === -50 && b.y === -20 && b.w === 100 && b.h === 40, "T8 contentBounds");
  ok(Pure.contentBounds({ nodes: [], combos: [], edges: [] }).w === 0, "T8 빈 scene");
}

// ── hit-grid + hitTest: 최상위 z 반환 ──
{
  const nodes = [
    { id: "lo", type: "rect", style: { x: 100, y: 100, size: [80, 40], zIndex: 2 } },
    { id: "hi", type: "rect", style: { x: 100, y: 100, size: [40, 20], zIndex: 5 } },
    { id: "far", type: "rect", style: { x: 5000, y: 5000, size: [40, 20], zIndex: 9 } },
  ];
  const hg = Pure.buildHitGrid(nodes, 128);
  ok(Pure.hitTest(100, 100, hg, nodes).id === "hi", "T9 겹침 시 최상위 z");
  ok(Pure.hitTest(70, 100, hg, nodes).id === "lo", "T9 hi 밖=lo");
  ok(Pure.hitTest(300, 300, hg, nodes) === null, "T9 빈 공간=null");
  ok(Pure.hitTest(5000, 5000, hg, nodes).id === "far", "T9 원거리 셀 조회");
}

// ── diffScene: add/keep/remove ──
{
  const prev = new Set(["a", "b", "c"]);
  const built = { combos: [{ id: "S1" }], nodes: [{ id: "a" }, { id: "d" }], edges: [{ id: "e1" }] };
  const d = Pure.diffScene(prev, built);
  ok(d.keep.includes("a") && d.add.includes("d") && d.add.includes("S1") && d.add.includes("e1"), "T10 diff add/keep");
  ok(d.remove.includes("b") && d.remove.includes("c") && !d.remove.includes("a"), "T10 diff remove");
  ok(d.nextIds.has("S1") && d.nextIds.size === 4, "T10 nextIds");
}

// ── 실제 _metaG6Build 출력 형태를 소비할 수 있는지 (스펙 정합 — 대표 요소) ──
{
  // graph-core 가 만드는 대표 노드/엣지/combo shape 를 어댑터 순수함수가 처리하는지
  const table = { id: "T1", type: "rect", combo: "S1", states: ["selected"], data: { kind: "table", role: "master" },
    style: { x: 200, y: 150, size: [150, 24], radius: 6, fill: "#0072B2", stroke: "#fff", lineWidth: 1, zIndex: 4, labelText: "Payment", labelPlacement: "center", labelMaxWidth: 140 } };
  const col = { id: "C1", type: "circle", combo: "S1", data: { kind: "column" }, style: { x: 120, y: 180, size: 11, fill: "#5c6773", zIndex: 3, labelText: "PaymentId", labelPlacement: "right" } };
  const bb1 = Pure.nodeBBox(table), bb2 = Pure.nodeBBox(col);
  ok(bb1.w === 150 && bb2.w === 11, "T11 실 build 노드 shape 처리");
  const combo = { id: "S1", type: "rect", style: { padding: [30, 16, 14, 16], lineDash: [6, 4], fill: "#3f4b8c", fillOpacity: 0.045 } };
  const cbb = Pure.comboBBox(combo.id, [table, col], combo.style.padding);
  ok(cbb && cbb.w > 0 && cbb.h > 0, "T11 combo 자식 auto-fit");
}

// ── gap 수정 계약 (배선 정합) ──
// T12 combo hitTest: 노드 없는 combo 영역 → 그 combo
{
  const nodes = [{ id: "a", type: "rect", combo: "S1", style: { x: 100, y: 100, size: [150, 24] } }];
  const combos = [{ id: "S1", style: { padding: [30, 16, 14, 16] } }];
  ok(Pure.hitTestCombo(200, 130, combos, nodes) === null, "T12 combo bbox 밖=null");
  const h = Pure.hitTestCombo(100, 60, combos, nodes);   // 노드 위(88~112) 아닌 padding 영역
  ok(h && h.id === "S1", "T12 combo padding 영역 hit");
}
// T13 edge hitTest: 선분 근처 → 그 엣지
{
  const edges = [{ id: "e1", source: "a", target: "b" }];
  const pos = (id) => id === "a" ? [0, 0] : [100, 0];
  ok(Pure.hitTestEdge(50, 2, edges, pos, 6).id === "e1", "T13 선분 근처 hit");
  ok(Pure.hitTestEdge(50, 40, edges, pos, 6) === null, "T13 선분 밖=null");
  ok(Pure._segDist(50, 3, 0, 0, 100, 0) === 3, "T13 점-선분 거리");
}

// ── 미니맵 순수 로직 (이슈#2 클램프 · 이슈#3 역투영) ──
// T14 projection: 콘텐츠를 미니맵 박스에 letterbox
{
  const pr = Pure.minimapProjection({ x: 0, y: 0, w: 1000, h: 500 }, [168, 112], 6);
  ok(pr !== null, "T14 projection 존재");
  ok(approx(pr.s, (168 - 12) / 1000), "T14 letterbox scale = min((mw-2p)/w,(mh-2p)/h)");
  ok(Pure.minimapProjection({ x: 0, y: 0, w: 0, h: 0 }, [168, 112]) === null, "T14 빈 bounds=null");
}
// T15 역투영 왕복: 미니맵 로컬 → model
{
  const pr = Pure.minimapProjection({ x: 100, y: 50, w: 800, h: 400 }, [168, 112], 6);
  // model 중심(500,250)이 미니맵 로컬 어디에? ox+(500-100)*s, oy+(250-50)*s
  const lx = pr.ox + (500 - 100) * pr.s, ly = pr.oy + (250 - 50) * pr.s;
  const [mx, my] = Pure.minimapToModel(lx, ly, pr);
  ok(approx(mx, 500) && approx(my, 250), "T15 미니맵 로컬→model 역투영 왕복");
}
// T16 뷰포트 사각형 클램프: 뷰포트가 콘텐츠보다 크면 미니맵 박스로 클램프(벗어남 0)
{
  const pr = Pure.minimapProjection({ x: 0, y: 0, w: 1000, h: 500 }, [168, 112], 6);
  // 극단 줌아웃: 뷰포트 model 이 콘텐츠를 크게 초과 (-5000..6000)
  const r = Pure.minimapViewportRect([-5000, -5000], [6000, 6000], pr, [168, 112]);
  ok(r.x >= 0 && r.y >= 0 && r.x + r.w <= 168 && r.y + r.h <= 112, "T16 사각형 미니맵 박스 내 클램프(벗어남 0)");
  // 정상 뷰포트(콘텐츠 일부): 사각형이 박스 안 부분영역
  const r2 = Pure.minimapViewportRect([200, 100], [600, 300], pr, [168, 112]);
  ok(r2.w > 0 && r2.h > 0 && r2.x + r2.w <= 168, "T16 정상 뷰포트 부분사각형");
}

// ── 오브젝트 풀 서명 (§18.8 M2: 재사용/재생성 정합) ──
// T17 nodeSig: type/combo/style/states 변화 시 서명 differ, 동일 시 same
{
  const n = { id: "a", type: "rect", combo: "S", states: [], style: { x: 1, y: 2, size: [150, 24], fill: "#0072B2" } };
  const s0 = Pure.nodeSig(n);
  ok(Pure.nodeSig({ ...n }) === s0, "T17 동일 노드 서명 동일(재사용)");
  ok(Pure.nodeSig({ ...n, states: ["selected"] }) !== s0, "T17 states 변화 → 서명 differ(recreate)");
  ok(Pure.nodeSig({ ...n, style: { ...n.style, x: 999 } }) !== s0, "T17 위치 변화 → 서명 differ");
  ok(Pure.nodeSig({ ...n, type: "circle" }) !== s0, "T17 type 변화 → 서명 differ(m1 — circle/rect 기하)");
  ok(Pure.nodeSig({ ...n, fill: "x" }) === s0, "T17 비-style 필드 무관(fill 은 style 안)");
}
// T18 edgeSig: 끝점 이동 시 differ (노드 이동 → 엣지 재생성)
{
  const e = { id: "e1", source: "a", target: "b", style: { stroke: "#000" } };
  const s0 = Pure.edgeSig(e, [0, 0], [100, 0]);
  ok(Pure.edgeSig(e, [0, 0], [100, 0]) === s0, "T18 끝점 동일 → 서명 동일");
  ok(Pure.edgeSig(e, [0, 0], [100, 50]) !== s0, "T18 끝점 이동 → 서명 differ(재생성)");
  ok(Pure.edgeId({ source: "a", target: "b" }).startsWith("__e:"), "T18 id 없는 엣지 폴백 키");
}
// T19 comboSig: bbox(자식 파생) 변화 시 differ
{
  const c = { id: "S", style: { fill: "#3f4b8c", lineDash: [6, 4] } };
  const s0 = Pure.comboSig(c, { x: 0, y: 0, w: 200, h: 100 });
  ok(Pure.comboSig(c, { x: 0, y: 0, w: 200, h: 100 }) === s0, "T19 bbox 동일 → 서명 동일");
  ok(Pure.comboSig(c, { x: 0, y: 0, w: 250, h: 100 }) !== s0, "T19 bbox 변화(자식 이동) → 서명 differ");
}

// T20 hexToTint (BitmapText tint 파싱, §80 — 실 PixiAdapterPure.hexToTint 경로 검증. 비-hex=valid:false→Text 폴백)
{
  ok(Pure.hexToTint("#ffffff").tint === 0xffffff && Pure.hexToTint("#ffffff").valid, "T20 흰색 파싱");
  ok(Pure.hexToTint("#161b22").tint === 0x161b22, "T20 어두운색 파싱");
  ok(Pure.hexToTint("#fff").tint === 0xffffff && Pure.hexToTint("#fff").valid, "T20 3자리 확장");
  ok(Pure.hexToTint(0x7b2fbe).tint === 0x7b2fbe, "T20 number 통과");
  ok(Pure.hexToTint("zzz").valid === false, "T20 비-hex → valid:false(Text 폴백)");
  ok(Pure.hexToTint("rgb(1,2,3)").valid === false, "T20 rgb() → valid:false");
  ok(Pure.hexToTint("white").valid === false, "T20 named → valid:false");
}

// ── T21 _pick 3-tier 층서 (graph-ctxmenu hit-test 회귀): 구체요소 > 스키마 combo > cat-bg ──
//   결함(수정 전): CAT 밴드 배경이 node(z=-1)로 built.nodes 에 있어 _pick 의 node-우선 반환이
//   스키마 클러스터 빈 배경(combo 폴백 대상) 우클릭을 CAT node 로 가로채 '카테고리 메뉴' 오라우팅했고,
//   반대로 밴드 위 카드/클러스터(z=4)가 CAT 를 눌러 밴드 우클릭이 '스키마 메뉴'로 샜다.
{
  const nodes = [
    // 제품 카테고리 밴드 배경 — 멤버 클러스터 전체를 덮음(center 300,300 → x 0..600, y 100..500), z=-1
    { id: "CAT:prod", type: "rect", data: { kind: "cat-bg", cat: "prod" }, style: { x: 300, y: 300, size: [600, 400], zIndex: -1 } },
    // 접힌 스키마 카드 SC — CAT 밴드 내부, z=4 (x 125..275, y 170..230)
    { id: "SC:s1", type: "rect", combo: "s1", data: { kind: "schema-card" }, style: { x: 200, y: 200, size: [150, 60], zIndex: 4 } },
    // 펼친 스키마 클러스터 s2 의 자식 테이블 — combo bbox 파생용, z=4 (x 375..525, y 238..262)
    { id: "t1", type: "rect", combo: "s2", data: { kind: "table" }, style: { x: 450, y: 250, size: [150, 24], zIndex: 4 } },
  ];
  const combos = [{ id: "s2", style: { padding: [30, 16, 14, 16] } }];   // s2 bbox ≈ x 359..541, y 208..276
  const hg = Pure.buildHitGrid(nodes, 128);
  const ctx = { _hitGrid: hg, _built: { nodes, combos }, _isCatBg: Adapter.prototype._isCatBg };
  const pick = (x, y) => Adapter.prototype._pick.call(ctx, x, y);

  // 수정 전 결함 witness: 필터 없는 raw hitTest 는 스키마 combo 영역(365,270)에서 CAT node 를 반환(오라우팅 근원)
  ok(Pure.hitTest(365, 270, hg, nodes) && Pure.hitTest(365, 270, hg, nodes).id === "CAT:prod", "T21 (witness) 수정 전엔 combo 영역이 CAT node 로 가로채짐");

  // tier1: 구체 요소 — 스키마 카드 위 → SC (카테고리 밴드 무관)
  const pCard = pick(200, 200);
  ok(pCard && pCard.id === "SC:s1" && !pCard.__combo, "T21 스키마 카드 우클릭 → SC 노드(카테고리 아님)");
  // tier1: 테이블 노드 위 → t1
  const pTbl = pick(450, 250);
  ok(pTbl && pTbl.id === "t1" && !pTbl.__combo, "T21 클러스터 멤버 테이블 → 그 노드");
  // tier2: 스키마 클러스터 빈 배경(combo, cat 밴드와 겹침) → combo s2 ('스키마 메뉴') — 핵심 fix
  const pCombo = pick(365, 270);
  ok(pCombo && pCombo.__combo && pCombo.id === "s2", "T21 스키마 클러스터 빈배경 → combo(스키마 메뉴), CAT 가로채기 제거");
  // tier3: 카테고리 밴드 고유 여백(카드·combo 없음) → CAT ('카테고리 메뉴')
  const pCat = pick(50, 130);
  ok(pCat && pCat.id === "CAT:prod" && !pCat.__combo, "T21 카테고리 밴드 고유 여백 → CAT(카테고리 메뉴)");
  // 빈 공간(밴드 밖) → null
  ok(pick(2000, 2000) === null, "T21 밴드 밖 빈 공간 → null(canvas)");
}

// ── T22 컨텐츠 카테고리(sim-group) 우클릭 = 자기 노드 + band-wins 철회 회귀 ──
//   band-wins 철회(2026-07-15, 사용자 정정 "제품 카테고리 밴드↔컨텐츠 카테고리 착각"): 우클릭은 이제 _pick(=좌클릭·드래그와 동일 hit).
//   ①sim-group 박스/헤더(GB/GH)는 tier1 실요소라 밴드로 흡수되지 않고 자기 노드로 반환 → graph-core 가 **컨텐츠 카테고리 메뉴**로 라우팅.
//   ②밴드 위 스키마 클러스터는 더 이상 카테고리로 승격되지 않는다(스키마 메뉴 복원). ③_pickContext 는 제거됨.
{
  const nodes = [
    { id: "CAT:prod", type: "rect", data: { kind: "cat-bg", cat: "prod" }, style: { x: 300, y: 300, size: [600, 400], zIndex: -1 } },   // 밴드 x0..600 y100..500
    { id: "SC:s1", type: "rect", combo: "s1", data: { kind: "schema-card" }, style: { x: 200, y: 200, size: [150, 60], zIndex: 4 } },    // 밴드 내 스키마 카드 x125..275 y170..230
    { id: "GB:grp1", type: "rect", combo: "s2", data: { kind: "group-bg", group: "grp1", schema: "s2" }, style: { x: 450, y: 400, size: [160, 80], zIndex: 1 } },   // 밴드 내 sim-group 박스 x370..530 y360..440
    { id: "GH:grp1", type: "rect", combo: "s2", data: { kind: "group-hd", group: "grp1", schema: "s2" }, style: { x: 400, y: 370, size: [80, 18], zIndex: 5 } },     // sim-group 헤더 x360..440 y361..379
  ];
  const combos = [{ id: "s2", style: { padding: [30, 16, 14, 16] } }];
  const hg = Pure.buildHitGrid(nodes, 128);
  const ctx = { _hitGrid: hg, _built: { nodes, combos }, _isCatBg: Adapter.prototype._isCatBg };
  const pick = (x, y) => Adapter.prototype._pick.call(ctx, x, y);

  // ① 밴드 위 sim-group 박스(GB) 우클릭 → 그 GB 노드(밴드로 흡수 안 됨) → 컨텐츠 카테고리 메뉴
  const pGB = pick(450, 400);
  ok(pGB && pGB.id === "GB:grp1" && !pGB.__combo, "T22 밴드 위 sim-group 박스 우클릭 → GB 노드(컨텐츠 카테고리), 밴드 흡수 안 함");
  // ① sim-group 헤더(GH, z=5) 우클릭 → GH 노드
  const pGH = pick(400, 370);
  ok(pGH && pGH.id === "GH:grp1", "T22 sim-group 헤더 우클릭 → GH 노드(컨텐츠 카테고리)");
  // ② band-wins 철회: 밴드 위 스키마 카드 우클릭 → SC(스키마 메뉴), 카테고리로 승격 안 됨
  const pSC = pick(200, 200);
  ok(pSC && pSC.id === "SC:s1" && !pSC.__combo, "T22 밴드 위 스키마 카드 우클릭 → SC(스키마 메뉴), band-wins 승격 제거");
  // ③ _pickContext 제거됨(회귀 방지)
  ok(typeof Adapter.prototype._pickContext === "undefined", "T22 _pickContext 제거됨(band-wins 철회)");
}

console.log("──────");
console.log((fail === 0 ? "ALL PASS" : "FAIL") + " — " + pass + " PASS / " + fail + " FAIL");
process.exit(fail === 0 ? 0 : 1);
