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
// T17 nodeShapeSig: type/combo/style/states 변화 시 서명 differ, **위치(x/y)만 변하면 동일**.
//   graph-expand-perf: 위치는 컨테이너 `position.set` 으로만 쓰이므로 파기·재생성 사유가 아니다 —
//   서명에서 빼야 masonry 재균형(형제 수백 이동)이 라벨 재생성 폭풍을 부르지 않는다.
{
  const n = { id: "a", type: "rect", combo: "S", states: [], style: { x: 1, y: 2, size: [150, 24], fill: "#0072B2" } };
  const s0 = Pure.nodeShapeSig(n);
  ok(Pure.nodeShapeSig({ ...n }) === s0, "T17 동일 노드 서명 동일(재사용)");
  ok(Pure.nodeShapeSig({ ...n, states: ["selected"] }) !== s0, "T17 states 변화 → 서명 differ(recreate)");
  ok(Pure.nodeShapeSig({ ...n, style: { ...n.style, x: 999, y: -40 } }) === s0, "T17 위치만 변화 → 서명 동일(재배치만)");
  ok(Pure.nodeShapeSig({ ...n, style: { ...n.style, size: [151, 24] } }) !== s0, "T17 크기 변화 → 서명 differ(기하 재생성)");
  ok(Pure.nodeShapeSig({ ...n, style: { ...n.style, labelText: "t" } }) !== s0, "T17 라벨 변화 → 서명 differ");
  ok(Pure.nodeShapeSig({ ...n, style: { ...n.style, opacity: 0.3 } }) !== s0, "T17 dim(opacity) 변화 → 서명 differ");
  ok(Pure.nodeShapeSig({ ...n, type: "circle" }) !== s0, "T17 type 변화 → 서명 differ(m1 — circle/rect 기하)");
  ok(Pure.nodeShapeSig({ ...n, combo: "T" }) !== s0, "T17 combo 변화 → 서명 differ");
  ok(Pure.nodeShapeSig({ ...n, fill: "x" }) === s0, "T17 비-style 필드 무관(fill 은 style 안)");
  ok(typeof Pure.nodeSig === "undefined", "T17 위치-포함 nodeSig 는 폐기(SSOT 단일화)");
}
// T18 edgeSig: 끝점 이동 시 differ (노드 이동 → 엣지 재생성)
{
  const e = { id: "e1", source: "a", target: "b", style: { stroke: "#000" } };
  const s0 = Pure.edgeSig(e, [0, 0], [100, 0]);
  ok(Pure.edgeSig(e, [0, 0], [100, 0]) === s0, "T18 끝점 동일 → 서명 동일");
  ok(Pure.edgeSig(e, [0, 0], [100, 50]) !== s0, "T18 끝점 이동 → 서명 differ(재생성)");
  ok(Pure.edgeId({ source: "a", target: "b" }).startsWith("__e:"), "T18 id 없는 엣지 폴백 키");
}
// T19 comboShapeSig: bbox **크기** 변화 시 differ, 원점(x/y) 이동만이면 동일(재배치).
//   `_drawCombo` 는 roundRect(0,0,w,h) 로 그리고 x/y 는 컨테이너 위치라 노드와 같은 분리가 성립한다.
{
  const c = { id: "S", style: { fill: "#3f4b8c", lineDash: [6, 4] } };
  const s0 = Pure.comboShapeSig(c, { x: 0, y: 0, w: 200, h: 100 });
  ok(Pure.comboShapeSig(c, { x: 0, y: 0, w: 200, h: 100 }) === s0, "T19 bbox 동일 → 서명 동일");
  ok(Pure.comboShapeSig(c, { x: 40, y: -80, w: 200, h: 100 }) === s0, "T19 원점만 이동 → 서명 동일(재배치만)");
  ok(Pure.comboShapeSig(c, { x: 0, y: 0, w: 250, h: 100 }) !== s0, "T19 폭 변화(자식 증가) → 서명 differ");
  ok(Pure.comboShapeSig(c, { x: 0, y: 0, w: 200, h: 160 }) !== s0, "T19 높이 변화(컬럼 펼침) → 서명 differ");
  ok(typeof Pure.comboSig === "undefined", "T19 위치-포함 comboSig 는 폐기(SSOT 단일화)");
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

// T20b hasEmoji (graph-emoji-color fix — 색 이모지 라벨은 BitmapText 아닌 Text 경로. 실 PixiAdapterPure.hasEmoji 검증)
//   버그: BitmapText 는 색 이모지를 alpha 마스크+tint 로 단색 실루엣(검은/흰)으로만 렌더 → _makeText 에서 emoji 포함 시 Text 강등.
{
  // 테이블 역할 아이콘(_META_ROLE.icon) 전종 — 전부 emoji 로 감지돼야(→ Text 컬러 렌더)
  ok(Pure.hasEmoji("📊 stats_daily"), "T20b 📊 stats(1F4CA) 감지");
  ok(Pure.hasEmoji("👤 members"), "T20b 👤 account(1F464) 감지");
  ok(Pure.hasEmoji("💳 orders"), "T20b 💳 transaction(1F4B3) 감지");
  ok(Pure.hasEmoji("📜 audit_log"), "T20b 📜 log(1F4DC) 감지");
  ok(Pure.hasEmoji("🔗 user_role_map"), "T20b 🔗 mapping(1F517) 감지");
  ok(Pure.hasEmoji("⚙️ sys_config"), "T20b ⚙️ config(2699+FE0F VS16) 감지");
  ok(Pure.hasEmoji("📘 code_master"), "T20b 📘 master(1F4D8) 감지");
  ok(Pure.hasEmoji("📦 etc_misc"), "T20b 📦 etc(1F4E6) 감지");
  ok(Pure.hasEmoji("🗂 카테고리"), "T20b 🗂 카테고리 헤더(1F5C2) 감지");
  // 평문 라벨(테이블/컬럼명·컨트롤 글리프)은 비-emoji → BitmapText 최적 경로 유지
  ok(!Pure.hasEmoji("orders"), "T20b 평문 라벨 비-emoji");
  ok(!Pure.hasEmoji("user_id"), "T20b 컬럼명 비-emoji");
  ok(!Pure.hasEmoji("−"), "T20b 접기 컨트롤 −(U+2212 minus) 비-emoji");
  ok(!Pure.hasEmoji("+"), "T20b 펼침 컨트롤 + 비-emoji");
  ok(!Pure.hasEmoji("ƒ get_total"), "T20b 함수 접두 ƒ(U+0192) 비-emoji");
  ok(!Pure.hasEmoji("스키마명 한글"), "T20b 한글 라벨 비-emoji");
  ok(Pure.hasEmoji(null) === false && Pure.hasEmoji(undefined) === false, "T20b null/undefined 안전");
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
  // graph-move-anim: 트윈 없음(_tweenPos/_tweenMovers null) → `_hitNodes` 가 기존 grid 경로 그대로.
  const ctx = { _hitGrid: hg, _built: { nodes, combos }, _isCatBg: Adapter.prototype._isCatBg,
    _tweenPos: null, _tweenMovers: null, _hitNodes: Adapter.prototype._hitNodes };
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
  // graph-move-anim: 트윈 없음(_tweenPos/_tweenMovers null) → `_hitNodes` 가 기존 grid 경로 그대로.
  const ctx = { _hitGrid: hg, _built: { nodes, combos }, _isCatBg: Adapter.prototype._isCatBg,
    _tweenPos: null, _tweenMovers: null, _hitNodes: Adapter.prototype._hitNodes };
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

// ── T23 graph-edge-follow-drag: 노드 드래그 시 incident 엣지 증분 재그림(특히 cross-category) ──
//   회귀: 엣지는 절대좌표를 Graphics 에 bake 한 독립 오브젝트라(_drawEdge) 노드 Container 이동으로 안 따라온다
//   → 예전엔 full draw()(줌 밴드 rebuild 등)만 edgeSig(끝점 포함) 변경을 감지해 재생성 → "줌 아웃해야 관계선 갱신".
//   _refreshIncidentEdges 는 "source 또는 target 이 이동집합에 포함"된 엣지만 재그린다:
//     ① 내부 엣지(양끝 이동) ② cross-category 엣지(한끝만 이동 — 사용자 정정: 다른 제품 카테고리로 가는 연결선
//        구조 갱신) ③ 무관 엣지(양끝 미이동, skip).
{
  const nodes = [
    { id: "A", type: "rect", style: { x: 10, y: 10, size: [20, 10] } },    // cat1 member
    { id: "B", type: "rect", style: { x: 50, y: 10, size: [20, 10] } },    // cat1 member (드래그로 이동)
    { id: "C", type: "rect", style: { x: 200, y: 200, size: [20, 10] } },  // cat2 member (미이동)
    { id: "D", type: "rect", style: { x: 300, y: 300, size: [20, 10] } },  // 무관(미이동)
  ];
  const edges = [
    { id: "e1", source: "A", target: "B", style: {} },   // 내부(cat1↔cat1)
    { id: "e2", source: "B", target: "C", style: {} },   // cross-category(cat1↔cat2) — 핵심 케이스
    { id: "e3", source: "C", target: "D", style: {} },   // 무관(둘 다 미이동)
  ];
  const drawn = [];   // _drawEdge 호출 기록
  const world = { children: [], addChild(o) { this.children.push(o); }, removeChild(o) { const i = this.children.indexOf(o); if (i >= 0) this.children.splice(i, 1); } };
  const objs = new Map();
  for (const e of edges) objs.set(e.id, { __stale: e.id, destroy() {} });   // 기존(옛 위치) 엣지 오브젝트
  const ctx = {
    world, _built: { nodes, edges, combos: [] }, _objs: objs, _objSig: new Map(),
    getElementPosition: Adapter.prototype.getElementPosition,
    _boundsOf: Adapter.prototype._boundsOf,
    _incidentEdges: Adapter.prototype._incidentEdges,   // graph-edge-drag-perf: 인덱스 부재 → O(E) filter 폴백
    _resolvePos: Adapter.prototype._resolvePos,   // _nodeById 부재 → getElementPosition 폴백
    _drawEdge(e, a, b) { const g = { __edge: e.id, a, b, destroy() {} }; drawn.push(g); return g; },
  };
  // 드래그: cat1(A,B) 이동 — translateElementTo 가 style 을 먼저 갱신하는 실제 순서를 모사(B 만 새 위치).
  nodes[1].style.x = 500; nodes[1].style.y = 400;
  Adapter.prototype._refreshIncidentEdges.call(ctx, ["A", "B"]);

  const ids = drawn.map((g) => g.__edge).sort();
  ok(ids.length === 2 && ids[0] === "e1" && ids[1] === "e2", "T23 incident 엣지만 재그림(e1 내부·e2 cross), 무관 e3 skip");
  // cross-category e2: B(이동) 끝점은 새 좌표, C(미이동) 끝점은 옛 좌표 → 연결선 구조가 새 위치로 갱신
  const g2 = drawn.find((g) => g.__edge === "e2");
  ok(g2 && g2.a[0] === 500 && g2.a[1] === 400, "T23 cross-category 엣지의 이동 끝점(B) 새 좌표 갱신");
  ok(g2 && g2.b[0] === 200 && g2.b[1] === 200, "T23 cross-category 엣지의 미이동 끝점(C) 옛 좌표 유지");
  ok(ctx._objs.get("e2") === g2 && world.children.indexOf(g2) >= 0, "T23 _objs·world 새 엣지로 교체");
  ok(ctx._objSig.get("e2") === Pure.edgeSig(edges[1], [500, 400], [200, 200]), "T23 _objSig 갱신(다음 full draw 재사용)");
  ok(ctx._objs.get("e3").__stale === "e3", "T23 무관 엣지 e3 오브젝트 불변");
  // 빈 이동집합·null 은 no-op(방어)
  const before = drawn.length;
  Adapter.prototype._refreshIncidentEdges.call(ctx, []);
  Adapter.prototype._refreshIncidentEdges.call(ctx, null);
  ok(drawn.length === before, "T23 빈/null 이동집합 no-op");
}

// ── T24 graph-edge-drag-perf: 드래그 재그림 3 lever(in-place 재사용·인접 인덱스·rAF 코얼레싱) ──
//   ① 기존 엣지 Graphics 재사용(_paintEdge, destroy/recreate·GC 회피) ② _edgeIndex 로 O(incident) ③ _scheduleEdgeRefresh rAF 병합.
{
  // ① in-place 재사용: 기존 엣지 오브젝트(clear 보유·parent===world)는 _paintEdge 로 재사용, _drawEdge/destroy 안 함
  const nodes = [
    { id: "A", type: "rect", style: { x: 0, y: 0, size: [10, 10] } },
    { id: "B", type: "rect", style: { x: 100, y: 0, size: [10, 10] } },
  ];
  const edges = [{ id: "e1", source: "A", target: "B", style: {} }];
  const world = { children: [], addChild(o) { this.children.push(o); }, removeChild(o) { const i = this.children.indexOf(o); if (i >= 0) this.children.splice(i, 1); } };
  const existing = { __edge: "e1", clear() { this.cleared = (this.cleared || 0) + 1; }, parent: world, destroy() { this.destroyed = true; } };
  world.children.push(existing);
  let paintCalls = 0, drawCalls = 0;
  const ctx = {
    world, _built: { nodes, edges, combos: [] }, _objs: new Map([["e1", existing]]), _objSig: new Map(),
    getElementPosition: Adapter.prototype.getElementPosition, _boundsOf: Adapter.prototype._boundsOf,
    _incidentEdges: Adapter.prototype._incidentEdges,
    _resolvePos: Adapter.prototype._resolvePos,
    _paintEdge(g, a2, aa, bb) { paintCalls++; g.__painted = [aa, bb]; return g; },
    _drawEdge(e, aa, bb) { drawCalls++; return { __edge: e.id, aa, bb, destroy() {} }; },
  };
  nodes[1].style.x = 500;   // B 이동
  Adapter.prototype._refreshIncidentEdges.call(ctx, ["B"]);
  ok(paintCalls === 1 && drawCalls === 0, "T24 in-place 재사용(_paintEdge 1·_drawEdge 0)");
  ok(ctx._objs.get("e1") === existing && !existing.destroyed, "T24 재사용 시 동일 Graphics 유지·destroy 안 함");
  ok(existing.__painted && existing.__painted[0][0] === 0 && existing.__painted[1][0] === 500, "T24 재사용 엣지 새 끝점 좌표로 re-path(A[0]·B[500])");
  ok(world.children.length === 1, "T24 재사용은 world 자식 add/remove 없음");
}
{
  // ② 인접 인덱스 incident dedup + 폴백 동치
  const eAB = { id: "eAB", source: "A", target: "B" }, eBC = { id: "eBC", source: "B", target: "C" }, eCD = { id: "eCD", source: "C", target: "D" };
  const edges = [eAB, eBC, eCD];
  const edgeIndex = new Map([["A", [eAB]], ["B", [eAB, eBC]], ["C", [eBC, eCD]], ["D", [eCD]]]);
  const inc = Adapter.prototype._incidentEdges.call({ _built: { edges }, _edgeIndex: edgeIndex }, new Set(["A", "B"])).map(e => e.id).sort();
  ok(inc.length === 2 && inc[0] === "eAB" && inc[1] === "eBC", "T24 인접 인덱스 incident dedup(eAB 1회·eBC, eCD 제외)");
  const inc2 = Adapter.prototype._incidentEdges.call({ _built: { edges }, _edgeIndex: null }, new Set(["A", "B"])).map(e => e.id).sort();
  ok(inc2.length === 2 && inc2[0] === "eAB" && inc2[1] === "eBC", "T24 인덱스 부재 O(E) 폴백 동치");
}
{
  // ③ scheduler: 비-rAF 즉시 동기 폴백(sandbox 에 requestAnimationFrame 없음 = 기본)
  const calls = [];
  const ctxSync = { _refreshIncidentEdges(ids) { calls.push(["refresh", [...ids].sort().join(",")]); }, _render() { calls.push(["render"]); } };
  Adapter.prototype._scheduleEdgeRefresh.call(ctxSync, ["A", "B"]);
  ok(calls.length === 2 && calls[0][0] === "refresh" && calls[0][1] === "A,B" && calls[1][0] === "render", "T24 scheduler 비-rAF 즉시 동기 폴백");
  // rAF 주입(sandbox 컨텍스트에 노출) → 코얼레싱 검증
  const flushFns = [];
  sandbox.requestAnimationFrame = (fn) => { flushFns.push(fn); return flushFns.length; };
  sandbox.cancelAnimationFrame = () => {};
  const c2 = [];
  const ctxRaf = { _refreshIncidentEdges(ids) { c2.push([...ids].sort().join(",")); }, _render() { c2.push("render"); } };
  Adapter.prototype._scheduleEdgeRefresh.call(ctxRaf, ["A"]);
  Adapter.prototype._scheduleEdgeRefresh.call(ctxRaf, ["B", "C"]);   // 같은 프레임 누적
  ok(flushFns.length === 1 && c2.length === 0, "T24 scheduler rAF 코얼레싱(2 호출→rAF 1개·미실행)");
  flushFns[0]();   // 프레임 발화
  ok(c2.length === 2 && c2[0] === "A,B,C" && c2[1] === "render", "T24 flush 시 누적 id(A,B,C) 1회 재그림+렌더");
  // _flushEdgeRefresh 즉시 반영(pending 있을 때)
  const c3 = [];
  const ctxFlush = { _pendingMoved: new Set(["X", "Y"]), _pendingRaf: 7, _refreshIncidentEdges(ids) { c3.push([...ids].sort().join(",")); }, _render() { c3.push("render"); } };
  Adapter.prototype._flushEdgeRefresh.call(ctxFlush);
  ok(c3.length === 2 && c3[0] === "X,Y" && c3[1] === "render" && ctxFlush._pendingRaf === 0 && ctxFlush._pendingMoved === null, "T24 _flushEdgeRefresh 즉시 반영+pending 클리어");
  delete sandbox.requestAnimationFrame; delete sandbox.cancelAnimationFrame;   // 복원(다른 테스트 격리)
}

// ── T25 graph-edge-drag-perf 실-경로 하드닝(적대 리뷰 C1~C4·P3) ──
{
  // C1: 실 _paintEdge 재사용 — stale 라벨 자식 제거 + geometry 재-path(라벨 있는 엣지)
  const staleLabel = { __stale: true, destroy() { this.destroyed = true; } };
  const g = {
    children: [staleLabel], _ops: [], zIndex: 0,
    clear() { this._ops.push("clear"); return this; },
    moveTo() { this._ops.push("moveTo"); return this; },
    lineTo() { this._ops.push("lineTo"); return this; },
    stroke() { this._ops.push("stroke"); return this; },
    removeChildren() { const c = this.children; this.children = []; this._ops.push("removeChildren"); return c; },
    addChild(o) { this.children.push(o); this._ops.push("addChild"); return o; },
  };
  let addedText = null;
  const ctx = { P: null, _arrow() {}, _makeText(t) { addedText = { __text: t, anchor: { set() {} }, position: { set() {} }, width: 10 }; return addedText; } };
  const edge = { source: "A", target: "B", style: { labelText: "REL", stroke: "#000", lineWidth: 2 } };
  Adapter.prototype._paintEdge.call(ctx, g, edge, [0, 0], [100, 0]);
  ok(g._ops[0] === "clear", "T25 실 _paintEdge 첫 동작 clear()");
  ok(staleLabel.destroyed === true, "T25 재사용 시 stale 라벨 자식 destroy");
  ok(g._ops.includes("moveTo") && g._ops.includes("lineTo") && g._ops.includes("stroke"), "T25 새 geometry 재-path");
  ok(g.children.length === 1 && g.children[0] === addedText, "T25 stale 제거 후 새 라벨 자식 1개(이중 렌더 아님)");
  ok(g.zIndex === 2, "T25 엣지 zIndex 2 유지");
}
{
  // C2: 순수 buildEdgeIndex — 자기루프 1회·null/빈 안전·incident dedup 계약
  const eAB = { source: "A", target: "B" }, eBC = { source: "B", target: "C" }, eSelf = { source: "X", target: "X" };
  const idx = Pure.buildEdgeIndex([eAB, eBC, eSelf]);
  ok(idx.get("A").length === 1 && idx.get("A")[0] === eAB, "T25 buildEdgeIndex A→[eAB]");
  ok(idx.get("B").length === 2, "T25 buildEdgeIndex B→[eAB,eBC]");
  ok(idx.get("X").length === 1, "T25 buildEdgeIndex 자기루프(source===target) 1회만 등재");
  ok(Pure.buildEdgeIndex(null).size === 0 && Pure.buildEdgeIndex([]).size === 0, "T25 buildEdgeIndex null/빈 안전");
}
{
  // C3: 재사용 불가(old 에 clear 없음 = node/combo Container) → 재생성(destroy+_drawEdge)
  const nodes = [{ id: "A", type: "rect", style: { x: 0, y: 0, size: [10, 10] } }, { id: "B", type: "rect", style: { x: 50, y: 0, size: [10, 10] } }];
  const edges = [{ id: "e1", source: "A", target: "B", style: {} }];
  const world = { children: [], addChild(o) { this.children.push(o); }, removeChild(o) { const i = this.children.indexOf(o); if (i >= 0) this.children.splice(i, 1); } };
  const nonReusable = { __container: true, parent: world, destroy() { this.destroyed = true; } };   // clear 없음
  world.children.push(nonReusable);
  let paintCalls = 0, drawCalls = 0;
  const ctx = { world, _built: { nodes, edges, combos: [] }, _objs: new Map([["e1", nonReusable]]), _objSig: new Map(),
    _incidentEdges: Adapter.prototype._incidentEdges, _resolvePos: Adapter.prototype._resolvePos, getElementPosition: Adapter.prototype.getElementPosition, _boundsOf: Adapter.prototype._boundsOf,
    _paintEdge() { paintCalls++; }, _drawEdge(e) { drawCalls++; return { __edge: e.id, destroy() {} }; } };
  Adapter.prototype._refreshIncidentEdges.call(ctx, ["A"]);
  ok(paintCalls === 0 && drawCalls === 1 && nonReusable.destroyed === true, "T25 재사용 불가(clear 없는 Container) → destroy+_drawEdge(else 분기)");
}
{
  // C4: incident 이나 끝점 미해소(pos null) → skip(재그림 안 함)
  const nodes = [{ id: "A", type: "rect", style: { x: 0, y: 0, size: [10, 10] } }];   // B 없음
  const edges = [{ id: "e1", source: "A", target: "B", style: {} }];
  const world = { children: [], addChild(o) { this.children.push(o); }, removeChild() {} };
  let drawCalls = 0;
  const ctx = { world, _built: { nodes, edges, combos: [] }, _objs: new Map(), _objSig: new Map(),
    _incidentEdges: Adapter.prototype._incidentEdges, _resolvePos: Adapter.prototype._resolvePos, getElementPosition: Adapter.prototype.getElementPosition, _boundsOf: Adapter.prototype._boundsOf,
    _drawEdge(e) { drawCalls++; return { __edge: e.id }; } };
  Adapter.prototype._refreshIncidentEdges.call(ctx, ["A"]);
  ok(drawCalls === 0 && world.children.length === 0, "T25 미해소 끝점 incident 엣지 skip(재그림 안 함)");
}
{
  // P3: _resolvePos 는 _nodeById 있으면 live node.style O(1) 조회(getElementPosition 미호출), 비-node 폴백
  const nodeA = { id: "A", style: { x: 7, y: 9 } };
  let gept = 0;
  const ctx = { _nodeById: new Map([["A", nodeA]]), getElementPosition() { gept++; return [0, 0]; } };
  const p = Adapter.prototype._resolvePos.call(ctx, "A");
  ok(p[0] === 7 && p[1] === 9 && gept === 0, "T25 _resolvePos _nodeById O(1)(getElementPosition 미호출)");
  Adapter.prototype._resolvePos.call(ctx, "SC:x");
  ok(gept === 1, "T25 _resolvePos 비-node(_nodeById miss) → getElementPosition 폴백");
}

// ── T26 graph-label-hover-expand: 잘린 라벨 hover 확장 ──
{
  // 기준 칩: TW=150 / labelMaxWidth=140 (_metaTableStyle 실값) — 전체 라벨 210px 로 잘린 상태.
  const tbl = (over) => ({ id: "t1", type: "rect", style: Object.assign({
    x: 100, y: 50, size: [150, 24], radius: 6,
    labelText: "cc_user_subscription", labelMaxWidth: 140, labelPlacement: "center" }, over || {}) });

  const g = Pure.hoverExpandGeom(tbl(), 210, { maxWidth: 460 });
  ok(!!g, "T26 잘린 라벨 → 확장 기하 산출");
  ok(g.y === 50 && g.left === 25, "T26 확장 앵커 = 원 칩 **좌변**(x100 - w150/2 = 25), y 는 원 칩 그대로");
  // graph-label-hover-anchor(사용자 정정): 좌변 고정 + 우측 확장 — 카드 중심은 폭에 비례해 오른쪽으로 밀린다.
  ok(Pure.hoverCardCenterX(g, g.w0) === 100, "T26 t=0 중심 = 원 칩 중심(픽셀 동일 시작)");
  ok(Pure.hoverCardCenterX(g, g.w1) === 135, "T26 t=1 중심 = left + w1/2 (좌변 25 고정, 우측만 220 까지 성장)");
  ok(Pure.hoverCardCenterX(g, g.w1) - g.w1 / 2 === g.left, "T26 어떤 폭에서도 좌변 불변");
  ok(Pure.hoverCardCenterX(g, 185) === 117.5, "T26 중간 폭도 좌변 기준 선형");
  ok(Pure.hoverCardCenterX({ x: 100, w0: 150 }, 220) === 100, "T26 left 부재(구 geom) → 중앙 고정 폴백");
  ok(Pure.hoverCardCenterX(null, 220) === 0, "T26 geom null 안전");
  // 앞글자 절대 고정: 카드가 넓어져도 라벨의 world 좌측(textLeft)은 불변 → 카드-로컬 오프셋으로 상쇄.
  const tl = 100 - 138 / 2;   // 원 렌더 폭 138px 인 잘린 라벨의 좌측(중앙 정렬 역산)
  ok(Pure.hoverCardCenterX(g, g.w0) + Pure.hoverTextOffsetX(g, g.w0, tl) === tl, "T26 t=0 라벨 좌측 = 원 렌더 좌측");
  ok(Pure.hoverCardCenterX(g, g.w1) + Pure.hoverTextOffsetX(g, g.w1, tl) === tl, "T26 t=1 라벨 좌측 동일(앞글자 이동 0)");
  // 루틴 칩(labelMaxWidth 176 > 칩 폭 150): pad 기준이면 17px 튄다 — 실렌더 폭 역산이라 튐 0.
  const gr2 = Pure.hoverExpandGeom(tbl({ size: [150, 24], labelMaxWidth: 176 }), 210, {});
  const tlr = 100 - 176 / 2;
  ok(Pure.hoverCardCenterX(gr2, gr2.w0) + Pure.hoverTextOffsetX(gr2, gr2.w0, tlr) === tlr,
    "T26 라벨이 칩보다 넓은 스타일도 t=0 라벨 좌측 불변(pad 추정 미사용)");
  ok(gr2.left + gr2.pad / 2 !== tlr, "T26 (대조) pad 기준 좌측은 실렌더 좌측과 다르다 — 그래서 역산이 필요");
  ok(g.w0 === 150 && g.h === 24 && g.radius === 6, "T26 시작 폭/높이/라운드 = 원 칩(t=0 픽셀 동일 → 팝 없음)");
  ok(g.pad === 10 && g.w1 === 220, "T26 목표 폭 = 전체 라벨 + 원 칩 좌우 여백(210+10)");
  ok(g.capped === false, "T26 상한 미도달");
  ok(g.inner0 === 140 && g.inner1 === 210, "T26 텍스트 가용폭 보간 구간 = [원 한계 140 → 전체 라벨 210]");

  // codex review 3차 P2: 루틴 칩처럼 labelMaxWidth(176) > 칩 폭(150) 인 스타일에서도 t=0 가용폭이 원 한계
  //   그대로여야 한다 — 박스폭-pad(142)로 잡으면 hover 순간 원래 보이던 글자가 줄어드는 역-팝이 난다.
  const gr = Pure.hoverExpandGeom(tbl({ size: [150, 24], labelMaxWidth: 176 }), 210, {});
  ok(gr.inner0 === 176, "T26 labelMaxWidth > 칩 폭(루틴 칩) → t=0 가용폭 = 원 한계(역-팝 없음)");
  ok(gr.inner1 === 210 && gr.w1 === 218, "T26 그 경우도 종단 가용폭 = 전체 라벨");

  // 상한: 초장문 이름이 화면을 덮지 않게 cap 클램프.
  const gc = Pure.hoverExpandGeom(tbl(), 1000, { maxWidth: 460 });
  ok(gc.w1 === 460 && gc.capped === true, "T26 초장문 라벨 → maxWidth 상한 클램프 + capped 플래그");

  // 확장 불필요 케이스 — 전부 null(카드 미생성 = 시각 노이즈 0).
  ok(Pure.hoverExpandGeom(tbl(), 140, {}) === null, "T26 라벨이 이미 다 보임 → null");
  ok(Pure.hoverExpandGeom(tbl(), 141, {}) === null, "T26 이득 < minGain(1px) → null");
  ok(Pure.hoverExpandGeom(tbl({ labelText: "" }), 210, {}) === null, "T26 라벨 없음 → null");
  ok(Pure.hoverExpandGeom(tbl({ labelMaxWidth: 0 }), 210, {}) === null, "T26 labelMaxWidth 미설정(잘림 없음) → null");
  ok(Pure.hoverExpandGeom(tbl({ labelPlacement: "right" }), 210, {}) === null, "T26 노드 밖 우측 라벨(컬럼) → 대상 아님");
  ok(Pure.hoverExpandGeom(tbl({ size: 11 }), 210, {}) === null, "T26 circle 노드 → 대상 아님");
  ok(Pure.hoverExpandGeom(Object.assign(tbl(), { __combo: true }), 210, {}) === null, "T26 combo(스키마 배경) → 대상 아님");
  ok(Pure.hoverExpandGeom(tbl(), 0, {}) === null, "T26 폭 측정 실패(0) → null(안전 폴백)");

  // pad 하한: labelMaxWidth 가 칩 폭에 근접해도 최소 8px 여백 확보.
  const gp = Pure.hoverExpandGeom(tbl({ size: [150, 24], labelMaxWidth: 148 }), 210, {});
  ok(gp.pad === 8 && gp.w1 === 218, "T26 pad 하한 8px");
}
{
  // _fitText: 폭이 커질수록 글자가 순차로 드러난다(잘린 상태에서 연속 시작 — 중간 슬라이스 팝 없음).
  const mk = () => ({ _t: "", get text() { return this._t; }, set text(v) { this._t = v; }, get width() { return this._t.length * 10; } });
  const F = Adapter.prototype._fitText;
  let t = mk(); F.call({}, t, "abcdefgh", 45);
  ok(t.text === "abc…", "T26 _fitText 좁은 폭 → 선두 3자 + ellipsis");
  t = mk(); F.call({}, t, "abcdefgh", 65);
  ok(t.text === "abcde…", "T26 _fitText 폭 증가 → 드러나는 글자 증가(단조)");
  t = mk(); F.call({}, t, "abcdefgh", 200);
  ok(t.text === "abcdefgh", "T26 _fitText 충분한 폭 → 전체 라벨(ellipsis 없음)");
  t = mk(); t.text = "zz…"; F.call({}, t, "abcdefgh", 200);
  ok(t.text === "abcdefgh", "T26 _fitText 는 직전 잘린 텍스트가 아닌 **전체 문자열** 기준 재계산");
}
{
  // _setLabelHover: 같은 대상 재-hover 는 재구성 없음(스윕 중 rebuild 폭주 차단) · 이탈은 카드 제거.
  //   sandbox 에 setTimeout 이 없어 hover-intent 분기는 즉시 fire 경로를 탄다(구현의 폴백).
  let shown = 0, cleared = 0, rendered = 0;
  const ctx = { _hoverId: null, _hoverTimer: 0, _hoverRaf: 0,
    _clearLabelHoverVisual() { cleared++; return this.__had === true; },
    _labelExpandGeom(n) { return (n && n.style.labelText === "long") ? { w0: 10, w1: 40 } : null; },
    _showLabelExpand() { shown++; this.__had = true; },
    _render() { rendered++; } };
  const S = Adapter.prototype._setLabelHover;
  const node = { id: "T1", style: { labelText: "long" } };
  S.call(ctx, node);
  ok(shown === 1 && ctx._hoverId === "T1", "T26 hover 진입 → 확장 카드 1회 생성");
  S.call(ctx, node);
  ok(shown === 1 && cleared === 1, "T26 같은 노드 재-hover → dedupe(재구성 0)");
  const plain = { id: "T2", style: { labelText: "short" } };
  S.call(ctx, plain);
  ok(shown === 1 && ctx._hoverId === "T2" && rendered === 1, "T26 잘리지 않은 노드 → 카드 없음 + 이전 카드만 정리 렌더");
  ctx.__had = false; rendered = 0;
  S.call(ctx, null);
  ok(ctx._hoverId === null && rendered === 0, "T26 빈 배경 이탈(직전 카드 없음) → 불필요 렌더 0(render-on-demand 보존)");
}
{
  // _probeHover: tier1(hit-grid)만 — _pick 의 tier2 hitTestCombo(O(combos×nodes))를 매 pointermove 에 돌리지 않는다.
  const nodes = [
    { id: "N1", type: "rect", style: { x: 0, y: 0, size: [100, 24], zIndex: 4 } },
    { id: "CB", type: "rect", data: { kind: "cat-bg" }, style: { x: 0, y: 0, size: [800, 600], zIndex: -1 } },
  ];
  let got = "unset";
  const ctx = { _built: { nodes, edges: [], combos: [{ id: "C1", style: {} }] },
    _hitGrid: Pure.buildHitGrid(nodes, 128), _cam: { zoom: 1, x: 0, y: 0 },
    _inMinimap() { return false; }, _isCatBg: Adapter.prototype._isCatBg,
    _tweenPos: null, _tweenMovers: null, _hitNodes: Adapter.prototype._hitNodes,
    _setLabelHover(n) { got = n; } };
  const origCombo = Pure.hitTestCombo; let comboCalls = 0;
  Pure.hitTestCombo = function () { comboCalls++; return origCombo.apply(this, arguments); };
  Adapter.prototype._probeHover.call(ctx, 0, 0);
  ok(got && got.id === "N1", "T26 hover 프로브 노드 적중");
  Adapter.prototype._probeHover.call(ctx, 200, 200);
  ok(got === null, "T26 cat-bg(밴드 배경)는 hover 확장 대상에서 제외");
  ok(comboCalls === 0, "T26 hover 프로브는 hitTestCombo 미호출(매 pointermove O(combos×nodes) 회피)");
  Pure.hitTestCombo = origCombo;
  ctx._inMinimap = () => true;
  Adapter.prototype._probeHover.call(ctx, 0, 0);
  ok(got === null, "T26 미니맵 위 커서 → hover 해제");
}

{
  // 카드 수명주기: 확장 카드는 1장 · 축소 진행 카드도 1장 · rAF 부재(node vm/헤드리스)면 종단 상태 즉시 적용.
  const mkCard = () => { const c = { alpha: 1, parent: {}, destroyed: false,
      destroy() { this.destroyed = true; }, };
    c.parent.removeChild = () => { c.parent = null; };
    const card = { c, g: { w0: 150 }, w: 220, raf: 0, paints: [] };
    card.paint = (w) => { card.w = w; card.paints.push(w); };
    return card; };

  const C = Adapter.prototype._clearLabelHoverVisual;
  const ctxBase = () => ({ _outCard: null, _hoverCard: null, _render() {},
    _destroyCard: Adapter.prototype._destroyCard, _tweenCard: Adapter.prototype._tweenCard });

  let ctx = ctxBase();
  ok(C.call(ctx, true) === false, "T26 지울 카드 없음 → false(호출부 렌더 억제)");

  ctx = ctxBase(); const c1 = mkCard(); ctx._hoverCard = c1;
  ok(C.call(ctx, false) === true && c1.c.destroyed === true && ctx._hoverCard === null,
    "T26 animate=false(rebuild/destroy) → 즉시 제거");

  // rAF 부재 환경: animate=true 라도 종단(원 칩 폭) 즉시 적용 후 제거 — 잔상 없음.
  ctx = ctxBase(); const c2 = mkCard(); ctx._hoverCard = c2;
  ok(C.call(ctx, true) === true && c2.c.destroyed === true && ctx._outCard === null,
    "T26 rAF 부재 → 축소 트윈 생략하고 즉시 종단 처리");

  // 축소 진행 중 새 이탈 → 이전 축소 카드 즉시 제거(동시 1장 불변식).
  ctx = ctxBase(); const cOld = mkCard(), cNew = mkCard();
  ctx._outCard = cOld; ctx._hoverCard = cNew;
  C.call(ctx, false);
  ok(cOld.c.destroyed === true && cNew.c.destroyed === true, "T26 축소 진행 카드 누적 없음(동시 1장)");

  // _tweenCard: rAF 부재면 목표 상태 1회 페인트 + onEnd 1회.
  const c3 = mkCard(); let ended = 0;
  Adapter.prototype._tweenCard.call({ _render() {} }, c3, 150, 220, 160, () => { ended++; });
  ok(c3.paints.length === 1 && c3.paints[0] === 220 && ended === 1,
    "T26 _tweenCard rAF 부재 → 종단 폭 즉시 + onEnd 1회");

  // _clearLabelHover: 예약 타이머·hover id 까지 초기화(다음 pointermove 가 재도출).
  const ctx2 = Object.assign(ctxBase(), { _hoverId: "T1", _hoverTimer: 0 });
  ctx2._clearLabelHoverVisual = C;
  Adapter.prototype._clearLabelHover.call(ctx2);
  ok(ctx2._hoverId === null, "T26 _clearLabelHover → hover id 초기화");
}
{
  // codex review P1 ①: 확장 카드 위 커서는 현 hover 유지 — 드러난 좌우 영역이 원 노드 bbox 밖이라
  //   그대로 두면 "이름 뒷부분을 보려고 다가가면 카드가 닫히는" 깜빡임이 난다.
  const g = { x: 100, y: 50, w0: 150, w1: 220, h: 24 };
  ok(Pure.hoverCardHit(205, 50, g, 220) === true, "T26 확장 폭(220) 안 = 카드 hit(원 bbox 밖 +105)");
  ok(Pure.hoverCardHit(205, 50, g, 150) === false, "T26 아직 확장 전(150) 이면 같은 점은 카드 밖");
  ok(Pure.hoverCardHit(100, 70, g, 220) === false, "T26 세로는 원 칩 높이 그대로(위/아래 유출 없음)");
  ok(Pure.hoverCardHit(100, 50, null, 220) === false, "T26 카드 없음 → false");
  ok(Pure.hoverCardHit(305, 50, g, 220, 300) === true, "T26 클램프로 밀린 카드는 그 실제 중심 기준으로 hit");

  // 뷰포트 클램프(codex review P2): 가장자리 칩의 카드가 캔버스 밖으로 잘리지 않게 가로 중심 보정.
  ok(Pure.clampCardCenterX(400, 220, 1000, 6) === 400, "T26 clamp 여유 있으면 그대로");
  ok(Pure.clampCardCenterX(20, 220, 1000, 6) === 116, "T26 clamp 좌측 침범 → pad+half 로 밀기");
  ok(Pure.clampCardCenterX(980, 220, 1000, 6) === 884, "T26 clamp 우측 침범 → vw-pad-half 로 밀기");
  ok(Pure.clampCardCenterX(500, 1200, 1000, 6) === 606, "T26 카드가 뷰포트보다 넓음 → 좌측 정렬(앞부분 판독 우선)");
  // 미니맵 회피(codex review P2): 우측 경계를 미니맵 좌변으로 좁혀 카드가 미니맵 밑에 깔리지 않게.
  ok(Pure.clampCardCenterX(800, 220, 1000, 6, 820) === 704, "T26 미니맵과 세로 겹침 → 그 왼쪽까지만 확장");
  ok(Pure.clampCardCenterX(300, 220, 1000, 6, 820) === 300, "T26 미니맵과 무관한 위치는 그대로");

  // _clampCardX: 미니맵과 세로로 겹칠 때만 우측 경계가 좁아진다(줌=1·팬=0 기준).
  //   좌변 고정 앵커(left) 위에 클램프가 얹힌다 — 기준 중심 = left + w/2.
  const mkCtx = (mmY) => ({ getSize() { return [1000, 600]; }, _cam: { zoom: 1, x: 0, y: 0 },
    _minimap: { c: { position: { x: 820, y: mmY } }, size: [168, 112] } });
  const gm = (y) => ({ x: 800, left: 725, w0: 150, y, h: 24 });   // 좌변 725 → w=220 이면 기준 중심 835
  ok(Adapter.prototype._clampCardX.call(mkCtx(478), gm(500), 220) === 704,
    "T26 _clampCardX 미니맵 y 밴드와 겹침 → 좌변 기준 중심(835)이 704 로 밀림");
  ok(Adapter.prototype._clampCardX.call(mkCtx(478), gm(100), 220) === 835,
    "T26 _clampCardX 미니맵 위쪽(겹침 없음) → 좌변 기준 중심 그대로(left+w/2)");
  ok(Adapter.prototype._clampCardX.call({ getSize() { return [0, 0]; } }, { x: 42, left: 0, w0: 84, y: 0, h: 24 }, 220) === 110,
    "T26 _clampCardX 뷰포트 미확정(0) → 클램프 없이 좌변 기준 중심(안전 폴백)");

  // _revalidateHover(codex review 5차 P2): 카메라 변화(wheel·focusElement·zoomTo·translateBy)마다 마지막
  //   커서 좌표로 재판정 — 눌림 중엔 무동작(팬 프레임 비용 0), 좌표 없으면 재페인트만.
  let probes = 0, repaints = 0;
  const RV = Adapter.prototype._revalidateHover;
  RV.call({ _hoverPt: { x: 5, y: 6 }, _ptrDown: false, _probeHover() { probes++; }, _repaintHoverCard() { repaints++; } });
  ok(probes === 1 && repaints === 1, "T26 카메라 변화 + 커서 좌표 있음 → 재판정 + 재페인트");
  RV.call({ _hoverPt: { x: 5, y: 6 }, _ptrDown: true, _probeHover() { probes++; }, _repaintHoverCard() { repaints++; } });
  ok(probes === 1 && repaints === 2, "T26 눌림 중(팬/드래그) → 재판정 생략(프레임 비용 0)");
  RV.call({ _hoverPt: null, _ptrDown: false, _probeHover() { probes++; }, _repaintHoverCard() { repaints++; } });
  ok(probes === 1 && repaints === 3, "T26 커서 좌표 없음(캔버스 진입 전) → 재페인트만");

  const nodes = [
    { id: "N1", type: "rect", style: { x: 100, y: 50, size: [150, 24], zIndex: 4 } },
    { id: "N2", type: "rect", style: { x: 300, y: 50, size: [150, 24], zIndex: 4 } },
  ];
  let calls = 0, got = "unset";
  const ctx = { _built: { nodes, edges: [], combos: [] }, _hitGrid: Pure.buildHitGrid(nodes, 128),
    _cam: { zoom: 1, x: 0, y: 0 }, _inMinimap() { return false; }, _isCatBg: Adapter.prototype._isCatBg,
    _tweenPos: null, _tweenMovers: null, _hitNodes: Adapter.prototype._hitNodes,
    _hoverCard: { g, w: 220 }, _setLabelHover(n) { calls++; got = n; } };
  Adapter.prototype._probeHover.call(ctx, 205, 50);
  ok(calls === 0, "T26 확장 카드 위 커서 → _setLabelHover 미호출(현 hover 유지)");
  Adapter.prototype._probeHover.call(ctx, 300, 50);
  ok(calls === 1 && got && got.id === "N2", "T26 카드 밖 다른 노드 → 정상 전환");

  // codex review 4차 P2: 확장 카드 위 클릭/우클릭/드래그는 **원 노드**로 라우팅(_pick tier0) —
  //   드러난 영역이 캔버스·이웃으로 새어 선택이 풀리거나 엉뚱한 메뉴가 뜨는 것 차단.
  const pctx = { _built: { nodes, edges: [], combos: [] }, _hitGrid: Pure.buildHitGrid(nodes, 128),
    _isCatBg: Adapter.prototype._isCatBg, _hoverCard: { g, w: 220, node: nodes[0] },
    _tweenPos: null, _tweenMovers: null, _hitNodes: Adapter.prototype._hitNodes };
  const hitCard = Adapter.prototype._pick.call(pctx, 205, 50);
  ok(hitCard && hitCard.id === "N1", "T26 _pick tier0 — 확장 카드 위(원 bbox 밖)는 원 노드로 라우팅");
  pctx._hoverCard = null;
  ok(Adapter.prototype._pick.call(pctx, 205, 50) === null, "T26 카드 없으면 같은 점은 종전대로 미적중(회귀 0)");
}
{
  // codex review P1 ②: pointerleave 시 대기 중인 프로브 rAF 까지 무효화(떠난 뒤 카드 부활 차단).
  // cancelAnimationFrame 은 vm sandbox 전역에 주입해야 어댑터 코드의 스코프에서 해석된다(host global 아님).
  let canceled = 0, cleared = 0;
  sandbox.cancelAnimationFrame = () => { canceled++; };
  const ctx = { _hoverProbeRaf: 7, _hoverPt: { x: 1, y: 2 }, _setLabelHover() { cleared++; } };
  Adapter.prototype._cancelHoverProbe.call(ctx, true);
  ok(canceled === 1 && ctx._hoverProbeRaf === 0 && ctx._hoverPt === null && cleared === 1,
    "T26 pointerleave → 대기 프로브 취소 + 좌표 무효화 + hover 해제");
  const ctx2 = { _hoverProbeRaf: 0, _hoverPt: { x: 1, y: 2 }, _setLabelHover() { cleared++; } };
  Adapter.prototype._cancelHoverProbe.call(ctx2, false);
  ok(cleared === 1 && ctx2._hoverPt === null, "T26 clear=false(destroy 경로) → hover 해제 없이 프로브만 정리");
  delete sandbox.cancelAnimationFrame;   // 이후 테스트의 rAF-부재 폴백 경로 보존
}
{
  // codex review P1 ③: 축소 진행 카드만 남은 상태에서의 정리도 "정리함"으로 집계 — 아니면 호출부가
  //   렌더를 생략해 render-on-demand 프레임버퍼에 유령 카드가 남는다.
  const stub = { destroyed: false, c: { parent: null, destroy() {} }, raf: 0 };
  const ctx = { _outCard: stub, _hoverCard: null,
    _destroyCard() { stub.destroyed = true; }, _tweenCard() {}, _render() {} };
  const r = Adapter.prototype._clearLabelHoverVisual.call(ctx, true);
  ok(r === true && stub.destroyed === true && ctx._outCard === null,
    "T26 축소 카드만 정리해도 true 반환(유령 카드 방지 렌더 유발)");
}
{
  // codex review 2차 P2 ①: 버튼 눌림(클릭/팬/드래그) 중엔 hover 판정 정지 — pointerdown 직전 예약된
  //   rAF 프로브가 뒤늦게 실행돼 드래그 중 옛 좌표로 유령 카드를 띄우는 경로 차단.
  let calls = 0;
  const ctx = { _ptrDown: true, _inMinimap() { return false; }, _setLabelHover() { calls++; } };
  Adapter.prototype._probeHover.call(ctx, 10, 10);
  ok(calls === 0, "T26 pointer 눌림 중 → hover 프로브 무동작(드래그 유령 카드 차단)");
  // 눌림 해제(pointerup/pointercancel) 후에는 정상 복귀 — 플래그가 고착되면 hover 가 영구 정지한다.
  ctx._ptrDown = false; ctx._hitGrid = null; ctx._cam = { zoom: 1, x: 0, y: 0 }; ctx._built = { nodes: [], edges: [], combos: [] };
  ctx._tweenPos = null; ctx._tweenMovers = null; ctx._hitNodes = Adapter.prototype._hitNodes; ctx._isCatBg = Adapter.prototype._isCatBg;
  Adapter.prototype._probeHover.call(ctx, 10, 10);
  ok(calls === 1, "T26 눌림 해제 후 hover 판정 복귀(플래그 고착 없음)");
}
{
  // codex review 2차 P2 ②: running desaturate(fillOpacity 0.45)를 카드도 공유 — hover 시 채도가 되살아나
  //   앰버 역할색 위에서 주황 점선 테두리가 위장되던 원 문제(§18.8 M1) 재발 방지.
  const A = Adapter.prototype._nodeFillAlpha, cfg = { _nodeState: {} };
  ok(A.call(cfg, { states: ["running"], style: {} }) === 0.45, "T26 running → 0.45 desaturate(기본값)");
  ok(A.call({ _nodeState: { running: { fillOpacity: 0.3 } } }, { states: ["running"], style: {} }) === 0.3,
    "T26 running → state config 의 fillOpacity 우선");
  ok(A.call(cfg, { states: ["selected"], style: {} }) === 1, "T26 비-running + style 미지정 → 1");
  ok(A.call(cfg, { states: [], style: { fillOpacity: 0.75 } }) === 0.75, "T26 비-running → style.fillOpacity 존중");
  ok(A.call(cfg, {}) === 1, "T26 states/style 부재 → 1(안전 기본)");
}
{
  // 비브라우저/미배선(P 부재)에서 확장 기하 산출 시도 → null(import 부작용 0 계약 보존).
  const g = Adapter.prototype._labelExpandGeom.call({ P: null }, { style: { labelText: "x", labelMaxWidth: 10 } });
  ok(g === null, "T26 Pixi 미배선 → 확장 기하 null");
}

// ── T27 haloGeom: 상태 테두리 기하 (graph-analyzed-halo-fit) ──
{
  // ① rect 노드는 회귀 0 — 종전 하드코딩(gap 3 / inset 2*i / radius+2+inset / lw 그대로)과 동일해야 한다.
  const chip = { style: { size: [150, 24], radius: 6 } };
  const g0 = Pure.haloGeom(chip, 0, 3);
  ok(g0.shape === "rect" && g0.x === -78 && g0.y === -15 && g0.w === 156 && g0.h === 30 && g0.radius === 8 && g0.lw === 3,
    "T27 rect halo 종전 수치 유지(i=0)");
  const g1 = Pure.haloGeom(chip, 1, 3);
  ok(g1.x === -80 && g1.y === -17 && g1.w === 160 && g1.h === 34 && g1.radius === 10 && g1.lw === 3,
    "T27 rect 동심링 inset 2px(i=1) 유지");
  // ② circle 노드(컬럼 지름 11)는 **원형** halo — 종전 rect 경로는 h 기본값 24 를 먹어 17×30 알약이었다.
  const col = { type: "circle", style: { size: 11 } };
  const c0 = Pure.haloGeom(col, 0, 3);
  ok(c0.shape === "circle", "T27 circle 노드 → 원형 halo");
  ok(approx(c0.lw, 3 * (11 / 24), 1e-9) && c0.lw < 3, "T27 두께가 노드 크기에 비례(3 → ~1.4)");
  ok(approx(c0.r, 5.5 + 1.5, 1e-9), "T27 반지름 = 노드 반지름 + 여백");
  // 외곽 지름이 노드 지름의 1.5배 이내 — 종전 30px(2.7배) 세로 알약 대비 축소가 계약.
  ok(2 * (c0.r + c0.lw / 2) < 11 * 1.5, "T27 halo 외곽 < 노드 지름 1.5배");
  const c1 = Pure.haloGeom(col, 1, 3);
  ok(c1.r > c0.r && (c1.r - c0.r) < 2, "T27 circle 동심링도 비례 간격(<2px)");
  // ③ size 미지정 circle → 기본 지름 11 폴백(_drawNode 와 동일 계약).
  ok(approx(Pure.haloGeom({ type: "circle", style: {} }, 0, 3).r, c0.r, 1e-9), "T27 circle size 미지정 → 11 폴백");
  // ④ type 미지정(hover 확장 카드는 {states,style} 만 넘긴다) → rect 경로 유지.
  ok(Pure.haloGeom({ style: { size: [120, 24] } }, 0, 3).shape === "rect", "T27 type 미지정 → rect 경로");
  // ⑤ 두께 하한 1px — 비례 축소가 hairline 아래로 사라지지 않게.
  ok(Pure.haloGeom({ type: "circle", style: { size: 6 } }, 0, 2).lw === 1, "T27 두께 하한 1px");
}

// ── T27 dashArcs: 원형 대시(running/busy 점선의 circle 등가) ──
{
  const r = 8, arcs = Pure.dashArcs(r, [4, 3]);
  ok(arcs.length > 0, "T27 dashArcs 세그먼트 생성");
  const onLen = arcs.reduce((a, [a0, a1]) => a + (a1 - a0) * r, 0);
  const circ = 2 * Math.PI * r;
  ok(Math.abs(onLen - circ * 4 / 7) < 4, "T27 on 호길이 ≈ 둘레*on/(on+off)");
  let mono = true, within = true;
  for (let i = 0; i < arcs.length; i++) {
    if (arcs[i][1] <= arcs[i][0]) mono = false;
    if (i && arcs[i][0] < arcs[i - 1][1]) mono = false;
    if ((arcs[i][1] - arcs[i][0]) * r > 4 + 1e-9) within = false;
  }
  ok(mono, "T27 dashArcs 각도 단조증가·비퇴화");
  ok(within, "T27 각 대시 호길이 ≤ on 길이(직선 대시와 동일 스케일)");
  ok(arcs[arcs.length - 1][1] <= 2 * Math.PI + 1e-9, "T27 한 바퀴를 넘지 않음");
}

// ── T28 moveTweenPlan: 재배치 이동 트윈 대상 선별(graph-move-anim, 2026-08-13) ──
//   잠그는 계약: ① 이동한 노드만 ② 신규/소멸 노드 제외 ③ 화면 밖 이동 제외(비용 0) ④ 상한 초과는
//   **보고되는** 절단(무음 금지) ⑤ 씬 교체(겹침 부족)는 통째로 포기 ⑥ 미세 이동은 무시.
{
  const mk = (id, x, y) => ({ id, style: { x, y } });
  const prev = new Map([["a", [0, 0]], ["b", [10, 10]], ["c", [20, 20]]]);

  // ① 이동한 노드만 — b 는 제자리
  {
    const p = Pure.moveTweenPlan(prev, [mk("a", 100, 0), mk("b", 10, 10), mk("c", 20, 60)], {});
    ok(p.items.length === 2, "T28 이동 노드만 선별");
    ok(p.items.map(i => i.id).sort().join(",") === "a,c", "T28 제자리 노드 제외");
    ok(p.moved === 2 && p.skipped === 0, "T28 moved/skipped 회계");
    const a = p.items.find(i => i.id === "a");
    ok(a.from[0] === 0 && a.from[1] === 0 && a.to[0] === 100 && a.to[1] === 0, "T28 from/to 좌표");
  }
  // ② 신규 노드(직전 씬에 없음)는 대상 아님 — 트윈할 출발점이 없다
  {
    const p = Pure.moveTweenPlan(prev, [mk("a", 100, 0), mk("b", 10, 10), mk("c", 20, 20), mk("d", 500, 500)], {});
    ok(!p.items.some(i => i.id === "d"), "T28 신규 노드 제외");
  }
  // ③ 미세 이동(minDelta 이하)은 무시 — 부동소수 흔들림으로 트윈이 켜지지 않게
  {
    const p = Pure.moveTweenPlan(prev, [mk("a", 0.3, 0.3), mk("b", 10, 10), mk("c", 20, 20)], {});
    ok(p.items.length === 0 && p.moved === 0 && p.reason === "no-move", "T28 미세 이동 무시");
  }
  // ④ 가시영역 밖 이동 제외 — 출발·도착 **어느 쪽도** 안 걸칠 때만 제외한다
  //    (화면 안에서 밖으로 떠나는 이동은 사용자가 그 이탈을 보므로 대상이다).
  {
    const vis = { x0: -50, y0: -50, x1: 50, y1: 50 };
    const far = new Map([["a", [0, 0]], ["b", [10, 10]], ["c", [900, 900]]]);
    const p = Pure.moveTweenPlan(far, [mk("a", 40, 40), mk("b", 10, 10), mk("c", 1200, 1200)], { vis });
    ok(p.items.length === 1 && p.items[0].id === "a", "T28 화면 밖 이동 제외");
    ok(p.moved === 2 && p.skipped === 1, "T28 제외분이 skipped 로 보고됨(무음 절단 금지)");
    // 도착만 화면 안이어도 대상(밖에서 들어오는 이동은 보인다)
    const p2 = Pure.moveTweenPlan(new Map([["a", [900, 900]]]), [mk("a", 0, 0)], { vis });
    ok(p2.items.length === 1, "T28 화면 밖 → 안 이동은 대상");
    // 화면 안에서 밖으로 떠나는 이동도 대상(이탈이 보인다)
    const p3 = Pure.moveTweenPlan(new Map([["a", [0, 0]]]), [mk("a", 900, 900)], { vis });
    ok(p3.items.length === 1, "T28 화면 안 → 밖 이동도 대상");
  }
  // ⑤ 상한 — 초과분은 즉시 반영 + skipped 로 보고
  {
    const big = new Map(), nodes = [];
    for (let i = 0; i < 10; i++) { big.set("n" + i, [0, 0]); nodes.push(mk("n" + i, 100 + i, 100)); }
    const p = Pure.moveTweenPlan(big, nodes, { cap: 4 });
    ok(p.items.length === 4, "T28 cap 적용");
    ok(p.moved === 10 && p.skipped === 6, "T28 cap 초과분 skipped 보고");
  }
  // ⑥-a 부분집합 씬 교체 — 새 씬이 **이전 씬의 부분집합**이면 새 씬 기준 겹침은 100% 다.
  //     분모를 양쪽의 큰 쪽으로 잡지 않으면 검색 prune(500→1)이 '재배치'로 오판된다.
  {
    const many = new Map();
    for (let i = 0; i < 100; i++) many.set("n" + i, [i, 0]);
    const p = Pure.moveTweenPlan(many, [mk("n0", 500, 500)], {});
    ok(p.items.length === 0 && p.reason === "scene-switch", "T28 부분집합 prune 은 씬 교체(분모=큰 쪽)");
    // 정상 펼침(기존 전량 유지 + 신규 추가)은 계속 트윈 대상
    const grow = [];
    for (let i = 0; i < 100; i++) grow.push(mk("n" + i, i, 40));
    for (let i = 0; i < 20; i++) grow.push(mk("new" + i, i, 80));
    const p2 = Pure.moveTweenPlan(many, grow, {});
    ok(p2.items.length === 100, "T28 펼침(전량 유지 + 신규)은 트윈 유지", p2.items.length);
  }
  // ⑥ 씬 교체 감지 — 직전과 겹치는 비율이 하한 미만이면 트윈 포기(스코프 전환·검색·중심보기)
  {
    const nodes = [mk("a", 100, 100)];
    for (let i = 0; i < 20; i++) nodes.push(mk("x" + i, i * 10, 0));
    const p = Pure.moveTweenPlan(prev, nodes, {});
    ok(p.items.length === 0 && p.reason === "scene-switch", "T28 씬 교체는 트윈 포기");
    // minOverlap 을 낮추면 같은 입력이 트윈 대상이 된다(임계가 실제로 판정에 쓰임)
    const p2 = Pure.moveTweenPlan(prev, nodes, { minOverlap: 0.01 });
    ok(p2.items.length === 1 && p2.items[0].id === "a", "T28 minOverlap 임계가 판정을 가른다");
  }
  // ⑦ 빈 입력 안전 — 직전 스냅샷 없음/노드 없음은 조용히 no-op
  {
    ok(Pure.moveTweenPlan(null, [mk("a", 1, 1)], {}).items.length === 0, "T28 prev 없음 → no-op");
    ok(Pure.moveTweenPlan(new Map(), [mk("a", 1, 1)], {}).reason === "no-prev", "T28 빈 prev → no-prev");
    ok(Pure.moveTweenPlan(prev, [], {}).items.length === 0, "T28 노드 없음 → no-op");
  }
  // ⑧ 비유한 좌표 방어(build 결함·미해소 좌표가 트윈을 NaN 으로 오염시키지 않게)
  {
    const p = Pure.moveTweenPlan(new Map([["a", [0, 0]], ["b", [0, 0]]]),
      [mk("a", NaN, 10), mk("b", 50, 50)], { minOverlap: 0 });
    ok(p.items.length === 1 && p.items[0].id === "b", "T28 비유한 좌표 노드 제외");
  }
}

// ── T29 이동 트윈 수명주기 (graph-move-anim) ──
//   Pixi 없이 어댑터 프로토타입만 빌려 계약을 잠근다: ① setData 가 **직전 좌표를 캡처**한다
//   ② 트윈 개시 시 오브젝트가 **출발 위치로 되감긴다**(그렇지 않으면 애니메이션이 존재하지 않는다)
//   ③ 시간이 흐르면 최종 위치로 수렴하고 ④ 종단에 오버레이(`_tweenPos`)·저품질 플래그가 **되돌아간다**
//   ⑤ 진행 중 정지(다음 draw)는 최종 위치로 즉시 안착 ⑥ 관계선 예산 초과는 트윈을 열지 않는다.
{
  // rAF 를 수동 큐로 — 프레임 진행을 테스트가 통제한다(시간 의존 flake 제거).
  const frames = [];
  sandbox.requestAnimationFrame = (f) => { frames.push(f); return frames.length; };
  sandbox.cancelAnimationFrame = () => {};
  let clock = 0;
  sandbox.performance.now = () => clock;
  const drain = (t) => { clock = t; const q = frames.splice(0); for (const f of q) f(); };

  const mkObj = () => ({ position: { x: 0, y: 0, set(x, y) { this.x = x; this.y = y; } } });
  const mkInst = (edgesLen) => {
    const inst = Object.create(Adapter.prototype);
    inst.world = { scale: { x: 1 }, position: { x: 0, y: 0 } };
    inst._objs = new Map();
    inst._built = { nodes: [], edges: [], combos: [] };
    inst._edgeIndex = null; inst._lowFi = false;
    inst._prevPos = null; inst._tweenPos = null; inst._moveTween = null;
    inst.getSize = () => [1000, 600];
    inst._renderMinimap = () => {};
    inst._render = () => {};
    inst._refreshIncidentEdges = () => { inst.__refreshes = (inst.__refreshes || 0) + 1; };
    inst._incidentEdges = () => new Array(edgesLen || 0).fill(0);
    return inst;
  };
  const seed = (inst, from, to) => {
    inst._built = { nodes: [{ id: "a", style: { x: from[0], y: from[1] } }], edges: [], combos: [] };
    inst.setData({ nodes: [{ id: "a", style: { x: to[0], y: to[1] } }], edges: [], combos: [] });
    const o = mkObj(); o.position.set(to[0], to[1]);   // draw() 가 최종 위치로 만든 상태
    inst._objs.set("a", o);
    return o;
  };

  // ①②③④ 정상 수명주기
  {
    const inst = mkInst(0);
    const o = seed(inst, [0, 0], [200, 100]);
    ok(inst._prevPos && inst._prevPos.get("a")[0] === 0, "T29 setData 가 직전 좌표 캡처");
    clock = 0;
    inst._startMoveTween(inst._built);
    ok(o.position.x === 0 && o.position.y === 0, "T29 개시 시 출발 위치로 되감김");
    ok(!!inst._tweenPos && !!inst._moveTween, "T29 오버레이·세대 토큰 생성");
    ok(inst._lowFi === true, "T29 트윈 중 관계선 저품질");
    drain(180);   // 중간 프레임 — 출발과 도착 사이
    ok(o.position.x > 0 && o.position.x < 200, "T29 중간 프레임은 경로 위", o.position.x);
    ok(inst._tweenPos.get("a")[0] === o.position.x, "T29 오버레이가 화면 좌표를 따라감");
    drain(1000);  // 종단
    ok(o.position.x === 200 && o.position.y === 100, "T29 최종 위치 수렴", o.position);
    ok(inst._tweenPos === null && inst._moveTween === null, "T29 종단에 오버레이·토큰 해제");
    ok(inst._lowFi === false, "T29 종단에 관계선 고품질 복원");
  }
  // ⑤ 진행 중 정지(다음 draw) → 최종 위치 즉시 안착 + 상태 정리
  {
    const inst = mkInst(0);
    const o = seed(inst, [0, 0], [200, 100]);
    clock = 0;
    inst._startMoveTween(inst._built);
    drain(120);
    inst._stopMoveTween();
    ok(o.position.x === 200 && o.position.y === 100, "T29 정지 시 최종 위치 즉시 안착", o.position);
    ok(inst._tweenPos === null && inst._moveTween === null && inst._lowFi === false, "T29 정지 시 상태 정리");
    const before = o.position.x;
    drain(1000);   // 취소된 프레임이 살아 돌아오지 않는다
    ok(o.position.x === before, "T29 정지 후 stale 프레임 무동작");
  }
  // ⑥ 관계선 예산 초과 → 트윈을 열지 않고 최종 위치(끊기는 애니메이션 방지)
  {
    const inst = mkInst(100000);
    const o = seed(inst, [0, 0], [200, 100]);
    inst._startMoveTween(inst._built);
    ok(inst._moveTween === null && o.position.x === 200, "T29 관계선 예산 초과 시 즉시 최종 위치");
  }
  // ⑦ 직전 스냅샷이 없으면(첫 draw) 조용히 no-op
  {
    const inst = mkInst(0);
    inst._objs.set("a", mkObj());
    inst.setData({ nodes: [{ id: "a", style: { x: 5, y: 5 } }], edges: [], combos: [] });
    inst._startMoveTween(inst._built);
    ok(inst._moveTween === null, "T29 첫 draw 는 트윈 없음");
  }
  // ⑧ 트윈 도중 오브젝트 교체(setElementState = busy 해제·선택 점등·분석 마커)에도 계속 움직인다.
  //    캡처한 참조만 붙들면 그 순간부터 노드는 멈추고 관계선만 보간돼 선이 떨어진다(codex review P1).
  {
    const inst = mkInst(0);
    const oldObj = seed(inst, [0, 0], [400, 0]);
    clock = 0;
    inst._startMoveTween(inst._built);
    drain(100);
    const midX = oldObj.position.x;
    const fresh = mkObj(); fresh.position.set(400, 0);   // _drawNode 는 최종 위치로 만든다
    inst._objs.set("a", fresh);                          // setElementState 가 교체한 상황
    drain(200);
    ok(fresh.position.x > midX && fresh.position.x < 400, "T29 교체된 오브젝트가 이어서 움직임", fresh.position.x);
    ok(oldObj.position.x === midX, "T29 파기된 옛 오브젝트는 더 이상 갱신 안 됨");
    drain(1000);
    ok(fresh.position.x === 400, "T29 교체 후에도 최종 위치 수렴");
  }
  // ⑨ 오버레이는 **첫 프레임 콜백 전에** 활성이고, 그 사이 포인터 이벤트도 보이는 좌표로 판정된다.
  //    (hit-grid 는 건드리지 않는다 — 이동 노드는 grid 에서 제외되고 `_hitNodes` 선형 스캔이 맡는다.)
  {
    const inst = mkInst(0);
    inst._built = { nodes: [{ id: "a", type: "rect", style: { x: 0, y: 0, size: [100, 24], zIndex: 4 } }], edges: [], combos: [] };
    inst.setData({ nodes: [{ id: "a", type: "rect", style: { x: 900, y: 0, size: [100, 24], zIndex: 4 } }], edges: [], combos: [] });
    inst._objs.set("a", mkObj());
    const gridBefore = Pure.buildHitGrid(inst._built.nodes, 128);   // draw() 가 만든 목적지 기준 grid
    inst._hitGrid = gridBefore;
    inst._isCatBg = Adapter.prototype._isCatBg;
    inst._hoverCard = null;
    clock = 0;   // 트윈 시작 시각 기준(앞 블록의 시계를 물려받지 않게)
    inst._startMoveTween(inst._built);
    ok(!!inst._tweenMovers && inst._tweenMovers.length === 1, "T29 트윈 개시 직후 movers 활성");
    ok(inst._hitGrid === gridBefore, "T29 hit-grid 는 재구성하지 않는다(프레임당 O(N) 제거)");
    ok(Adapter.prototype._pick.call(inst, 0, 0) !== null, "T29 첫 프레임 전에도 보이는 좌표가 hit");
    ok(Adapter.prototype._pick.call(inst, 900, 0) === null, "T29 첫 프레임 전 목적지는 hit 아님");
    drain(1000);
    ok(inst._tweenMovers === null, "T29 종단에 movers 해제");
    ok(Adapter.prototype._pick.call(inst, 900, 0) !== null, "T29 안착 후 최종 좌표에서 hit(복귀)");
  }
  // ⑩ 드래그가 트윈을 이긴다 — 조작 중 프레임이 손끝 위치를 덮어쓰지 않는다(codex review 3차 P1)
  {
    const inst = mkInst(0);
    const o = seed(inst, [0, 0], [400, 0]);
    inst._scheduleEdgeRefresh = () => {};
    clock = 0;
    inst._startMoveTween(inst._built);
    drain(100);
    ok(inst._moveTween !== null, "T29 (전제) 드래그 전 트윈 진행 중");
    Adapter.prototype._moveElement.call(inst, "a", 10, 5);   // 사용자가 노드를 잡아 끈다
    ok(inst._moveTween === null && inst._tweenPos === null, "T29 드래그가 트윈을 취소");
    const model = inst._built.nodes[0].style;
    ok(model.x === 410 && model.y === 5, "T29 드래그 델타가 모델 최종 좌표에 적용", model);
    ok(o.position.x === 410 && o.position.y === 5, "T29 화면도 손끝 위치", o.position);
    drain(1000);   // 취소된 트윈 프레임이 되살아나 덮어쓰지 않는다
    ok(o.position.x === 410 && o.position.y === 5, "T29 취소 후 stale 프레임이 드래그 위치를 덮지 않음", o.position);
  }
  // ⑪ 요소 bounds 가 **보이는 위치**를 따른다 — 카메라 보정(`_metaGraphKeepInView`)·중앙 focus 가 이 값을
  //    읽는다. 최종 좌표를 주면 노드가 아직 반대편에 그려진 동안 카메라가 목적지로 가버려, 애니메이션
  //    내내 그 노드가 화면 밖이 된다("선택한 노드를 잃지 않게" 요구의 정반대 — codex review 4차 P2).
  {
    const inst = mkInst(0);
    inst._built = { nodes: [{ id: "a", type: "rect", style: { x: 0, y: 0, size: [100, 24], zIndex: 4 } }], edges: [], combos: [] };
    inst.setData({ nodes: [{ id: "a", type: "rect", style: { x: 1000, y: 0, size: [100, 24], zIndex: 4 } }], edges: [], combos: [] });
    inst._objs.set("a", mkObj());
    clock = 0;
    inst._startMoveTween(inst._built);
    const b0 = Adapter.prototype.getElementRenderBounds.call(inst, "a");
    ok(b0 && Math.abs(b0.center[0] - 0) < 1e-6, "T29 개시 시 bounds = 출발 위치(카메라가 보이는 곳을 본다)", b0 && b0.center);
    drain(180);
    const b1 = Adapter.prototype.getElementRenderBounds.call(inst, "a");
    ok(b1.center[0] > 0 && b1.center[0] < 1000, "T29 진행 중 bounds = 보간 위치(목적지 아님)", b1.center);
    drain(1000);
    const b2 = Adapter.prototype.getElementRenderBounds.call(inst, "a");
    ok(Math.abs(b2.center[0] - 1000) < 1e-6, "T29 안착 후 bounds = 최종 위치", b2.center);
  }
  // ⑫ `isElementAnimating` — 카메라 보정이 "지금 보인다" 로 조기 종료하지 않게 하는 신호.
  {
    const inst = mkInst(0);
    const o = seed(inst, [0, 0], [400, 0]);
    ok(Adapter.prototype.isElementAnimating.call(inst, "a") === false, "T29 트윈 전 = 미이동");
    clock = 0;
    inst._startMoveTween(inst._built);
    ok(Adapter.prototype.isElementAnimating.call(inst, "a") === true, "T29 트윈 중 = 이동 중");
    ok(Adapter.prototype.isElementAnimating.call(inst, "zzz") === false, "T29 이동 대상 아닌 id 는 false");
    ok(Adapter.prototype.isElementAnimating.call(inst) === true, "T29 인자 생략 = 트윈 존재 여부");
    drain(1000);
    ok(Adapter.prototype.isElementAnimating.call(inst, "a") === false, "T29 안착 후 = 미이동");
    ok(o.position.x === 400, "T29 (전제) 안착 확인");
  }
  // ⑬ dragstart 가 트윈을 **먼저** 끝낸다 — graph-core 핸들러가 모델 좌표로 잡기 오프셋을 계산하므로,
  //    트윈이 살아 있으면 첫 델타가 튀고 종속 이동 offset 이 어긋난다.
  {
    const inst = mkInst(0);
    const o = seed(inst, [0, 0], [400, 0]);
    inst._emit = () => {};
    inst._renderMinimapViewport = () => {};
    inst._flushEdgeRefresh = () => {};
    inst._payload = () => ({});
    clock = 0;
    inst._startMoveTween(inst._built);
    drain(100);
    ok(inst._moveTween !== null, "T29 (전제) dragstart 전 트윈 진행 중");
    Adapter.prototype._emitDrag.call(inst, "dragstart", { id: "a" }, null, { x: 0, y: 0 }, 0, 0);
    ok(inst._moveTween === null, "T29 dragstart 가 트윈을 종료");
    ok(o.position.x === 400 && Adapter.prototype.getElementPosition.call(inst, "a")[0] === 400,
      "T29 dragstart 후 화면·모델 좌표 일치(잡기 오프셋 정합)", o.position.x);
  }
  // ⑭ 정지 시에도 **현재** 오브젝트를 최종 위치로 — 프레임 사이 교체(setElementState)가 있었으면
  //    캡처된 참조는 파기된 것이라, 그것만 옮기면 화면에 남은 새 오브젝트가 중간 위치에 굳는다.
  {
    const inst = mkInst(0);
    const oldObj = seed(inst, [0, 0], [400, 0]);
    inst._scheduleEdgeRefresh = () => {};
    clock = 0;
    inst._startMoveTween(inst._built);
    drain(100);
    const fresh = mkObj(); fresh.position.set(oldObj.position.x, 0);   // 교체본은 중간 위치에 있다
    inst._objs.set("a", fresh);
    inst._stopMoveTween();
    ok(fresh.position.x === 400, "T29 정지 시 교체본이 최종 위치로 안착", fresh.position.x);
  }
  frames.length = 0;
}

// ── T30 트윈 중 hit-test 정합(WYSIWYG) ──
//   grid 를 최종 좌표로 두면 **보이는 자리는 안 눌리고 빈 목적지가 눌린다**(codex review P2).
{
  const nodes = [{ id: "a", type: "rect", style: { x: 900, y: 0, size: [100, 24], zIndex: 4 } }];
  const seen = new Map([["a", [0, 0]]]);          // 지금 화면에 보이는 위치
  const posOf = (n) => seen.get(n.id) || null;
  // 평시(트윈 없음) — grid 가 최종 좌표에서 잡는다
  {
    const hg = Pure.buildHitGrid(nodes, 128);
    ok(Pure.hitTest(900, 0, hg, nodes) !== null, "T30 평시: 최종 좌표에서 hit");
    ok(Pure.hitTest(0, 0, hg, nodes) === null, "T30 평시: 다른 좌표는 miss(무회귀)");
  }
  // 트윈 중 — 이동 노드는 선형 스캔(hitTestMoving)이 **보이는 좌표**로 잡는다
  {
    const movers = [{ n: nodes[0], at: seen.get("a") }];
    ok(Pure.hitTestMoving(0, 0, movers) !== null, "T30 트윈 중: 보이는 좌표에서 hit(선형 스캔)");
    ok(Pure.hitTestMoving(900, 0, movers) === null, "T30 트윈 중: 아직 도착 안 한 목적지는 miss");
    ok(Pure.hitTestMoving(0, 0, movers, () => false) === null, "T30 hitTestMoving 도 tier filter 적용");
    ok(Pure.hitTestMoving(0, 0, []) === null && Pure.hitTestMoving(0, 0, null) === null, "T30 빈 movers 안전");
    // `at` 은 트윈이 제자리 갱신하는 배열 — 재할당 없이 판정이 따라간다
    seen.get("a")[0] = 450;
    ok(Pure.hitTestMoving(450, 0, movers) !== null, "T30 at 배열 제자리 갱신이 판정에 반영");
    seen.get("a")[0] = 0;
  }
  // grid 와 hitTest 의 override 는 **짝** — 한쪽만 주면 판정이 어긋난다(계약 명시)
  // nodeBBox 의 중심 override
  {
    const b = Pure.nodeBBox(nodes[0], [10, 20]);
    ok(b.x === -40 && b.y === 8 && b.w === 100 && b.h === 24, "T30 nodeBBox 중심 override", b);
    const b0 = Pure.nodeBBox(nodes[0]);
    ok(b0.x === 850, "T30 override 없으면 기존 동작(무회귀)", b0);
  }
  // **배선** — 순수함수가 옳아도 `_pick` 이 override 를 넘기지 않으면 화면과 클릭이 어긋난 채 통과한다
  //   (§16.7 G6 계열: 로직이 아니라 등록 누락이 결함이 되는 부류). 호출부 레벨로 잠근다.
  {
    const tp = new Map([["a", [0, 0]]]);
    const ctx = {
      _hoverCard: null, _built: { nodes, edges: [], combos: [] },
      _hitGrid: Pure.buildHitGrid(nodes, 128),
      _isCatBg: Adapter.prototype._isCatBg, _hitNodes: Adapter.prototype._hitNodes,
      _tweenPos: tp, _tweenMovers: [{ n: nodes[0], at: tp.get("a") }],
    };
    const hit = Adapter.prototype._pick.call(ctx, 0, 0);
    ok(hit && hit.id === "a", "T30 배선 — _pick 이 트윈 좌표로 판정(보이는 자리 클릭)");
    ok(Adapter.prototype._pick.call(ctx, 900, 0) === null, "T30 배선 — 목적지는 아직 클릭 대상 아님");
    ctx._tweenPos = null; ctx._tweenMovers = null;   // 트윈 종료 → 오버레이 소멸(기존 계약 복귀)
    ok(Adapter.prototype._pick.call(ctx, 900, 0) !== null, "T30 배선 — 트윈 종료 후 최종 좌표 판정 복귀");
  }
  // **hover 배선** — `_pick` 만 고치고 `_probeHover` 를 빠뜨리면 "클릭은 되는데 hover 는 안 되는"
  //   반쪽 상태가 된다(같은 화면·다른 판정 기준). 두 경로가 같은 override 를 쓰는지 잠근다.
  {
    const tp = new Map([["a", [0, 0]]]);
    let got = "unset";
    const ctx = {
      _ptrDown: false, _hoverCard: null, _built: { nodes, edges: [], combos: [] },
      _hitGrid: Pure.buildHitGrid(nodes, 128),
      _isCatBg: Adapter.prototype._isCatBg, _hitNodes: Adapter.prototype._hitNodes,
      _tweenPos: tp, _tweenMovers: [{ n: nodes[0], at: tp.get("a") }],
      _inMinimap: () => false, _setLabelHover(n) { got = n; },
      get _cam() { return { zoom: 1, x: 0, y: 0 }; },
    };
    Adapter.prototype._probeHover.call(ctx, 0, 0);
    ok(got && got.id === "a", "T30 배선 — _probeHover 도 트윈 좌표로 판정");
    Adapter.prototype._probeHover.call(ctx, 900, 0);
    ok(got === null, "T30 배선 — hover 도 목적지는 아직 대상 아님");
  }
  // **엣지 배선** — 관계선은 트윈 중 그려진 좌표를 따라가므로 판정 끝점도 `_resolvePos`(오버레이 우선)여야 한다.
  {
    const tp = new Map([["a", [0, 0]], ["b", [0, 200]]]);
    const ctx = {
      _built: { nodes: [], edges: [{ source: "a", target: "b", style: {} }], combos: [] },
      _nodeById: new Map([["a", { style: { x: 900, y: 0 } }], ["b", { style: { x: 900, y: 200 } }]]),
      _tweenPos: tp, _resolvePos: Adapter.prototype._resolvePos,
      getElementPosition: () => null,
      get _cam() { return { zoom: 1, x: 0, y: 0 }; },
    };
    const onVisible = Adapter.prototype._pickEdge.call(ctx, 0, 100);
    ok(!!onVisible, "T30 배선 — _pickEdge 가 보이는 관계선을 잡는다");
    ctx._tweenPos = null;   // 트윈 종료 → 모델 좌표
    ok(Adapter.prototype._pickEdge.call(ctx, 0, 100) == null, "T30 배선 — 종료 후엔 모델 좌표 기준(무회귀)");
    ok(!!Adapter.prototype._pickEdge.call(ctx, 900, 100), "T30 배선 — 종료 후 최종 좌표에서 잡힘");
  }
}

// ── T31 scene diff — graph-expand-perf: 이동은 재배치, 모양 변경만 재생성, 엣지는 in-place 재-path ──
//   실측 근거(693 노드 스키마에서 1 테이블 컬럼 펼침): 종전 diff 는 위치가 서명에 있어 이동한 형제
//   538개를 파기·재생성했고 그중 524개가 라벨 재생성이었다(drawMs 207ms). 아래는 그 회귀를 잠근다.
async function T31() {
  const mkC = () => ({ position: { x: 0, y: 0, set(x, y) { this.x = x; this.y = y; } }, destroyed: false,
    destroy() { this.destroyed = true; }, });
  const mkInst = () => {
    const inst = Object.create(Adapter.prototype);
    inst._ready = Promise.resolve();
    inst.world = { children: [], addChild(o) { this.children.push(o); o.parent = this; },
      removeChild(o) { const i = this.children.indexOf(o); if (i >= 0) this.children.splice(i, 1); } };
    inst._objs = new Map(); inst._objSig = null; inst._built = { nodes: [], edges: [], combos: [] };
    inst.made = { node: 0, combo: 0, edge: 0, paint: 0 };
    inst._stopMoveTween = () => {}; inst._stopHoverFlow = () => {}; inst._clearHoverLayer = () => {};
    inst._clearLabelHover = () => {}; inst._renderMinimap = () => {}; inst._render = () => {};
    inst._startMoveTween = () => {}; inst._emit = () => {};
    inst._drawNode = (n) => { inst.made.node++; const c = mkC(); c.position.set(n.style.x, n.style.y); inst._objs.set(n.id, c); return c; };
    inst._drawCombo = (c, bb) => { inst.made.combo++; const o = mkC(); o.position.set(bb.x, bb.y); inst._objs.set(c.id, o); return o; };
    inst._drawEdge = (e) => { inst.made.edge++; const g = mkC(); g.clear = () => {}; return g; };
    inst._paintEdge = (g) => { inst.made.paint++; return g; };
    inst.getElementRenderBounds = () => null;
    return inst;
  };
  const scene = (dx) => ({
    nodes: [{ id: "a", type: "rect", combo: "S", states: [], style: { x: 0 + dx, y: 0, size: [100, 24], fill: "#0f7d8c" } },
            { id: "b", type: "rect", combo: "S", states: [], style: { x: 200 + dx, y: 0, size: [100, 24], fill: "#0f7d8c" } }],
    edges: [{ id: "e1", source: "a", target: "b", style: { stroke: "#ccc" } }],
    combos: [{ id: "S", style: { fill: "#3f4b8c" } }],
  });
  const inst = mkInst();
  inst.setData(scene(0)); await inst.draw();
  ok(inst.made.node === 2 && inst.made.combo === 1 && inst.made.edge === 1, "T31 최초 draw — 전부 생성");
  const objA = inst._objs.get("a"), objS = inst._objs.get("S");
  // ① 전원 이동(모양 동일) → 재생성 0, 재배치 2, 엣지는 in-place 재-path
  inst.setData(scene(500)); await inst.draw();
  ok(inst.made.node === 2, "T31 이동만 → 노드 재생성 0(누적 2 유지)");
  ok(inst._objs.get("a") === objA, "T31 이동해도 같은 오브젝트 재사용(라벨 재생성 없음)");
  ok(objA.position.x === 500, "T31 재사용 오브젝트가 새 위치로 재배치됨");
  ok(objA.destroyed === false, "T31 이동 노드가 파기되지 않음");
  ok(inst._lastDrawStats.made === 0 && inst._lastDrawStats.moved === 3, "T31 통계 — made 0 / moved 3(노드2+combo1)");
  ok(inst.made.edge === 1 && inst.made.paint === 1, "T31 끝점 이동 엣지는 in-place 재-path(재생성 0)");
  ok(inst._objs.get("S") === objS, "T31 combo 오브젝트 재사용");
  ok(objS.position.x === (500 - 100 / 2 - 16), "T31 combo 도 원점만 이동 → 재배치(bbox 좌측 pad)");
  // ② 모양 변경(states) → 그 노드만 재생성
  const s2 = scene(500); s2.nodes[0].states = ["selected"];
  inst.setData(s2); await inst.draw();
  ok(inst.made.node === 3, "T31 states 변경 노드만 재생성(+1)");
  ok(objA.destroyed === true, "T31 재생성 대상은 파기됨");
  ok(inst._objs.get("b") !== undefined && inst._lastDrawStats.made === 1, "T31 형제는 그대로 재사용");
  // ③ combo 크기 변경(컬럼 펼침으로 자식 bbox 확대) → combo 재생성
  const s3 = scene(500); s3.nodes[1].style.size = [100, 400];
  inst.setData(s3); await inst.draw();
  ok(inst.made.combo === 2, "T31 combo 크기 변경 → 재생성");
}

T31().then(() => {
  console.log("──────");
  console.log((fail === 0 ? "ALL PASS" : "FAIL") + " — " + pass + " PASS / " + fail + " FAIL");
  process.exit(fail === 0 ? 0 : 1);
});
