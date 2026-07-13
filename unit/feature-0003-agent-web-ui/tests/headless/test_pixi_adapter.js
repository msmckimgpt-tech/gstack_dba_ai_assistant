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
vm.runInContext(src + "\nthis.__Pure = PixiAdapterPure;", sandbox, { filename: "adapter.js" });
const Pure = sandbox.__Pure;

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

console.log("──────");
console.log((fail === 0 ? "ALL PASS" : "FAIL") + " — " + pass + " PASS / " + fail + " FAIL");
process.exit(fail === 0 ? 0 : 1);
