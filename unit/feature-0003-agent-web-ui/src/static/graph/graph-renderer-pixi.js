// feature-0016 §78 Phase B — SceneAdapter (PixiJS v8 렌더러, G6.Graph 인터페이스 호환)
//
// 목적: graph-core.js 의 `_metaG6Build()` 출력(scene-spec = G6 data-shape, SCENE_SPEC.md)을
//   PixiJS v8(WebGL/WebGPU) 씬으로 렌더한다. 팬/줌은 world Container transform 1회 갱신
//   (GPU 상주 — 매 프레임 CPU 재래스터 제거, ADR-030 병목 해소). G6.Graph 가 노출하던 메서드를
//   미러해 graph-core 배선을 최소화한다(setData→setScene 치환).
//
// 설계 경계:
//   - 순수 로직(엔진 무관, node 테스트 대상): camera 변환 수학·hit-test spatial grid·
//     대시 세그먼트·combo bbox·scene 파싱. → `PixiAdapterPure` 로 분리 export.
//   - Pixi 의존(브라우저 win-browser 실증): 씬 그래프 구성·렌더·이벤트. → `PixiGraphAdapter`.
//
// PIXI 전역은 UMD vendored(`vendor/pixi.min.js`)로 window.PIXI 에 있다(admin.html B-late 배선).
// 이 모듈은 렌더러 seam(_META_RENDERER)에서만 인스턴스화되며, 미배선 상태에서 import 되어도
// 부작용이 없다(클래스 정의만).

"use strict";

// graph-edge-flow(§83): 단일 가닥 엣지의 오프셋 배열 — 매 페인트마다 [0] 을 새로 할당하지 않도록
//   모듈 상수로 고정한다(대다수 엣지가 단일 가닥 = 최다 호출 경로의 GC 압력 제거). 불변 사용.
const EDGE_NO_STRAND = [0];

// graph-edge-encoding(§86): 두께의 줌 정책 = **줌인은 화면 고정, 줌아웃은 콘텐츠 비례**.
//
//   경위 — §84 는 줌아웃 소실만 막으려 화면 두께에 *바닥* 을 걸었고(줌인 구간은 model 고정 = 확대할수록
//   굵어짐), §85 는 그 변성을 없애려 전 구간 화면 고정으로 갔다. 그런데 전 구간 고정은 반대편 실패를
//   낳는다 — 극단 줌아웃에서 노드·간격은 작아지는데 선만 같은 두께로 남아 **선이 화면을 뒤덮는다**
//   (사용자 리포트 + 스크린샷). 두 실패는 같은 축의 양극이고, 옳은 답은 구간별로 다른 정책이다.
//
//   `w_screen = clamp(base · min(1, zoom/ZFULL), MIN, base)` ⟹ `w_model = w_screen / zoom`
//     - zoom ≥ ZFULL : w_screen = base            → 확대해도 굵어지지 않는다(§85 가 고친 변성).
//     - zoom < ZFULL : w_screen ∝ zoom            → 축소하면 콘텐츠와 함께 얇아진다(화면을 가리지 않음).
//     - 하한 MIN     : 완전 소실만 막는다          → 저밀도 단선은 희미해도, 겹치면 alpha 누적으로 드러난다.
//   즉 model 좌표로는 "줌아웃 구간에서 상수, 줌인 구간에서 1/zoom" 이다.
const EDGE_ZFULL = 1;            // 이 줌 이상에서 화면 두께를 고정(=기준 배율)
const EDGE_MIN_SCREEN_W = 0.25;  // 극단 줌아웃에서도 남기는 최소 화면 두께(완전 소실만 방지 — 기본
                                 //   굵기 대비 충분히 낮아야 줌아웃 비례 구간이 평탄해지지 않는다)

// graph-edge-hairline(§87): **서브픽셀 폭은 alpha 로 환산**한다(hairline 처리).
//
//   증상 — 줌아웃에서 관계선이 깨지고 계단지고 끊겨 보인다(사용자 리포트).
//   오진하기 쉬운 지점: "anti-aliasing 을 켜자". 그러나 AA 는 **이미 켜져 있다**
//   (`app.init({ antialias: true, resolution: devicePixelRatio })`). 원인은 AA 부재가 아니라
//   **선 폭이 1물리픽셀 미만** 이라는 데 있다 — §86 의 기본 굵기 0.6px 는 dpr 1 에서 전 줌 구간이
//   서브픽셀이고, 줌아웃하면 하한 0.25px 까지 내려간다.
//   MSAA 는 픽셀당 유한 샘플(보통 4)의 커버리지를 평균할 뿐이라, 폭 0.3px 선의 커버리지는
//   0/25/50/75% 로 **양자화**된다 → 픽셀마다 밝기가 튀어 끊겨 보이고, 대각선·곡선에서는 그 튐이
//   계단으로 읽힌다. 샘플을 늘려도 단계만 촘촘해질 뿐 근본은 그대로고 fill rate 만 먹는다.
//
//   해법(지도·CAD 렌더러의 표준 hairline 기법 — Mapbox GL·deck.gl·Skia/Cairo 동일 원리):
//   폭을 **정확히 1물리픽셀**로 올리고, 부족했던 두께분을 alpha 에 곱한다.
//     - 커버리지가 균일해져 끊김·밝기 계단이 원천 소멸한다.
//     - 시각적 '가늘기' 는 alpha 가 연속적으로 표현하므로 "가느다랗게" 요구는 그대로 유지된다.
//     - 비용은 산술 몇 줄. MSAA 증설·resolution 상향 같은 전역 비용이 없다.
//   트레이드오프: 서브픽셀 구간에서 굵기(개수 축)의 일부가 alpha(신뢰도 축)와 곱해진다. 다만 그
//   구간은 애초에 굵기 차이를 눈으로 분해할 수 없는 영역이라, alpha 로 옮기는 편이 정보를 **더**
//   보존한다. 1물리픽셀 이상 구간에서는 두 축이 종전대로 분리된다.
function edgeHairline(baseScreen, zoom, dpr) {
  const z = Math.max(0.02, zoom || 1);
  const d = Math.max(1, dpr || 1);
  const wScreen = Math.max(EDGE_MIN_SCREEN_W, Math.min(baseScreen, baseScreen * (z / EDGE_ZFULL)));
  const minCss = 1 / d;   // 1 물리픽셀에 해당하는 CSS px (Pixi 는 resolution 을 곱해 렌더한다)
  if (wScreen >= minCss) return { w: wScreen / z, fade: 1 };
  return { w: minCss / z, fade: wScreen / minCss };   // 폭은 1물리픽셀로, 모자란 두께분은 alpha 로
}

// ─────────────────────────────────────────────────────────────────────────────
// 순수 로직 (엔진 무관) — node vm 테스트 대상
// ─────────────────────────────────────────────────────────────────────────────

export const PixiAdapterPure = {
  // 카메라: world transform (scale=zoom, position=pan). G6 좌표 의미와 동일하게.
  //   model→screen: s = m*zoom + pan.  screen→model: m = (s - pan)/zoom.
  //   ⚠ G6 명명 역설 유지: getCanvasByViewport = model→screen, getViewportByCanvas = screen→model.
  modelToScreen(mx, my, cam) { return [mx * cam.zoom + cam.x, my * cam.zoom + cam.y]; },
  screenToModel(sx, sy, cam) { return [(sx - cam.x) / cam.zoom, (sy - cam.y) / cam.zoom]; },

  clampZoom(z, range) { return Math.max(range[0], Math.min(range[1], z)); },

  // fit: 콘텐츠 bounds 를 뷰포트에 맞추는 zoom+pan (여백 pad px, 판독 하한 minZoom).
  fitCamera(bounds, viewport, opts) {
    const pad = (opts && opts.pad != null) ? opts.pad : 80, range = (opts && opts.range) || [0.05, 4];
    const minRead = (opts && opts.minReadZoom) || 0;
    if (!bounds || bounds.w <= 0 || bounds.h <= 0) return { zoom: 1, x: 0, y: 0 };
    let z = Math.min((viewport.w - pad) / bounds.w, (viewport.h - pad) / bounds.h);
    z = Math.max(range[0], Math.min(range[1], z));
    if (minRead && z < minRead) z = minRead;   // graph-initview A1: 초기 fit 판독 하한 클램프
    const x = (viewport.w - bounds.w * z) / 2 - bounds.x * z;
    const y = (viewport.h - bounds.h * z) / 2 - bounds.y * z;
    return { zoom: z, x, y };
  },

  // 커서 고정 줌: 커서 아래 model 점이 화면상 같은 위치에 남도록 pan 보정.
  zoomAroundCursor(cam, factor, cursor, range) {
    const nz = this.clampZoom(cam.zoom * factor, range);
    const [mx, my] = this.screenToModel(cursor.x, cursor.y, cam);
    return { zoom: nz, x: cursor.x - mx * nz, y: cursor.y - my * nz };
  },

  // graph-move-anim(사용자 요청 2026-08-13 "노드 위치 재배치가 깜빡이는 순식간이라 이동을 인지할 수 없다"):
  //   직전 씬 대비 **어느 노드를 애니메이션으로 옮길지** 고르는 순수 판정. `draw()` 의 오브젝트 풀 diff 는
  //   이동 노드를 최종 위치로 **재배치**(graph-expand-perf 이전에는 파기→재생성)하므로 중간 프레임이 아예
  //   없다 — 여기서 고른 노드만 어댑터가 `from → to` 로 트윈한다.
  //   선별 기준(비용 상한이 곧 정확성 — 대형 스코프에서 전량 트윈은 프레임을 무너뜨린다):
  //     ① 직전 씬과 새 씬 **양쪽에 존재**하고 이동량이 minDelta 초과 — 신규/소멸 노드는 대상 아님.
  //     ② `vis`(model 좌표 가시 rect, 마진 포함) 안에 **출발 또는 도착**이 걸린 노드만 — 화면 밖 이동은
  //        보이지 않으므로 애니메이션 가치가 0 이고 비용만 든다.
  //     ③ `cap` 초과분은 잘라내고 `skipped` 로 **보고**한다(무음 절단 금지 — AGENTS.md §16.7 G9-b).
  //     ④ **씬 교체 감지** — 직전과 겹치는 노드 비율이 minOverlap 미만이면 재배치가 아니라 새 화면이다
  //        (스코프 전환·검색·중심보기). 이때 트윈은 '날아다니는 화면'이 되므로 통째로 포기한다.
  //   반환 {items:[{id,from:[x,y],to:[x,y]}], moved, skipped, reason}. reason 은 빈 결과의 사유(관측용).
  moveTweenPlan(prevPos, nodes, opts) {
    const o = opts || {};
    const minDelta = (o.minDelta != null) ? o.minDelta : 0.5;
    const cap = (o.cap != null) ? o.cap : 600;
    const minOverlap = (o.minOverlap != null) ? o.minOverlap : 0.3;
    const vis = o.vis || null;
    const list = nodes || [];
    const empty = (reason) => ({ items: [], moved: 0, skipped: 0, reason });
    if (!prevPos || typeof prevPos.get !== "function" || !prevPos.size || !list.length) return empty("no-prev");
    let overlap = 0;
    for (const n of list) if (prevPos.has(n.id)) overlap += 1;
    // 분모는 **양쪽 씬의 큰 쪽**이다. 새 씬 기준만 쓰면 이전 씬의 부분집합(검색 prune·모드 전환으로 500개
    //   중 1개만 남는 경우)이 겹침 100% 로 계산돼 가드를 그대로 통과한다 — 남은 1개가 옛 배치에서
    //   날아오는 그림이 되고, 그것이 정확히 이 가드가 막으려던 '새 화면' 이다(codex review 2차 P2).
    if (overlap / Math.max(list.length, prevPos.size) < minOverlap) return empty("scene-switch");
    const inVis = (x, y) => !vis || (x >= vis.x0 && x <= vis.x1 && y >= vis.y0 && y <= vis.y1);
    const items = [];
    let moved = 0, skipped = 0;
    for (const n of list) {
      const p = prevPos.get(n.id);
      if (!p) continue;
      const s = n.style || {};
      const tx = s.x, ty = s.y;
      if (!isFinite(tx) || !isFinite(ty) || !isFinite(p[0]) || !isFinite(p[1])) continue;
      if (Math.abs(tx - p[0]) <= minDelta && Math.abs(ty - p[1]) <= minDelta) continue;
      moved += 1;
      if (!inVis(p[0], p[1]) && !inVis(tx, ty)) { skipped += 1; continue; }   // 화면 밖 이동 — 즉시 반영
      if (items.length >= cap) { skipped += 1; continue; }                    // 상한 초과 — 즉시 반영(보고됨)
      items.push({ id: n.id, from: [p[0], p[1]], to: [tx, ty] });
    }
    return { items, moved, skipped, reason: items.length ? "" : (moved ? "all-filtered" : "no-move") };
  },

  // 대시 세그먼트: 폴리라인을 [on,off] 반복으로 분할 → [[x1,y1,x2,y2],...] (D2 점선 등가).
  dashSegments(x1, y1, x2, y2, dash) {
    const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len, segs = [];
    let t = 0, on = true, i = 0;
    while (t < len) {
      const seg = Math.min(dash[i % dash.length], len - t);
      if (on) segs.push([x1 + ux * t, y1 + uy * t, x1 + ux * (t + seg), y1 + uy * (t + seg)]);
      t += seg; on = !on; i++;
    }
    return segs;
  },

  // 원형 대시: 호 길이 기준 [on,off] 반복 → [[a0,a1],...] 라디안 구간 목록. dashSegments 의 원형 등가.
  //   반지름 r 위에서 호 길이 L 은 각도 L/r 이므로 직선 대시와 **같은 화면 대시 길이**가 나온다.
  dashArcs(r, dash) {
    const rr = Math.max(r, 1e-6), circ = 2 * Math.PI * rr, arcs = [];
    let t = 0, on = true, i = 0;
    while (t < circ) {
      const seg = Math.min(dash[i % dash.length], circ - t);
      if (on) arcs.push([t / rr, (t + seg) / rr]);
      t += seg; on = !on; i++;
    }
    return arcs;
  },

  // 상태 테두리(halo) 기하 — 노드의 **모양과 크기에 비례**해 산출한다(graph-analyzed-halo-fit).
  //   ① circle 노드(컬럼 지름 11 · 루틴 파라미터)는 **원형** halo. 종전엔 rect 경로만 있어 h 가 기본값
  //      24 로 잡혀 11px 점 주위에 17×30 알약이 그려졌다(사용자 리포트 2026-07-28 "노드 크기에 비해
  //      테두리가 비대"). 모양 자체가 어긋난 것이 지배 원인이고, 두께는 그 다음이다.
  //   ② 두께·여백은 노드 최소변에 비례: k = clamp(min(w,h)/24, 0.4, 1). 24 는 테이블/루틴 칩 높이라
  //      **모든 rect 노드에서 k=1 → 기존 수치 그대로**(회귀 0). 11px 컬럼은 k≈0.458 → 3px 테두리가
  //      1.4px 링으로 줄어 점을 삼키지 않는다.
  //   ③ 동심링 간격(다중 상태 동시 표기)도 같은 비율 — 작은 노드에서 링이 밖으로 퍼지지 않는다.
  //   반환: {shape:"circle", r, lw} | {shape:"rect", x, y, w, h, radius, lw} — r/x/y 는 **stroke 중심선**.
  haloGeom(n, i, lineWidth) {
    const s = n.style || {}, isCircle = n.type === "circle";
    const w = isCircle ? (typeof s.size === "number" ? s.size : 11)
                       : (Array.isArray(s.size) ? s.size[0] : (s.size || 24));
    const h = isCircle ? w : (Array.isArray(s.size) ? s.size[1] : 24);
    const k = Math.max(0.4, Math.min(1, Math.min(w, h) / 24));
    const lw = Math.max(1, (lineWidth || 1) * k);
    const gap = Math.max(1.5, 3 * k);        // 노드 표면 ↔ 링 중심선 여백(작은 노드도 흰 테를 남긴다)
    const off = gap + (i || 0) * 2 * k;      // 동심링: 상태 순서마다 바깥으로 2*k
    if (isCircle) return { shape: "circle", r: w / 2 + off, lw };
    return { shape: "rect", x: -w / 2 - off, y: -h / 2 - off, w: w + 2 * off, h: h + 2 * off,
      radius: (s.radius || 4) + off - 1, lw };
  },

  // 노드 bbox (모델 좌표, 좌상단 기준). rect=[w,h] 중심, circle=지름 중심.
  //   `at`(선택, [x,y]): 중심 좌표 override. graph-move-anim 트윈 중에는 모델(`n.style`)이 이미 **최종**
  //   위치라, 화면에 보이는 위치로 hit-test 하려면(WYSIWYG) 중심만 갈아끼운 bbox 가 필요하다.
  nodeBBox(n, at) {
    const s = n.style || {};
    const cx = at ? at[0] : s.x, cy = at ? at[1] : s.y;
    if (n.type === "circle") { const r = (typeof s.size === "number" ? s.size : 11) / 2; return { x: cx - r, y: cy - r, w: 2 * r, h: 2 * r }; }
    const w = Array.isArray(s.size) ? s.size[0] : (s.size || 100), h = Array.isArray(s.size) ? s.size[1] : 24;
    return { x: cx - w / 2, y: cy - h / 2, w, h };
  },

  // combo bbox = 자식 union + padding (G6 auto-fit 대체). combo 미소속 노드는 무시.
  comboBBox(comboId, nodes, padding) {
    const pad = padding || [30, 16, 14, 16];   // [top,right,bottom,left]
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, has = false;
    for (const n of nodes) {
      if (n.combo !== comboId) continue;
      const b = this.nodeBBox(n); has = true;
      minX = Math.min(minX, b.x); minY = Math.min(minY, b.y);
      maxX = Math.max(maxX, b.x + b.w); maxY = Math.max(maxY, b.y + b.h);
    }
    if (!has) return null;
    return { x: minX - pad[3], y: minY - pad[0], w: (maxX - minX) + pad[1] + pad[3], h: (maxY - minY) + pad[0] + pad[2] };
  },

  // 전체 콘텐츠 bounds (fitView 용).
  contentBounds(built) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, has = false;
    const acc = (b) => { if (!b) return; has = true; minX = Math.min(minX, b.x); minY = Math.min(minY, b.y); maxX = Math.max(maxX, b.x + b.w); maxY = Math.max(maxY, b.y + b.h); };
    for (const n of (built.nodes || [])) acc(this.nodeBBox(n));
    for (const c of (built.combos || [])) acc(this.comboBBox(c.id, built.nodes || [], (c.style || {}).padding));
    if (!has) return { x: 0, y: 0, w: 0, h: 0 };
    return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
  },

  // Spatial hit-grid: 노드 bbox 를 셀에 버킷팅. 팬/줌 무관 모델 좌표 grid → O(1) 근방 조회.
  //   per-object Pixi 이벤트(대량 오브젝트에서 느림) 대신 이 grid 로 pointer picking 을 합성.
  buildHitGrid(nodes, cell) {
    const c = cell || 128, grid = new Map();
    const key = (cx, cy) => cx + "," + cy;
    for (const n of nodes) {
      const b = this.nodeBBox(n);
      const x0 = Math.floor(b.x / c), x1 = Math.floor((b.x + b.w) / c);
      const y0 = Math.floor(b.y / c), y1 = Math.floor((b.y + b.h) / c);
      for (let cx = x0; cx <= x1; cx++) for (let cy = y0; cy <= y1; cy++) {
        const k = key(cx, cy); if (!grid.has(k)) grid.set(k, []); grid.get(k).push(n);
      }
    }
    return { grid, cell: c };
  },

  // model 점 위 최상위(z 큰) 노드. hit-grid 사용. filter(n)→false 인 노드는 제외(층서 tier 분리용).
  hitTest(mx, my, hg, nodes, filter) {
    const cx = Math.floor(mx / hg.cell), cy = Math.floor(my / hg.cell);
    const bucket = hg.grid.get(cx + "," + cy) || [];
    let best = null, bestZ = -Infinity;
    for (const n of bucket) {
      if (filter && !filter(n)) continue;
      const b = this.nodeBBox(n);
      if (mx < b.x || mx > b.x + b.w || my < b.y || my > b.y + b.h) continue;
      const z = (n.style && n.style.zIndex) || 0;
      if (z >= bestZ) { bestZ = z; best = n; }
    }
    return best;
  },

  // graph-move-anim: **이동 중인 노드**만 대상으로 하는 선형 hit-test. 트윈 중 노드는 모델(최종) 좌표에
  //   버킷팅된 grid 로는 찾을 수 없다(보이는 자리는 비어 있고 목적지가 눌린다). grid 를 매 프레임 다시
  //   굽는 방법도 있으나 그건 **화면 전체 노드**에 비례하는 비용을 22 프레임 반복하는 것이라, 이동 대상이
  //   상한(트윈 cap)으로 묶인 선형 스캔을 **포인터 이벤트당 1회** 하는 쪽이 싸다(프레임당 비용 0).
  //   movers: [{n, at:[x,y]}] — `at` 은 트윈이 매 프레임 제자리 갱신하는 배열이라 재할당이 없다.
  hitTestMoving(mx, my, movers, filter) {
    let best = null, bestZ = -Infinity;
    for (const m of (movers || [])) {
      const n = m.n;
      if (filter && !filter(n)) continue;
      const b = this.nodeBBox(n, m.at);
      if (mx < b.x || mx > b.x + b.w || my < b.y || my > b.y + b.h) continue;
      const z = (n.style && n.style.zIndex) || 0;
      if (z >= bestZ) { bestZ = z; best = n; }
    }
    return best;
  },

  // combo 히트: 노드가 없을 때 폴백(스키마 배경 클릭/우클릭). 자식 union bbox 안이면 그 combo.
  hitTestCombo(mx, my, combos, nodes) {
    let best = null, bestArea = Infinity;   // 여러 combo 겹치면 가장 작은(구체) 것
    for (const c of combos) {
      const b = this.comboBBox(c.id, nodes, (c.style || {}).padding); if (!b) continue;
      if (mx < b.x || mx > b.x + b.w || my < b.y || my > b.y + b.h) continue;
      const area = b.w * b.h; if (area < bestArea) { bestArea = area; best = c; }
    }
    return best;
  },

  // ── graph-edge-flow(§83): 방향성 곡선 관계선 ──────────────────────────────
  // 곡률 오프셋은 **진행방향(a→b) 기준 항상 같은 쪽(왼쪽 수직)**. 따라서 A→B 와 B→A 가 자동으로
  //   반대편 호를 그린다 — 같은 두 객체 사이의 읽기/쓰기가 겹치지 않고 렌즈 모양으로 갈라진다
  //   (Cytoscape.js 평행엣지 자동 bezier·Gephi "수직 컨트롤포인트" 관례와 동일 어휘).
  //   반환: len(직선 길이) · c(컨트롤 포인트) · off(중점 편차, 부호=휘는 쪽) · p*(왼쪽 단위 수직).
  //   quadratic Q(0.5) = (a + 2c + b)/4 이므로 중점 편차를 off 로 만들려면 컨트롤을 2·off 로 민다.
  edgeArc(a, b, k, maxOff, minOff) {
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
    const px = dy / len, py = -dx / len;   // 진행방향 왼쪽(화면 y-down 좌표계)
    const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
    if (!k) return { len, cx: mx, cy: my, off: 0, px, py };
    const sgn = k < 0 ? -1 : 1;
    const off = sgn * Math.max(minOff == null ? 5 : minOff, Math.min(maxOff == null ? 44 : maxOff, len * Math.abs(k)));
    return { len, cx: mx + px * off * 2, cy: my + py * off * 2, off, px, py };
  },
  // quadratic bezier 샘플 폴리라인 — 대시 분할·히트테스트 근사 전용(실선은 Pixi 네이티브 tessellation).
  quadPoints(a, c, b, segs) {
    const n = Math.max(1, segs | 0), pts = new Array(n + 1);
    for (let i = 0; i <= n; i++) {
      const t = i / n, u = 1 - t, w0 = u * u, w1 = 2 * u * t, w2 = t * t;
      pts[i] = [w0 * a[0] + w1 * c[0] + w2 * b[0], w0 * a[1] + w1 * c[1] + w2 * b[1]];
    }
    return pts;
  },
  // adaptive 세그먼트 수 — **화면 픽셀** 길이 기준이라 줌아웃 시 자동으로 줄어든다(공격적 최적화).
  //   lowFi=드래그 중(rAF 코얼레싱 프레임) → 상한·해상도 절반. 실선 경로는 애초에 호출하지 않는다.
  curveSegs(len, zoom, lowFi) {
    const px = len * (zoom || 1);
    const n = Math.ceil(px / (lowFi ? 34 : 17));
    return Math.max(lowFi ? 3 : 5, Math.min(lowFi ? 10 : 22, n));
  },
  // 폴리라인 전체를 하나의 연속 길이로 보고 대시 위상을 이어붙인다 — 구간마다 위상을 리셋하면
  //   곡선 샘플 경계마다 대시가 뭉쳐 "점선이 굵어 보이는" 아티팩트가 생긴다. 반환 형식은 dashSegments 와 동일.
  // detail-hover-flow: 선택적 `phase`(호 길이 단위) — 패턴을 그만큼 **미리 소비한 상태**로 시작한다.
  //   phase 를 프레임마다 키우면 대시가 pts[0] 쪽으로 되감기고, 줄이면(음수) pts[끝] 쪽으로 흐른다.
  //   호출부(setHoverHighlight)는 데이터 흐름 방향에 맞춰 부호를 정한다. 미지정이면 종전과 동일(위상 0).
  dashPolyline(pts, dash, phase) {
    const segs = []; let i = 0, on = true, rem = dash[0];
    if (phase) {
      // 실주기: 홀수 길이 패턴은 on/off 가 뒤집혀 한 번 더 돌아야 원위상 — 그때만 2배.
      let sum = 0; for (let k = 0; k < dash.length; k++) sum += dash[k];
      const T = (dash.length % 2 ? 2 : 1) * sum;
      let p = T > 0 ? ((phase % T) + T) % T : 0;
      while (p > 1e-9) {
        const step = Math.min(rem, p); rem -= step; p -= step;
        if (rem <= 1e-9) { i++; rem = dash[i % dash.length]; on = !on; }
      }
    }
    for (let s = 0; s < pts.length - 1; s++) {
      const p = pts[s], q = pts[s + 1];
      const dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy);
      if (!L) continue;
      const ux = dx / L, uy = dy / L; let t = 0;
      while (t < L) {
        const step = Math.min(rem, L - t);
        if (on) segs.push([p[0] + ux * t, p[1] + uy * t, p[0] + ux * (t + step), p[1] + uy * (t + step)]);
        t += step; rem -= step;
        if (rem <= 1e-9) { i++; rem = dash[i % dash.length]; on = !on; }
      }
    }
    return segs;
  },
  // detail-hover-flow: 관계선 스타일 → **데이터 흐름이 (source→target) 방향인가**.
  //   graph-roleviz 의 화살표 어휘가 그대로 흐름 어휘다: 쓰기(루틴→테이블)·REFERENCES 는 endArrow 라
  //   선언 방향으로 흐르고, 읽기(테이블→루틴)는 startArrow 라 **역류**한다(AGE 모델은 항상 Routine→Table
  //   로 저장되므로 읽기의 데이터 흐름은 target→source). 화살표가 둘 다거나 없으면(SCHEMA_REF 등)
  //   선언 방향 폴백.
  flowForward(style) { const s = style || {}; return !(s.startArrow && !s.endArrow); },
  // 스트랜드(다발) 가닥별 오프셋 배율 — 상위 부모가 품은 관계 수의 '볼륨' 표현. 중앙 대칭 분포.
  strandOffsets(n, spread) {
    const c = Math.max(1, Math.min(6, n | 0)), sp = spread == null ? 3.2 : spread, out = new Array(c);
    for (let i = 0; i < c; i++) out[i] = (i - (c - 1) / 2) * sp;
    return out;
  },

  // edge 히트: 점-선분 거리 ≤ tol(model px)인 최근접 엣지(우클릭 컨텍스트 메뉴용, gap #12).
  //   graph-edge-flow: 곡선 엣지는 저해상도(lowFi) 샘플 폴리라인으로 근사한다 — 직선 거리로 판정하면
  //   호의 배(중앙부 최대 off px)만큼 어긋나 "보이는 선을 눌렀는데 안 잡히는" 괴리가 생긴다.
  hitTestEdge(mx, my, edges, posOf, tol, zoom) {
    const t = tol || 6; let best = null, bestD = t;
    for (const e of edges) {
      const a = posOf(e.source), b = posOf(e.target); if (!a || !b) continue;
      const st = e.style || {}, k = st.curve || 0;
      let d;
      if (k) {
        const arc = this.edgeArc(a, b, k, st.curveMax, st.curveMin);
        const pts = this.quadPoints(a, [arc.cx, arc.cy], b, this.curveSegs(arc.len, zoom || 1, true));
        d = Infinity;
        for (let i = 0; i < pts.length - 1; i++) {
          const dd = this._segDist(mx, my, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]);
          if (dd < d) d = dd;
        }
      } else d = this._segDist(mx, my, a[0], a[1], b[0], b[1]);
      if (d <= bestD) { bestD = d; best = e; }
    }
    return best;
  },
  _segDist(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1, L2 = dx * dx + dy * dy;
    let t = L2 ? ((px - x1) * dx + (py - y1) * dy) / L2 : 0; t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
  },

  // 미니맵 projection: contentBounds+size → {s,ox,oy,bx,by} (콘텐츠를 미니맵 박스에 letterbox). 이슈#2/#3 공용.
  minimapProjection(bounds, size, pad) {
    const [mw, mh] = size, p = pad == null ? 6 : pad;
    if (!bounds || bounds.w <= 0 || bounds.h <= 0) return null;
    const s = Math.min((mw - 2 * p) / bounds.w, (mh - 2 * p) / bounds.h);
    return { s, ox: p + (mw - 2 * p - bounds.w * s) / 2, oy: p + (mh - 2 * p - bounds.h * s) / 2, bx: bounds.x, by: bounds.y };
  },
  // 미니맵 로컬 점 → model (이슈#3 드래그 역투영).
  minimapToModel(lx, ly, pr) { return [pr.bx + (lx - pr.ox) / pr.s, pr.by + (ly - pr.oy) / pr.s]; },
  // 뷰포트 model 사각형 → 미니맵 좌표(경계 클램프, 이슈#2).
  minimapViewportRect(m0, m1, pr, size) {
    const [mw, mh] = size, cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const x0 = cl(pr.ox + (m0[0] - pr.bx) * pr.s, 0, mw), y0 = cl(pr.oy + (m0[1] - pr.by) * pr.s, 0, mh);
    const x1 = cl(pr.ox + (m1[0] - pr.bx) * pr.s, 0, mw), y1 = cl(pr.oy + (m1[1] - pr.by) * pr.s, 0, mh);
    return { x: x0, y: y0, w: Math.max(0, x1 - x0), h: Math.max(0, y1 - y0) };
  },

  // 오브젝트 풀 요소 서명(재사용 판정 — 렌더 기하 영향 전량 포착). draw() 와 테스트가 공유.
  //   node: type+combo+style+states (§18.8 m1: type 포함 — circle/rect 기하 갈림). edge: 끝점+style.
  //   combo: style+bbox(자식 파생). 좌표는 0.1px 양자화(FP 노이즈 무불필요 recreate 방지, m2 일관).
  // graph-expand-perf(2026-08-13): **위치를 뺀** 노드 서명. `_drawNode` 는 x/y 를 컨테이너 `position.set` 에만
  //   쓰고 나머지 자식(Graphics·라벨·역할 배지·상태 오버레이)은 전부 로컬 좌표계라, **이동만 한 노드는 파기·
  //   재생성할 이유가 없다** — `position.set` 한 번이면 화면이 같다. 종전 `nodeSig` 는 style 을 통째로
  //   JSON.stringify 해 x/y 가 섞였고, 그래서 컬럼 하나를 펼쳐 masonry 가 재균형될 때마다 **이동한 형제
  //   수백 개가 전부 destroy→re-create** 됐다(라이브 실측: 693 노드 스키마에서 1테이블 펼침 = made 538 ·
  //   labelsCreated 524 · drawMs 207ms — draw 비용의 지배항이 라벨 재생성이었다).
  //   `for...in` 은 JSON.stringify 와 같은 삽입 순서를 따르므로 서명 결정론은 그대로다(같은 build 코드가
  //   같은 순서로 style 을 만든다). x/y 만 제외해 "모양이 같은가" 만 묻는다.
  nodeShapeSig(n) {
    const s = n.style || {};
    let body = "";
    for (const k in s) { if (k === "x" || k === "y") continue; body += k + ":" + JSON.stringify(s[k]) + ","; }
    return "N|" + (n.type || "") + "|" + (n.combo || "") + "|{" + body + "}|" + ((n.states || []).join(","));
  },
  // combo 는 bbox 의 **크기**만 기하에 들어가고(roundRect 0,0,w,h) x/y 는 컨테이너 위치다 — 노드와 동형 분리.
  comboShapeSig(c, bb) { return "C|" + JSON.stringify(c.style || {}) + "|" + bb.w.toFixed(1) + "," + bb.h.toFixed(1); },
  edgeSig(e, a, b) { return "E|" + e.source + "|" + e.target + "|" + JSON.stringify(e.style || {}) + "|" + a[0].toFixed(1) + "," + a[1].toFixed(1) + "," + b[0].toFixed(1) + "," + b[1].toFixed(1); },

  // graph-edge-drag-perf: 인접 인덱스(node id → incident edge[]). 드래그 재그림이 이동 노드의 인접 엣지만
  //   O(incident) 로 조회(전량 O(E) 스캔 제거). 토폴로지(source/target)만 의존. 자기루프(source===target)는
  //   1회만 등재. **미해소 끝점 엣지도 포함**(완전) — 소비측(_refreshIncidentEdges)이 pos null 이면 skip.
  buildEdgeIndex(edges) {
    const idx = new Map();
    const add = (k, e) => { let arr = idx.get(k); if (!arr) { arr = []; idx.set(k, arr); } arr.push(e); };
    for (const e of (edges || [])) { add(e.source, e); if (e.target !== e.source) add(e.target, e); }
    return idx;
  },
  edgeId(e) { return e.id != null ? e.id : ("__e:" + e.source + ">" + e.target); },

  // §80 BitmapText tint: "#rgb"/"#rrggbb"/number → {tint, valid}. 비-hex(rgb()/named)면 valid=false(Text 폴백 유도).
  hexToTint(hex) {
    if (typeof hex === "number") return { tint: hex, valid: true };
    const s = String(hex).trim();
    if (!/^#?[0-9a-fA-F]{3}$|^#?[0-9a-fA-F]{6}$/.test(s)) return { tint: 0xffffff, valid: false };
    const h = s.replace("#", ""); const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
    return { tint: parseInt(full, 16), valid: true };
  },

  // graph-emoji-color(fix): 문자열에 색 이모지(pictographic)가 포함됐는지. 포함 시 BitmapText 를 피하고 PIXI.Text 로
  //   강등시키기 위한 판정. 이유 — BitmapText 는 dynamic font atlas 에 glyph 를 **alpha 커버리지 단색 마스크**로
  //   래스터화한 뒤 tint 를 곱하므로 색 이모지의 색 채널이 소실돼 labelFill 색(어두운 역할=#161b22 → 검은색)의
  //   **단색 실루엣**으로만 렌더된다(PixiJS BitmapText 원천 한계). Text(canvas)는 브라우저 색 이모지 폰트로 네이티브
  //   렌더하므로 테이블 역할 아이콘(📊/👤/💳/📜/🔗/⚙️/📘/📦·🗂)이 제 색으로 보인다. 범위: 주요 pictographic 블록
  //   + Misc Symbols/Dingbats(2600-27BF, ⚙ 포함) + VS16(FE0F, ⚙️ 결합)·ZWJ(200D, 결합 이모지). `−`(2212)·`ƒ`(0192)
  //   같은 텍스트 글리프는 비-매칭(불필요한 Text 강등 회피 = BitmapText draw-call 최적화 보존).
  hasEmoji(text) {
    if (text == null) return false;
    return /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2300}-\u{23FF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}]/u.test(String(text));
  },

  // graph-role-badge(2026-07-28): 테이블 노드 좌측 역할 배지 타일의 **노드-로컬 중심 x**. 노드 좌변에서
  //   BADGE_PAD 만큼 띄운 뒤 타일 반폭. 노드 본체(`_drawNode`)와 hover 확장 카드(`_showLabelExpand`)가
  //   **같은 함수를 공유**해야 hover 순간 배지가 1px 도 움직이지 않는다(라벨 앵커 textLeft 와 동일 원칙).
  roleBadgeCX(w, size) { return -w / 2 + 2 + (size > 0 ? size : 0) / 2; },

  // graph-label-hover-expand: 라벨이 ellipsis 로 잘린 칩의 **hover 확장 카드** 기하(순수 — node vm 테스트 대상).
  //   문제: 테이블/루틴/카드 칩은 폭 고정(TW=150 등)이라 긴 이름이 `labelMaxWidth` 에서 잘리고(_ellipsize),
  //   사용자가 전체 이름을 알려면 상세 패널까지 가야 했다. hover 시 그 칩만 부드럽게 넓어지며 나머지 글자를
  //   드러낸다.
  //   설계 제약(사용자 요구):
  //     ① **다른 노드 위치 불변** — 확장은 scene 모델(node.style.size)을 건드리지 않고 별도 오버레이 레이어에
  //        그린다. 따라서 masonry/shelf-pack 재배치·combo bbox·hit-grid·미니맵 전부 무영향(reflow 0).
  //     ② **좌변 고정 + 우측 확장**(사용자 정정 2026-07-28 — 이전 중앙 대칭에서 변경) — 원 칩의 왼쪽 모서리를
  //        앵커로 고정하고 오른쪽 모서리만 밀어낸다. t=0 에서 원 칩과 픽셀 동일(팝 없음)인 성질은 그대로이고,
  //        이미 읽고 있던 앞글자가 제자리에 머문 채 뒷글자만 오른쪽에서 드러나 읽기 방향과 정합한다.
  //     ③ **z-order** — 오버레이 레이어가 최상단이라 확장분이 이웃 칩 아래로 숨지 않는다(어댑터 배선 참조).
  //   반환 null = 확장 불필요(라벨/상한 없음 · 이미 전부 보임 · 이득 < minGain).
  //   대상은 `labelPlacement:"center"` rect 칩(테이블·루틴·스키마 카드·용어·그룹/카테고리 헤더) — 즉 "노드 **안**
  //   에 든 명칭". 컬럼 circle 의 우측 외부 라벨(placement:"right")은 노드 밖 텍스트라 본 확장 대상이 아니다.
  hoverExpandGeom(n, fullW, opts) {
    const s = (n && n.style) || {}, o = opts || {};
    if (n && n.__combo) return null;                                  // combo(스키마 배경) 라벨은 상한 없음 — 잘리지 않는다
    if (!s.labelText || !s.labelMaxWidth || !(fullW > 0)) return null;
    if ((s.labelPlacement || "center") !== "center") return null;
    if (!Array.isArray(s.size)) return null;                          // rect 칩만(circle=컬럼 점, 라벨이 노드 밖)
    if (fullW <= s.labelMaxWidth + 0.5) return null;                  // 이미 전부 보임
    const cap = o.maxWidth || 460, minGain = o.minGain == null ? 2 : o.minGain;
    const w0 = s.size[0], h = s.size[1];
    const pad = Math.max(8, w0 - s.labelMaxWidth);                    // 원 칩의 좌우 여백을 확장 카드도 보존
    const w1 = Math.min(cap, Math.max(w0, Math.ceil(fullW + pad)));
    if (w1 - w0 < minGain) return null;
    // 텍스트 가용폭은 카드 박스 폭과 **분리**해 보간한다: inner0 = 원 노드가 실제로 쓰던 한계(labelMaxWidth),
    //   inner1 = 확장 종단의 안쪽 폭. 루틴 칩처럼 labelMaxWidth(176)가 칩 폭(150)보다 큰 스타일이 있어(칩 밖으로
    //   라벨이 삐져나오는 기존 동작), 박스폭-pad 로 계산하면 t=0 에 원래 보이던 글자가 오히려 줄어드는 역-팝이
    //   난다(codex review P2). inner0 을 원 한계로 고정하면 t=0 이 항상 픽셀 동일.
    // graph-label-hover-anchor(사용자 정정 2026-07-28): 확장 기준점은 **좌변 고정 + 우측으로만 성장**.
    //   `left` 가 그 앵커(원 칩의 좌변, world x). 카드 중심은 폭에 따라 우측으로 밀린다(hoverCardCenterX).
    //   중앙 대칭이던 이전 동작 대비: 이미 읽고 있던 앞부분 글자가 제자리에 머물고 뒷글자만 오른쪽에서
    //   드러나므로 시선이 따라가기 쉽다(읽기 방향 정합).
    return { x: s.x, y: s.y, left: s.x - w0 / 2, w0, w1, h, pad, radius: s.radius || 0, capped: w1 >= cap,
      inner0: s.labelMaxWidth, inner1: w1 - pad };
  },

  // 폭 w 인 확장 카드의 중심 world x — 좌변(g.left)을 고정한 결과값. `left` 부재(구 geom)면 중앙 고정 폴백.
  hoverCardCenterX(g, w) {
    if (!g) return 0;
    if (g.left == null) return g.x;
    return g.left + (w > 0 ? w : g.w0) / 2;
  },

  // 라벨의 카드-로컬 x (anchor 0 = 좌측 정렬). **원 노드가 렌더하던 라벨의 절대 좌측(textLeft)을 그대로
  //   유지**하도록 카드 중심 이동분만큼 상쇄한다 → 확장 내내 앞글자가 1px 도 움직이지 않고 뒷글자만 오른쪽에서
  //   드러난다. textLeft 를 "칩 좌변 + pad/2" 로 계산하지 않는 이유: 루틴 칩은 `labelMaxWidth`(176)가 칩
  //   폭(150)보다 커서 원 라벨이 이미 칩 밖으로 넘쳐 있다 — 그 경우 pad 기준으로 잡으면 hover 순간 라벨이
  //   ~17px 튄다(codex review P2). 실제 렌더 폭에서 역산한 textLeft 만이 t=0 픽셀 동일을 보장한다.
  hoverTextOffsetX(g, w, textLeft) { return textLeft - this.hoverCardCenterX(g, w); },

  // graph-role-badge(2026-07-28, codex review P2): 확장 카드 안 역할 배지의 **카드-로컬 x 오프셋**.
  //   `hoverTextOffsetX` 와 **동형**이어야 한다 — 둘 다 unclamped 중심(hoverCardCenterX) 기준으로 계산하고
  //   카드 컨테이너의 실제 위치(`_clampCardX`)에 얹힌다. 이유: 좌측 가장자리 칩이 확장될 때 카드가 뷰포트
  //   안으로 밀리는데(클램프), world 좌표에 배지를 고정하면 카드 배경만 이동해 배지가 카드 밖으로 삐져
  //   나가거나 잘린다. 카드-로컬로 잡으면 라벨과 같이 카드에 실려 이동하고, 클램프가 없는 통상 경로에서는
  //   world 가 원 노드 위치와 정확히 일치해 t=0 픽셀 동일이 그대로 보존된다.
  hoverBadgeOffsetX(g, w) { return (g ? g.x : 0) - this.hoverCardCenterX(g, w); },

  // graph-label-hover-expand: 현재 폭 w 의 확장 카드 사각형 안에 model 점이 있는가.
  //   **필요한 이유(codex review P1)**: 카드가 넓어지면 드러난 좌우 영역은 원 노드 bbox 밖이라 hit-grid 가
  //   null 을 돌려준다 → 사용자가 이름 뒷부분을 보려고 커서를 그쪽으로 옮기는 순간 카드가 닫히는 깜빡임.
  //   보이는 카드 자체를 hover 유지 영역으로 삼아(WYSIWYG — _pick 층서 철학과 동일) 이를 없앤다.
  hoverCardHit(mx, my, g, w, cx) {
    if (!g) return false;
    const hw = (w > 0 ? w : g.w0) / 2, hh = g.h / 2, x = (cx == null ? g.x : cx);
    return mx >= x - hw && mx <= x + hw && my >= g.y - hh && my <= g.y + hh;
  },

  // graph-label-hover-expand: 확장 카드 중심의 화면 x 를 뷰포트 안으로 보정(codex review P2).
  //   가장자리 칩은 카드가 캔버스 밖으로 나가 잘려 "확장했는데 여전히 안 보이는" 상태가 된다. 세로·중심 y 는
  //   원 칩 그대로 두고 **가로만** 민다. 카드가 뷰포트보다 넓으면 좌측 정렬(이름 앞부분 판독 우선).
  //   rightMax(선택) = 우측 가용 경계(screen x). 미니맵은 app.stage 자식이라 world 위에 그려지므로, 카드가
  //   미니맵과 세로로 겹치면 그 왼쪽 변을 우측 경계로 넘겨 카드가 미니맵 밑에 깔리지 않게 한다.
  clampCardCenterX(sx, wScreen, vw, pad, rightMax) {
    const p = pad == null ? 6 : pad, half = wScreen / 2;
    const lo = p, hi = (rightMax == null ? vw : rightMax) - p;
    if (wScreen >= hi - lo) return lo + half;   // 가용 폭보다 넓음 → 좌측 정렬(이름 앞부분 판독 우선)
    if (sx - half < lo) return lo + half;
    if (sx + half > hi) return hi - half;
    return sx;
  },

  // 두 built scene diff (오브젝트 풀 재사용 판정). id 기준 add/remove/keep.
  diffScene(prevIds, built) {
    const next = new Set(), add = [], keep = [];
    const all = [].concat(built.combos || [], built.nodes || [], built.edges || []);
    for (const el of all) { next.add(el.id); (prevIds.has(el.id) ? keep : add).push(el.id); }
    const remove = [];
    for (const id of prevIds) if (!next.has(id)) remove.push(id);
    return { add, keep, remove, nextIds: next };
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Pixi 의존 어댑터 (브라우저) — win-browser 실증
// ─────────────────────────────────────────────────────────────────────────────

const DBLCLICK_MS = 320;
// graph-label-hover-expand: 잘린 라벨 hover 확장 카드 파라미터.
//   DELAY = hover-intent(노드 위를 빠르게 스쳐 지나갈 땐 뜨지 않게) · MS = 확장 애니 지속 · MAXW = 카드 폭 상한.
//   MAXW 단위는 **model(world) px** 이다 — 화면 px 가 아니다(codex review P2 지적 반영한 의도 명시). 카드는
//   world 자식이라 줌과 함께 스케일되므로, 상한을 화면 px 로 잡으면 같은 라벨이 줌마다 다르게 잘려(고배율에서
//   오히려 안 보임) 확장의 목적을 잃는다. 460 = 테이블 칩(TW=150) 약 3배 — "그래프 대비" 상대 크기를 고정한다.
const HOVER_EXPAND_DELAY_MS = 90;
const HOVER_EXPAND_MS = 160;
const HOVER_COLLAPSE_MS = 110;   // 이탈 축소 — 확장보다 짧게(되돌아감은 빠르게 느껴지는 게 자연스럽다)
const HOVER_EXPAND_MAXW = 460;

// graph-move-anim(사용자 요청 2026-08-13): 재배치 이동 트윈 파라미터.
//   MS = 지속시간. 360ms 는 "이동을 눈으로 좇을 수 있는" 하한(~250ms)과 "기다린다고 느끼는" 상한(~500ms)
//     사이다 — 펼침은 사용자가 방금 클릭한 결과라 지연으로 읽히면 안 된다.
//   CAP = 한 번에 트윈할 노드 수 상한. 초과분은 즉시 최종 위치(기존 동작) + `skipped` 로 관측에 남긴다.
//   VIS_MARGIN = 가시 rect 판정 마진(화면 px). 화면 밖에서 들어오는 노드도 도입부가 보이도록 여유를 준다.
//   MIN_OVERLAP = 직전 씬과 겹치는 노드 비율 하한. 미만이면 '재배치'가 아니라 '씬 교체'라 트윈하지 않는다.
//   EDGE_CAP = 매 프레임 따라 그려야 하는 관계선 수 상한. 노드 수가 아니라 **관계선 수**가 프레임
//     비용의 지배항이라(허브 노드 하나가 수백 선을 끈다) 노드 상한만으로는 비용이 안 잡힌다.
//     초과하면 트윈 자체를 포기한다 — 끊기는 애니메이션은 없느니만 못하다(관측에 사유를 남긴다).
const MOVE_TWEEN_MS = 360;
const MOVE_TWEEN_CAP = 600;
const MOVE_TWEEN_EDGE_CAP = 1500;
const MOVE_TWEEN_VIS_MARGIN = 240;
const MOVE_TWEEN_MIN_OVERLAP = 0.3;

// graph-perf: 렌더 비용 관측 지점(graph-state.js `_metaPerf` 와 같은 전역을 공유한다 — 어댑터는
//   graph-state 를 import 하지 않는 엔진-중립 모듈이라 로컬로 lazy-init 한다). 계측 전용·fail-soft.
function _pxPerf() {
  const w = (typeof window !== "undefined") ? window : null;
  if (!w) return { label: {}, render: {} };
  if (!w.__META_GRAPH_PERF) w.__META_GRAPH_PERF = { label: {}, render: {} };
  return w.__META_GRAPH_PERF;
}
const _pxNow = () => ((typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now());

export class PixiGraphAdapter {
  constructor(cfg) {
    this.cfg = cfg || {};
    this.P = (typeof window !== "undefined" && window.PIXI) || null;
    this.zoomRange = this.cfg.zoomRange || [0.05, 4];
    this._handlers = new Map();        // event name → [fn]
    this._nodeState = (this.cfg.node && this.cfg.node.state) || {};
    this._built = { nodes: [], edges: [], combos: [] };
    this._objs = new Map();            // id → PIXI.Container/Graphics (오브젝트 풀)
    this._hitGrid = null;
    // graph-move-anim: 재배치 이동 트윈 상태. _prevPos=직전 씬 좌표 스냅샷(setData 가 캡처, draw 가 소비),
    //   _tweenPos=트윈 중에만 유효한 화면좌표 오버레이(관계선 끝점), _moveTween=세대 토큰.
    this._userCamSeq = 0;       // 사용자 카메라 조작(팬·줌·미니맵) 세대 — keep-in-view 추종의 중단 신호
    this._prevPos = null;
    this._tweenPos = null;
    this._tweenMovers = null;   // 트윈 중 노드 [{n, at}] — hit-test 선형 스캔 대상
    this._moveTween = null;
    this._labelRes = Math.min((typeof window !== "undefined" ? (window.devicePixelRatio || 1) : 1) * 2, 4);
    // graph-label-hover-expand: hover 확장 상태. _hoverId=현재 확장 대상 노드 id(변화 시에만 재구성),
    //   _labelWCache=전체 라벨 폭 측정 캐시(잘림 판정·목표폭 산출 — 폰트 파라미터+텍스트가 같으면 폭 동일).
    this._hoverId = null;
    this._hoverTimer = 0;
    this._hoverProbeRaf = 0;
    this._hoverPt = null;
    this._hoverCard = null;   // 현재 확장 카드 {c, paint, g, a0, w, raf}
    this._outCard = null;     // 축소(이탈) 진행 중 카드 — 동시 1장만
    this._labelWCache = new Map();
    this._labelStat = { created: 0, bitmap: 0, text: 0, ms: 0 };   // graph-perf: draw 단위 라벨 생성 비용
    this._lastTap = 0;
    this.container = this.cfg.container || null;
    this.app = null;
    this.world = null;                 // 카메라 = world transform
    this._ready = this._init();
  }

  async _init() {
    if (!this.P) return;               // 미배선/비브라우저 — no-op (import 부작용 0)
    this.app = new this.P.Application();
    await this.app.init({ background: this.cfg.background || "#f6f8fb", antialias: true,
      resolution: (window.devicePixelRatio || 1), autoDensity: true,
      preference: this.cfg.renderer === "webgpu" ? "webgpu" : "webgl",
      // render-on-demand: 정적 그래프는 idle 시 GPU 를 돌릴 필요가 없다(게임 아님). autoStart:false 로 ticker
      //   자동 렌더를 끄고, 변경(draw/카메라/상태/드래그) 시에만 명시 _render() 한다 — idle GPU 0 + rAF-throttle
      //   무관한 즉시 페인트(headless/CDP 스크린샷도 안정). preserveDrawingBuffer: present 후 버퍼 클리어로 인한
      //   스크린샷/미니맵 RenderTexture 검은 캡처 방지.
      autoStart: false, sharedTicker: false, preserveDrawingBuffer: true });
    try { this.app.ticker.stop(); } catch (_) {}
    if (this.container) { this.container.appendChild(this.app.canvas); this._resizeToContainer(); }
    this.world = new this.P.Container(); this.world.sortableChildren = true;
    this.app.stage.addChild(this.world);
    // detail-hover-fx: 상세 패널 하위 항목 hover 강조용 world-space 오버레이(팬/줌 자동 추종). 비커밋 —
    //   커밋 선택(setElementState)·전체 rebuild(setScene/draw) 상태와 독립. zIndex 최상단·이벤트 비참여
    //   (어댑터는 raw canvas pointer 로 hit-test 하므로 hit 방해 0). draw() 는 _objs 만 정리하고 이 레이어는 보존.
    this._hoverLayer = new this.P.Container(); this._hoverLayer.zIndex = 99999; this._hoverLayer.eventMode = "none";
    this.world.addChild(this._hoverLayer);
    // graph-label-hover-expand: 잘린 라벨 확장 카드 전용 레이어. detail-hover-fx 강조(z=99999) **바로 아래**,
    //   그러나 전 노드·엣지·combo 보다 위 → 확장분이 이웃 칩에 가리지 않는다(z-order 요구). world 자식이라
    //   팬/줌 자동 추종. eventMode="none" — 어댑터는 raw canvas pointer + 자체 hit-grid 로 picking 하므로
    //   오버레이가 클릭/우클릭/드래그를 가로채지 않는다. _objs 밖이라 draw() 의 diff 정리 대상도 아니다.
    this._labelHoverLayer = new this.P.Container(); this._labelHoverLayer.zIndex = 99998; this._labelHoverLayer.eventMode = "none";
    this.world.addChild(this._labelHoverLayer);
    this._initMinimap();
    this._bindPointer();
    // autoResize(gap #15): 컨테이너/창 리사이즈 자동 추종.
    if (this.cfg.autoResize !== false && typeof ResizeObserver !== "undefined" && this.container) {
      this._ro = new ResizeObserver(() => this._resizeToContainer()); this._ro.observe(this.container);
    }
  }

  // 미니맵: app.stage 오버레이(팬/줌 무관, 우하단). 전체 노드를 축소 렌더 + 뷰포트 사각형.
  //   G6 minimap 플러그인 대체 — getPluginInstance("minimap") 호환 스텁 노출(graph-core 재사용 최적화는
  //   pixi 분기에서 no-op). 어댑터가 자체 관리하므로 §74/§77 재복제 게이트 불필요.
  _initMinimap() {
    if (!this.P || this.cfg.minimap === false) { this._minimap = null; return; }
    const P = this.P, sz = this.cfg.minimapSize || [168, 112];
    const c = new P.Container(); c.zIndex = 10000;
    const bg = new P.Graphics(); bg.roundRect(0, 0, sz[0], sz[1], 6).fill({ color: "#ffffff", alpha: 0.92 }).stroke({ color: "#d5dbe5", width: 1 });
    const content = new P.Graphics(), mask = new P.Graphics();
    mask.rect(0, 0, sz[0], sz[1]).fill(0xffffff); content.mask = mask;
    const vp = new P.Graphics();
    c.addChild(bg, content, mask, vp);
    this.app.stage.addChild(c);
    this._minimap = { c, content, vp, mask, size: sz, __reusePatched: true, __fullImageSig: null, _geomSig: null,
      renderMinimap: () => this._renderMinimap(), setShapes: () => {} };
    this._positionMinimap();
  }
  _positionMinimap() {
    if (!this._minimap || !this.app) return;
    const [vw, vh] = this.getSize();
    this._minimap.c.position.set(vw - this._minimap.size[0] - 10, vh - this._minimap.size[1] - 10);
  }
  _renderMinimap() {
    if (!this._minimap || !this.world) return;
    const mm = this._minimap;
    const b = PixiAdapterPure.contentBounds(this._built);
    const pr = PixiAdapterPure.minimapProjection(b, mm.size, 6);
    if (!pr) { mm.content.clear(); mm._proj = null; return; }   // m4: 빈 콘텐츠 시 stale proj 제거(엉뚱한 팬 방지)
    mm._proj = pr; const s = pr.s, ox = pr.ox, oy = pr.oy;
    const g = mm.content; g.clear();
    // 노드를 미니맵 스케일 점/사각형으로 (combo 배경은 옅게)
    for (const cb of (this._built.combos || [])) { const bb = PixiAdapterPure.comboBBox(cb.id, this._built.nodes, (cb.style || {}).padding); if (!bb) continue;
      g.rect(ox + (bb.x - b.x) * s, oy + (bb.y - b.y) * s, bb.w * s, bb.h * s).fill({ color: "#3f4b8c", alpha: 0.06 }); }
    for (const n of (this._built.nodes || [])) { const bb = PixiAdapterPure.nodeBBox(n);
      g.rect(ox + (bb.x - b.x) * s, oy + (bb.y - b.y) * s, Math.max(1, bb.w * s), Math.max(1, bb.h * s)).fill({ color: (n.style && n.style.fill) || "#0f7d8c", alpha: 0.85 }); }
    this._renderMinimapViewport();
  }
  _renderMinimapViewport() {
    if (!this._minimap || !this._minimap._proj || !this.app) return;
    const mm = this._minimap, pr = mm._proj, cam = this._cam, [vw, vh] = this.getSize(), [mw, mh] = mm.size;
    // 화면 뷰포트의 model 사각형 → 미니맵 좌표
    const m0 = PixiAdapterPure.screenToModel(0, 0, cam), m1 = PixiAdapterPure.screenToModel(vw, vh, cam);
    // 이슈#2: 극단 줌아웃 시 뷰포트가 콘텐츠보다 커 사각형이 미니맵 박스를 벗어난다 → 경계 클램프(순수 함수).
    const r = PixiAdapterPure.minimapViewportRect(m0, m1, pr, mm.size);
    mm.vp.clear();
    mm.vp.rect(r.x, r.y, r.w, r.h).stroke({ color: "#2563eb", width: 1.5, alpha: 0.9 });
  }

  _resizeToContainer() {
    if (!this.container || !this.app) return;
    const w = this.container.clientWidth || 800, h = this.container.clientHeight || 600;
    // 크기 무변화 시 skip — ResizeObserver 루프(resize→layout→observe) 경고 방지.
    if (this._lastW === w && this._lastH === h) return;
    this._lastW = w; this._lastH = h;
    this.app.renderer.resize(w, h);
    this._positionMinimap();
    this._repaintHoverCard();   // graph-label-hover-expand: 뷰포트 폭이 바뀌면 카드 클램프 재계산(codex review P2)
    this._render();
  }

  // 활성 확장 카드를 현재 카메라·뷰포트 기준으로 다시 그린다(폭 유지). 카메라·리사이즈 변경점 공용.
  _repaintHoverCard() { if (this._hoverCard) { try { this._hoverCard.paint(this._hoverCard.w); } catch (_) {} } }
  // 카메라가 바뀌면 커서 아래 대상이 달라질 수 있다 — wheel 뿐 아니라 focusElement/zoomTo/translateBy(더블클릭
  //   앵커 팬 등) 도 포함해 마지막 포인터 위치로 재판정한다(codex review P2). 버튼 눌림 중(팬/드래그)엔
  //   _probeHover 가 스스로 무동작이므로 매 팬 프레임 비용은 0.
  _revalidateHover() {
    const p = this._hoverPt;
    if (p && !this._ptrDown) this._probeHover(p.x, p.y);
    this._repaintHoverCard();
  }

  // render-on-demand: 변경 지점마다 명시 렌더(ticker autoStart:false). rAF-throttle 무관 즉시 페인트.
  _render() { if (this.app && this.app.renderer && this.world) { try { this.app.renderer.render(this.app.stage); } catch (_) {} } }
  // ── 카메라 상태 헬퍼 ──
  get _cam() { return this.world ? { zoom: this.world.scale.x, x: this.world.position.x, y: this.world.position.y } : { zoom: 1, x: 0, y: 0 }; }
  // graph-label-hover-expand: 카메라가 바뀌면 확장 카드의 뷰포트 클램프도 다시 계산해야 한다(줌 중 카드가
  //   화면 밖으로 밀리는 것 방지). 팬/드래그는 개시 시점에 hover 가 해제되므로 실제 발동은 wheel 줌 경로 한정.
  _applyCam(c) { if (!this.world) return; this.world.scale.set(c.zoom); this.world.position.set(c.x, c.y); this._renderMinimapViewport();
    this._syncEdgeZoom();   // §85: screen-space 굵기 유지 — 줌이 바뀌면 엣지 기하를 다시 굽는다
    this._revalidateHover(); this._render(); this._emitTransform(); }
  // §85: 굵기는 페인트 시점의 zoom 으로 model 좌표에 **bake** 되므로, world scale 만 바뀌면 화면 두께가
  //   다시 줌 비례로 흐른다 — 줌 변화가 유의할 때만 엣지를 재페인트해 화면 두께를 되돌린다.
  //   임계(로그 0.22 ≈ 25%)를 둔 이유: 휠 한 틱마다 전량 재페인트하면 대형 스코프에서 프레임이 무너진다.
  //   그 사이 구간의 두께 오차는 최대 ±12% 로 육안 식별이 어렵다. 재페인트는 rAF 로 코얼레싱한다.
  _syncEdgeZoom() {
    const z = this._cam.zoom, last = this._edgePaintZoom;
    if (last && Math.abs(Math.log(z / last)) < 0.22) return;
    this._edgePaintZoom = z;
    if (this._edgeZoomRaf) return;
    const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
    if (!raf) { this._repaintAllEdges(); return; }
    this._edgeZoomRaf = raf(() => { this._edgeZoomRaf = 0; this._repaintAllEdges(); this._render(); });
  }
  // 전 엣지 in-place 재페인트(Graphics 재사용 — destroy/recreate 없음). 좌표는 불변이라 서명도 그대로다.
  _repaintAllEdges() {
    if (!this.world) return;
    for (const e of (this._built.edges || [])) {
      const eid = PixiAdapterPure.edgeId(e);
      const g = this._objs.get(eid);
      if (!g || typeof g.clear !== "function") continue;
      const a = this._resolvePos(e.source), b = this._resolvePos(e.target);
      if (!a || !b) continue;
      this._paintEdge(g, e, a, b);
    }
  }
  getSize() { return this.app ? [this.app.renderer.width / this.app.renderer.resolution, this.app.renderer.height / this.app.renderer.resolution] : [0, 0]; }
  getZoom() { return this._cam.zoom; }
  zoomTo(z, opts) { const c = this._cam; c.zoom = PixiAdapterPure.clampZoom(z, this.zoomRange); this._applyCam(c); }
  zoomBy(f) { const c = this._cam; c.zoom = PixiAdapterPure.clampZoom(c.zoom * f, this.zoomRange); this._applyCam(c); }
  translateBy(d) { const c = this._cam; c.x += d[0]; c.y += d[1]; this._applyCam(c); }
  // ⚠ G6 명명(gap #2): getCanvasByViewport(screen)→model, getViewportByCanvas(model)→screen. graph-core 용법과 일치.
  getCanvasByViewport(s) { return PixiAdapterPure.screenToModel(s[0], s[1], this._cam); }
  getViewportByCanvas(m) { return PixiAdapterPure.modelToScreen(m[0], m[1], this._cam); }

  // 위치: 노드 우선, combo/SC:/GB:/GH:/CAT: 등 장식은 bbox 중심(gap #9).
  getElementPosition(id) {
    const n = this._built.nodes.find(x => x.id === id);
    if (n) return [n.style.x, n.style.y];
    const b = this._boundsOf(id);
    return b ? [b.x + b.width / 2, b.y + b.height / 2] : null;
  }
  _boundsOf(id) {
    const n = this._built.nodes.find(x => x.id === id);
    // graph-move-anim: 트윈 중이면 **보이는 위치**의 bbox 를 준다. 카메라 보정(`_metaGraphKeepInView`)과
    //   중앙 focus(`_metaGraphAnimateFocus`)가 이 값을 읽는데, 최종 좌표를 주면 노드가 아직 반대편에
    //   그려져 있는 동안 카메라가 목적지로 가버려 **애니메이션 내내 그 노드가 화면 밖**이 된다 —
    //   "선택한 노드를 잃지 않게" 라는 요구 자체를 뒤집는다(codex review 4차 P2). 두 카메라 루프 모두
    //   매 프레임 재조회하는 follow 구조라, 움직이는 목표를 그대로 따라가 안착 시점에 함께 수렴한다.
    if (n) {
      const p = this._tweenPos && this._tweenPos.get(id);
      const b = PixiAdapterPure.nodeBBox(n, p || null);
      return { x: b.x, y: b.y, width: b.w, height: b.h };
    }
    const c = this._built.combos.find(x => x.id === id);
    if (c) { const b = PixiAdapterPure.comboBBox(c.id, this._built.nodes, (c.style || {}).padding); if (b) return { x: b.x, y: b.y, width: b.w, height: b.h }; }
    return null;
  }
  // G6 반환형 superset: graph-core(_metaGraphAnimateFocus)는 b.min[0..1]/b.max[0..1] 을 읽는다(gap #1).
  getElementRenderBounds(id) {
    const b = this._boundsOf(id);
    if (!b) return null;
    return { x: b.x, y: b.y, width: b.width, height: b.height, min: [b.x, b.y], max: [b.x + b.width, b.y + b.height], center: [b.x + b.width / 2, b.y + b.height / 2] };
  }

  fitView(opts) {
    const [vw, vh] = this.getSize();
    const b = PixiAdapterPure.contentBounds(this._built);
    const cam = PixiAdapterPure.fitCamera(b, { w: vw, h: vh },
      { pad: (opts && opts.padding) || 80, range: this.zoomRange, minReadZoom: (opts && opts.minReadZoom) || 0 });
    this._applyCam(cam);
  }

  // 앵커-중심 포커스 (더블클릭 카메라 애니팬 — ADR-008/011). opts.duration 있으면 rAF tween.
  focusElement(id, opts) {
    const rb = this.getElementRenderBounds(id); if (!rb) return;
    const [vw, vh] = this.getSize(); const cam = this._cam;
    const cx = rb.x + rb.width / 2, cy = rb.y + rb.height / 2;
    const target = { zoom: cam.zoom, x: vw / 2 - cx * cam.zoom, y: vh / 2 - cy * cam.zoom };
    if (!opts || !opts.duration || !this.P) { this._applyCam(target); return; }
    this._tween(cam, target, opts.duration);
  }
  _tween(from, to, dur) {
    if (this._tweenRaf) cancelAnimationFrame(this._tweenRaf);
    const t0 = (typeof performance !== "undefined" ? performance.now() : 0);
    const ease = t => 1 - Math.pow(1 - t, 3);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = ease(k);
      this._applyCam({ zoom: from.zoom + (to.zoom - from.zoom) * e, x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e });
      if (k < 1) this._tweenRaf = requestAnimationFrame(step);
    };
    this._tweenRaf = requestAnimationFrame(step);
  }

  // ── 이벤트 (G6 이벤트명 합성) ──
  on(name, fn) { if (!this._handlers.has(name)) this._handlers.set(name, []); this._handlers.get(name).push(fn); return this; }
  off(name, fn) { const a = this._handlers.get(name); if (a) this._handlers.set(name, a.filter(f => f !== fn)); return this; }
  _emit(name, payload) { const a = this._handlers.get(name); if (a) for (const f of a.slice()) { try { f(payload); } catch (_) {} } }
  _emitTransform() { this._emit("aftertransform", {}); }

  _bindPointer() {
    if (!this.app) return;
    const el = this.app.canvas; el.style.touchAction = "none";
    const MOVE_THRESH = 4;   // px — 이 이하 이동은 '정지=클릭', 초과는 드래그(팬 or 노드이동)
    let down = null, mode = null;   // mode: null|"pan"|"nodedrag"
    const scr = (e) => { const r = el.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const rawClient = (e) => ({ x: e.clientX, y: e.clientY });
    const midBtn = (btn) => btn === 1;
    // 노드 이동 대상인가(gap #7, _metaElementDragEnable 등가): 좌클릭 + 노드/장식(SC:/GB:/GH:/CAT:/CATH: 등)이되
    //   접기 컨트롤(GX:/CATX:)·접힌 카테고리 밴드는 클릭 전용 → graph-core 핸들러가 최종 판정(어댑터는 dragstart 만 발화).
    el.addEventListener("wheel", (e) => { e.preventDefault();
      // graph-label-hover-expand: 줌으로 커서 아래 노드가 바뀌어도 pointermove 는 안 온다 → 최신 커서 좌표를
      //   먼저 기록해 두면 _applyCam 의 _revalidateHover 가 그 좌표로 재판정한다.
      const s = scr(e); this._hoverPt = s;
      this._userCamSeq += 1;   // graph-move-anim: 사용자 줌도 카메라 소유권 회수
      this._applyCam(PixiAdapterPure.zoomAroundCursor(this._cam, e.deltaY < 0 ? 1.12 : 0.9, s, this.zoomRange)); }, { passive: false });
    const onDown = (e) => {
      this._ptrDown = true;   // graph-label-hover-expand: 버튼 눌림 동안 hover 판정 정지(아래 _probeHover 가드)
      const s = scr(e);
      // 이슈#3: 미니맵 영역 클릭/드래그 = 카메라 이동(그래프 드래그·선택보다 우선).
      // graph-label-hover-expand: 미니맵 조작 진입 시 확장 카드 정리 — 미니맵은 같은 캔버스라 pointerleave 가
      //   없고, 이후 move/up 경로가 전부 프로브를 건너뛰어 카드가 남는다(codex review P2).
      if (this._inMinimap(s.x, s.y)) { this._setLabelHover(null); down = { minimap: true }; mode = "minimap"; this._minimapPanTo(s.x, s.y); return; }
      const [mx, my] = PixiAdapterPure.screenToModel(s.x, s.y, this._cam);
      const hit = this._pick(mx, my);
      down = { sx: s.x, sy: s.y, button: e.button, ox: this._cam.x, oy: this._cam.y, hit, client: rawClient(e), mx, my, lmx: mx, lmy: my }; mode = null;
    };
    el.addEventListener("pointerdown", onDown);
    const onMove = (e) => {
      if (!down) return;
      if (down.minimap) { const s2 = scr(e); this._minimapPanTo(s2.x, s2.y); return; }   // 이슈#3: 미니맵 드래그 추종
      const s = scr(e), dx = s.x - down.sx, dy = s.y - down.sy;
      const [mx, my] = PixiAdapterPure.screenToModel(s.x, s.y, this._cam);
      if (!mode && Math.hypot(dx, dy) > MOVE_THRESH) {
        // 중간버튼=팬. 좌클릭+노드/장식=노드드래그(단 elementDragEnable predicate 통과 시 — M2: GX:/CATX:/접힌 밴드는 click 전용). 그 외=팬.
        const dragOk = down.hit && this._elementDragEnable(down.hit, e);
        if (midBtn(down.button) || !dragOk) mode = "pan";
        else { mode = "nodedrag"; this._emitDrag("dragstart", down.hit, e, s, mx, my); }
        this._setLabelHover(null);   // graph-label-hover-expand: 팬/드래그 개시 = hover 종료(확장 카드 잔상 방지)
      }
      if (mode === "pan") { this._userCamSeq += 1; this._applyCam({ zoom: this._cam.zoom, x: down.ox + dx, y: down.oy + dy }); }   // graph-move-anim: 사용자 팬 = 카메라 소유권 회수(진행 중 keep-in-view 추종 중단)
      else if (mode === "nodedrag") {
        // grabbed 요소를 델타만큼 이동(모델 좌표) — graph-core 핸들러가 종속을 translateElementTo 로 따라 옮긴다.
        const ddx = mx - down.lmx, ddy = my - down.lmy; down.lmx = mx; down.lmy = my;
        this._moveElement(down.hit.id, ddx, ddy);
        this._emitDrag("drag", down.hit, e, s, mx, my);
      }
    };
    window.addEventListener("pointermove", onMove);
    const up = (e) => {
      this._ptrDown = false;   // graph-label-hover-expand
      if (!down) return;
      if (down.minimap) { down = null; mode = null; return; }   // 이슈#3: 미니맵 드래그 종료(클릭 억제)
      const finished = mode, d = down, s = scr(e); down = null; mode = null;
      const [mx, my] = PixiAdapterPure.screenToModel(s.x, s.y, this._cam);
      if (finished === "pan") return;                       // 팬 → 클릭 억제
      if (finished === "nodedrag") { this._emitDrag("dragend", d.hit, e, s, mx, my); return; }
      // 정지 클릭/우클릭
      const hit = d.hit, kindEvt = hit ? (hit.__combo ? "combo" : "node") : "canvas";
      if (d.button === 2) {   // 우클릭: WYSIWYG _pick(=d.hit) — 보이는 대로. 노드(GB/GH/GX 컨텐츠 카테고리·CAT* 카테고리 포함)>combo(스키마)>cat-bg(카테고리)>edge>canvas
        // graph-ctxmenu(band-wins 철회 2026-07-15): 이전 _pickContext 는 밴드 위 스키마 클러스터를 카테고리 밴드로 승격했으나,
        //   사용자 정정("제품 카테고리 밴드↔컨텐츠 카테고리 착각") — 세 대상(제품 카테고리 밴드/스키마 클러스터/컨텐츠 카테고리=sim-group)은
        //   각자 자기 메뉴를 가져야 정합. 우클릭도 좌클릭·드래그와 동일한 _pick 결과(d.hit)를 쓴다 → 스키마 클러스터는 어디서나 스키마 메뉴.
        if (hit) { this._emit(kindEvt + ":contextmenu", this._payload(hit, s, mx, my, e)); return; }
        const eh = this._pickEdge(mx, my);
        if (eh) { this._emit("edge:contextmenu", this._payload(eh, s, mx, my, e)); return; }
        this._emit("canvas:contextmenu", this._payload(null, s, mx, my, e)); return;
      }
      const now = (typeof performance !== "undefined" ? performance.now() : 0);
      if (hit && this._lastTapId === hit.id && (now - this._lastTap) < DBLCLICK_MS) { this._lastTap = 0; this._lastTapId = null; this._emit((hit.__combo ? "combo" : "node") + ":dblclick", this._payload(hit, s, mx, my, e)); return; }
      this._lastTap = hit ? now : 0; this._lastTapId = hit ? hit.id : null;
      this._emit(kindEvt + ":click", this._payload(hit, s, mx, my, e));
    };
    window.addEventListener("pointerup", up);
    // pointercancel: 터치·펜에서 pointerup 없이 발화한다. 미처리 시 down/mode/_ptrDown 이 고착돼 다음
    //   pointerdown 까지 hover 판정이 죽고, 진행 중이던 nodedrag 는 dragend 를 못 받아 graph-core 의
    //   드래그 상태(_metaGraph._drag)·z 부스트가 남는다 → "놓은 자리에서 종료" 로 동치 처리한다(codex review P2).
    const cancel = (e) => {
      this._ptrDown = false;
      const d = down, m = mode; down = null; mode = null;
      this._cancelHoverProbe(true);   // 대기 중이던 프로브 rAF 도 함께 무효화(취소 후 카드 부활 차단)
      if (m === "nodedrag" && d && d.hit) this._emitDrag("dragend", d.hit, e, { x: d.sx, y: d.sy }, d.lmx, d.lmy);
    };
    window.addEventListener("pointercancel", cancel);
    el.addEventListener("contextmenu", (e) => e.preventDefault());
    // graph-label-hover-expand: hover 프로브(캔버스 한정 — window 가 아니라 el 에 건다). 드래그/팬 중(down)엔 억제.
    //   rAF 코얼레싱: 고폴링 마우스의 pointermove 폭주에도 프레임당 1회만 hit-test(§76 엣지 재그림과 동일 패턴).
    const onHoverMove = (e) => {
      if (down) return;
      this._hoverPt = scr(e);
      if (this._hoverProbeRaf) return;
      const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
      if (!raf) { const p = this._hoverPt; this._probeHover(p.x, p.y); return; }
      this._hoverProbeRaf = raf(() => { this._hoverProbeRaf = 0; const p = this._hoverPt; if (p) this._probeHover(p.x, p.y); });
    };
    el.addEventListener("pointermove", onHoverMove);
    // 이탈 시 **대기 중인 프로브까지** 무효화한다 — 그러지 않으면 leave 뒤 실행된 rAF 가 캔버스 안의 낡은
    //   좌표로 재판정해 커서가 떠난 뒤 카드가 되살아난다(codex review P1).
    el.addEventListener("pointerleave", () => this._cancelHoverProbe(true));
    this._winListeners = [["pointermove", onMove], ["pointerup", up], ["pointercancel", cancel]];   // m1: destroy 시 정리
  }

  // ── graph-label-hover-expand: 잘린 라벨 hover 확장 ──────────────────────────
  // 커서 아래 노드 판정. **tier1(실 요소 hit-grid)만** 쓴다 — _pick 의 tier2(hitTestCombo)는 combo 당
  //   자식 union bbox 를 재계산해 O(combos×nodes) 라 매 pointermove 에 돌릴 수 없다(클릭 1회는 무방).
  //   combo/cat-bg 는 애초 확장 대상도 아니므로(hoverExpandGeom 이 거른다) 기능 손실 0.
  _probeHover(sx, sy) {
    // 버튼 눌림 중(클릭/팬/노드드래그)엔 판정하지 않는다 — pointerdown **직전**에 예약된 rAF 프로브가 뒤늦게
    //   실행되면 드래그 중 옛 좌표로 카드를 띄워, 노드가 이동한 뒤 제자리에 남는 유령 카드가 된다(codex review P2).
    if (this._ptrDown) return;
    if (this._inMinimap(sx, sy)) { this._setLabelHover(null); return; }
    const [mx, my] = PixiAdapterPure.screenToModel(sx, sy, this._cam);
    // 확장 카드 위에 커서가 있으면 현 hover 유지 — 드러난 좌우 영역은 원 노드 bbox 밖이라 그대로 두면
    //   "이름 뒷부분을 보려고 다가가면 닫히는" 깜빡임이 난다(codex review P1).
    const cur = this._hoverCard;
    if (cur && PixiAdapterPure.hoverCardHit(mx, my, cur.g, cur.w, cur.c ? cur.c.position.x : null)) return;   // 클램프된 실제 중심 기준
    // graph-move-anim: `_pick` 과 **같은 판정기**를 쓴다 — 한쪽만 트윈을 고려하면 보이는 노드를 hover 해도
    //   카드가 안 뜨거나 엉뚱한 노드가 뜬다(codex review 2차 P2).
    const hit = this._hitNodes(mx, my, (nd) => !this._isCatBg(nd));
    this._setLabelHover(hit || null);
  }

  // 대기 중인 hover 프로브 무효화(+ clear=true 면 현 hover 도 해제). pointerleave·destroy 공용.
  _cancelHoverProbe(clear) {
    if (this._hoverProbeRaf) { try { cancelAnimationFrame(this._hoverProbeRaf); } catch (_) {} this._hoverProbeRaf = 0; }
    this._hoverPt = null;
    if (clear) this._setLabelHover(null);
  }

  _setLabelHover(n) {
    const id = n ? n.id : null;
    if (id === this._hoverId) return;              // 같은 대상 — 재구성 없음(스윕 중 무한 rebuild 방지)
    this._hoverId = id;
    if (this._hoverTimer) { try { clearTimeout(this._hoverTimer); } catch (_) {} this._hoverTimer = 0; }
    const had = this._clearLabelHoverVisual(true);   // 이탈은 축소 애니(툭 꺼지지 않게)
    const geom = n ? this._labelExpandGeom(n) : null;
    // render-on-demand 보존: 보이던 카드가 없고 새로 띄울 것도 없으면 렌더하지 않는다(마우스 스윕 = GPU 0).
    if (!geom) { if (had) this._render(); return; }
    const fire = () => { this._hoverTimer = 0; if (this._hoverId === id) this._showLabelExpand(n, geom); };
    if (typeof setTimeout === "function" && HOVER_EXPAND_DELAY_MS > 0) this._hoverTimer = setTimeout(fire, HOVER_EXPAND_DELAY_MS);
    else fire();
  }

  // 전체 라벨 폭을 측정해 순수 기하로 넘긴다(잘림 판정 + 목표 폭).
  _labelExpandGeom(n) {
    const s = (n && n.style) || {};
    if (!this.P || !s.labelText || !s.labelMaxWidth) return null;
    const fullW = this._measureLabel(String(s.labelText), s);
    return PixiAdapterPure.hoverExpandGeom(n, fullW, { maxWidth: HOVER_EXPAND_MAXW });
  }

  // 전체 라벨 폭 측정(1회 캐시). 텍스트+폰트 파라미터가 같으면 폭도 같으므로 노드 id 가 아닌 그 조합이 캐시 키
  //   (스코프 전환·rebuild 로 id 가 바뀌어도 재측정 없음). 측정용 텍스트는 씬에 붙이지 않고 즉시 destroy.
  _measureLabel(text, s) {
    const size = s.labelFontSize || 12, weight = s.labelFontWeight || 400;
    const k = size + "|" + weight + "|" + text;
    if (this._labelWCache.has(k)) return this._labelWCache.get(k);
    let w = 0;
    try { const t = this._makeText(text, { size, fill: s.labelFill || "#ffffff", weight }); w = t.width; t.destroy(); } catch (_) { w = 0; }
    if (this._labelWCache.size > 4000) this._labelWCache.clear();   // 장기 세션 누적 방어(재측정은 저렴)
    this._labelWCache.set(k, w);
    return w;
  }

  // 확장 카드 구성 + rAF 트윈. 카드 = [상태 halo] + [칩 배경] + [전체 라벨(현재 폭에 맞춰 순차 노출)].
  //   원 노드는 그대로 두고 그 위에 같은 중심·같은 높이·같은 색으로 덮으므로 t=0 에 시각적으로 동일 →
  //   "칩이 스스로 넓어지는" 연속 애니가 된다(교체 팝 없음). scene 모델 미변경 = 이웃 노드 위치 불변.
  _showLabelExpand(n, g) {
    const P = this.P, layer = this._labelHoverLayer;
    if (!P || !layer) return;
    const s = n.style || {}, full = String(s.labelText);
    // 카드는 **항상 불투명**(alpha 1)이다. dim(§57.9) 된 노드의 alpha(0.38)를 카드에도 램프하면, 램프 도중
    //   아래 원 노드의 잘린 라벨이 비쳐 확장 중인 글자와 이중으로 겹친다(codex review P2). 애초에 사용자가
    //   hover 한 이유가 "이 이름을 읽으려고" 이므로 dim 노드도 즉시 판독 가능한 게 맞다.
    const c = new P.Container(); c.position.set(PixiAdapterPure.hoverCardCenterX(g, g.w0), g.y); c.alpha = 1;
    const halo = new P.Container(), bg = new P.Graphics();
    const t = this._makeText(full, { size: s.labelFontSize || 12, fill: s.labelFill || "#ffffff", weight: s.labelFontWeight || 400 });
    // graph-label-hover-anchor: 텍스트도 **좌측 정렬**. 기준선(textLeft)은 pad 로 추정하지 않고 **원 노드가
    //   실제로 렌더하던 잘린 라벨의 좌측**을 역산해 쓴다 — 원 라벨은 중앙 정렬이므로 `노드중심 - 렌더폭/2`.
    //   (루틴 칩처럼 labelMaxWidth 가 칩 폭보다 큰 스타일에서 pad 기준을 쓰면 hover 순간 ~17px 튄다.)
    t.anchor.set(0, 0.5);
    this._fitText(t, full, g.inner0);
    const tw0 = t.width;
    // graph-role-badge(2026-07-28): 원 노드의 center 라벨은 `labelOffsetX`(배지 몫)만큼 밀려 있다 — 역산하는
    //   textLeft 도 같은 몫을 더해야 hover 순간 앞글자가 배지 위로 튀지 않는다(t=0 픽셀 동일 보존).
    const lox = s.labelOffsetX || 0;
    const textLeft = (tw0 > 0) ? (g.x + lox - tw0 / 2) : (g.left + g.pad / 2);
    // 배지는 원 노드와 **같은 world 위치**에 고정한다(카드는 좌변 고정·우측 성장이므로 배지는 움직이지 않는
    //   영역). 카드 로컬 좌표계는 폭에 따라 원점이 이동하므로 paint 에서 노드 원점 오프셋으로 상쇄한다.
    // 카드 배지도 body 와 같은 alpha(running desaturate) — 카드는 아래 `fa` 로 body 를 그린다(codex P2).
    const badge = s.roleBadge ? this._roleBadge(Object.assign({}, s, { size: [g.w0, g.h] }), this._nodeFillAlpha(n)) : null;
    c.addChild(halo, bg);
    if (badge) c.addChild(badge);
    c.addChild(t);
    layer.addChild(c);
    const card = { c, g, node: n, w: g.w0, raf: 0, paint: null };   // node = _pick tier0 프록시 대상
    card.paint = (w) => {
      card.w = w;
      c.position.x = this._clampCardX(g, w);   // 가장자리 칩·미니맵 아래로 카드가 잘리지 않게 가로 보정
      // 상태 테두리(selected/analyzed/running/match)를 확장 폭에 맞춰 다시 그린다 — 원 노드 halo 가 카드 밖으로
      //   비죽 나와 보이는 어긋남 방지. _drawNode 와 동일 계약(_applyNodeStates) 재사용.
      for (const ch of halo.removeChildren()) { try { ch.destroy({ children: true }); } catch (_) {} }
      this._applyNodeStates(halo, { states: n.states, style: Object.assign({}, s, { size: [w, g.h] }) });
      bg.clear();
      // 반투명 fill(running desaturate)을 그대로 얹으면 아래 원 노드의 라벨이 비친다 → 캔버스 배경색 불투명
      //   베이스를 깔고 같은 alpha 로 덮어 "노드가 배경 위에 합성된 모습"을 재현(불투명 + 상태 채도 동시 충족).
      const fa = this._nodeFillAlpha(n);
      if (fa < 1) bg.roundRect(-w / 2, -g.h / 2, w, g.h, g.radius).fill({ color: this.cfg.background || "#f6f8fb", alpha: 1 });
      bg.roundRect(-w / 2, -g.h / 2, w, g.h, g.radius).fill({ color: s.fill || "#0f7d8c", alpha: fa });
      if (s.lineWidth) bg.stroke({ color: s.stroke || "#ffffff", width: s.lineWidth });
      // 텍스트 가용폭은 박스 폭과 분리 보간(inner0=원 한계 → inner1=종단 안쪽 폭) — 위 hoverExpandGeom 주석 참조.
      const span = g.w1 - g.w0, k = span > 0 ? Math.max(0, Math.min(1, (w - g.w0) / span)) : 1;
      this._fitText(t, full, Math.max(0, g.inner0 + (g.inner1 - g.inner0) * k));
      t.position.set(PixiAdapterPure.hoverTextOffsetX(g, w, textLeft), 0);   // 앞글자 절대 위치 고정
      // graph-role-badge: 배지도 라벨과 **같은 규약**(unclamped 중심 기준 카드-로컬) — 클램프로 카드가 밀릴 때
      //   함께 실려 이동하므로 카드 밖으로 삐져나가지 않고, 클램프 없는 통상 경로에선 원 노드 위치와 일치.
      //   alpha 는 매 paint 에서 재적용한다 — hover 중 running 전이(setElementState → paint)에도 배지 채도가
      //   body(위 `fa`)·halo 와 함께 갱신된다(codex review P2 2차: 생성 시 1회면 stale 채도가 hover 종료까지 남음).
      if (badge) { badge.position.x = PixiAdapterPure.hoverBadgeOffsetX(g, w); badge.alpha = fa; }
    };
    this._hoverCard = card;
    card.paint(g.w0);
    this._render();
    this._tweenCard(card, g.w0, g.w1, HOVER_EXPAND_MS, null);
  }

  // 확장 카드 중심의 world x — 좌변 고정(hoverCardCenterX) 위에 뷰포트 + 미니맵 회피 클램프를 얹는다.
  //   순수 산술은 PixiAdapterPure.hoverCardCenterX / clampCardCenterX.
  _clampCardX(g, w) {
    const base = PixiAdapterPure.hoverCardCenterX(g, w);
    const [vw] = this.getSize();
    if (!(vw > 0)) return base;
    const cam = this._cam;
    let rightMax = vw;
    const mm = this._minimap;
    if (mm && mm.c) {   // 미니맵(app.stage 자식 = world 위)과 세로로 겹치면 그 왼쪽까지만 확장
      const my0 = mm.c.position.y, my1 = my0 + mm.size[1];
      const cy = g.y * cam.zoom + cam.y, ch = Math.abs(g.h * cam.zoom) / 2;
      if (cy + ch > my0 && cy - ch < my1) rightMax = mm.c.position.x;
    }
    const sx = PixiAdapterPure.clampCardCenterX(base * cam.zoom + cam.x, w * cam.zoom, vw, 6, rightMax);
    return (sx - cam.x) / cam.zoom;
  }

  // 카드 폭 트윈(확장/축소 공용). rAF 부재 환경(node vm 등)은 종단 상태 즉시 적용.
  _tweenCard(card, w0, w1, dur, onEnd) {
    const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
    const done = () => { if (onEnd) onEnd(); };
    if (!raf) { card.paint(w1); this._render(); done(); return; }
    const t0 = (typeof performance !== "undefined" ? performance.now() : 0);
    const ease = (k) => 1 - Math.pow(1 - k, 3);   // easeOutCubic — _tween(카메라)과 동일 감속감
    const step = (now) => {
      card.raf = 0;
      if (!card.c.parent) { done(); return; }     // rebuild/destroy 로 이미 떨어져 나감
      const k = Math.min(1, (now - t0) / dur), e = ease(k);
      card.paint(w0 + (w1 - w0) * e);
      this._render();
      if (k < 1) card.raf = raf(step); else done();
    };
    card.raf = raf(step);
  }

  _destroyCard(card) {
    if (!card) return;
    if (card.raf) { try { cancelAnimationFrame(card.raf); } catch (_) {} card.raf = 0; }
    try { if (card.c.parent) card.c.parent.removeChild(card.c); } catch (_) {}
    try { card.c.destroy({ children: true }); } catch (_) {}
  }

  // 전체 문자열을 maxW 안에 맞춰 넣는다(넘치면 ellipsis). _ellipsize 와 달리 **매번 전체 문자열 기준**이라
  //   확장 애니 중 폭이 커질수록 글자가 순차로 드러난다(잘린 상태에서 연속 시작 → 중간 슬라이스 팝 없음).
  _fitText(t, full, maxW) {
    const s = String(full);
    if (t.text !== s) t.text = s;
    if (t.width <= maxW) return;
    let lo = 0, hi = s.length;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; t.text = s.slice(0, mid) + "…"; (t.width <= maxW) ? lo = mid : hi = mid - 1; }
    t.text = s.slice(0, lo) + "…";
  }

  // 현재 카드 종료. animate=true 면 원 칩 폭으로 되감아(축소) 제거 — 넓은 카드가 툭 꺼지는 팝 방지.
  //   축소 진행 카드는 **동시 1장**만 유지한다(새 이탈이 겹치면 이전 것은 즉시 제거 — 누적/겹침 차단).
  //   반환 = 실제로 정리한 카드가 있었는가(호출부의 불필요 렌더 억제용).
  _clearLabelHoverVisual(animate) {
    // 축소 진행 카드 제거도 "정리함"으로 집계해야 한다 — 그러지 않으면 (확장카드 이탈 → 축소 중 → 빈 배경)
    //   연속에서 false 를 반환해 호출부가 렌더를 생략하고, render-on-demand(autoStart:false) 라 마지막
    //   프레임버퍼에 유령 카드가 남는다(codex review P1).
    let cleaned = false;
    if (this._outCard) { this._destroyCard(this._outCard); this._outCard = null; cleaned = true; }
    const card = this._hoverCard;
    this._hoverCard = null;
    if (!card) return cleaned;
    if (card.raf) { try { cancelAnimationFrame(card.raf); } catch (_) {} card.raf = 0; }
    const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
    if (!animate || !raf) { this._destroyCard(card); return true; }
    this._outCard = card;
    this._tweenCard(card, card.w, card.g.w0, HOVER_COLLAPSE_MS, () => {
      if (this._outCard === card) this._outCard = null;
      this._destroyCard(card); this._render();
    });
    return true;
  }
  // rebuild/destroy 진입점 — 예약 타이머·hover id 까지 초기화(다음 pointermove 가 재도출). 좌표·라벨이 이미
  //   바뀐 뒤라 축소 애니는 무의미(옛 위치에서 되감기면 오히려 어색) → 즉시 제거.
  _clearLabelHover() {
    if (this._hoverTimer) { try { clearTimeout(this._hoverTimer); } catch (_) {} this._hoverTimer = 0; }
    this._hoverId = null;
    this._clearLabelHoverVisual(false);
  }
  // graph-ctxmenu(hit-test 층서 = 시각 z-페인트 순서 정합, WYSIWYG): 구체 요소 > 스키마 클러스터 배경(combo) > 카테고리 밴드 배경(cat-bg).
  //   근본 결함: CAT 밴드 배경은 멤버 클러스터 전체를 덮는 node(z=_METZ.CAT_BG=-1)인데, 예전 _pick 은
  //   node 를 combo 보다 **무조건 먼저** 반환했다. 그래서 스키마 클러스터 빈 배경(combo, z=0 — 밴드보다
  //   위에 페인팅됨) 우클릭이 combo 폴백에 닿기 전에 밑에 깔린 CAT node(z=-1)에 가로채여 '카테고리 메뉴'로
  //   오라우팅됐다(사용자 보고 "스키마 클러스터 우클릭 → 카테고리 메뉴"). 즉 hit-test 가 페인트 순서를
  //   위반했다. → cat-bg 를 최하위 tier 로 내려 "combo(z0)가 cat-bg(z-1) 위"라는 페인트 순서를 hit 에도 재현.
  //   시각 페인팅 z 불변 — hit-test 우선순위만 교정. 결과는 "보이는 대로 클릭": 카드·클러스터가 밴드 위에
  //   보이면 그 요소 메뉴(tier1/2), 밴드 tint 고유 여백만 보이면 카테고리 메뉴(tier3). 헤더 CATH/컨트롤 CATX
  //   는 cat-bg 아님 → tier1 최우선(카테고리 메뉴).
  _isCatBg(n) { return !!(n && n.data && n.data.kind === "cat-bg"); }
  _pick(mx, my) {
    // tier0(graph-label-hover-expand): 확장 카드가 떠 있으면 그 사각형 안은 **그 노드**다. 카드는
    //   eventMode="none" 이고 hit-grid 는 원 bbox 만 알아서, 그대로 두면 드러난 영역 클릭·우클릭이 캔버스나
    //   이웃 노드로 새어 선택이 풀리거나 엉뚱한 메뉴가 뜬다(codex review P2). 보이는 대로 클릭 = WYSIWYG.
    const cur = this._hoverCard;
    if (cur && cur.node && PixiAdapterPure.hoverCardHit(mx, my, cur.g, cur.w, cur.c ? cur.c.position.x : null)) return cur.node;
    // tier1: 실 요소(카드·테이블·GB/GH/GX·CATH/CATX 등, cat-bg 제외) — z 최상위
    const n = this._hitNodes(mx, my, (nd) => !this._isCatBg(nd));
    if (n) return n;
    // tier2: 스키마 클러스터 배경(combo) — 카테고리 밴드보다 우선
    const c = PixiAdapterPure.hitTestCombo(mx, my, this._built.combos || [], this._built.nodes || []);
    if (c) return Object.assign({ __combo: true }, c);
    // tier3: 카테고리 밴드 배경(cat-bg) — 밴드 고유 여백/헤더밖 영역 우클릭·드래그만 카테고리로
    return this._hitNodes(mx, my, (nd) => this._isCatBg(nd)) || null;
  }
  // graph-move-anim: 노드 hit-test 단일 진입점 — **보이는 대로 눌린다**(WYSIWYG).
  //   트윈 중이면 ① grid 에서 이동 중인 노드를 제외하고(그 버킷은 목적지라 stale) ② 이동 노드는 화면
  //   좌표로 선형 스캔한 뒤 ③ z 가 큰 쪽을 고른다. 평시(트윈 없음)엔 기존 grid 경로 그대로 = 무회귀.
  //   `_pick`(클릭·우클릭·드래그)과 `_probeHover`(라벨 확장) 가 **같은 함수**를 쓰게 해, 한쪽만 고쳐
  //   "클릭은 되는데 hover 는 안 되는" 반쪽 상태가 나오지 않게 한다.
  _hitNodes(mx, my, filter) {
    const tp = this._tweenPos, mv = this._tweenMovers;
    const gridFilter = tp ? ((nd) => (!filter || filter(nd)) && !tp.has(nd.id)) : filter;
    const gridHit = this._hitGrid ? PixiAdapterPure.hitTest(mx, my, this._hitGrid, this._built.nodes, gridFilter) : null;
    if (!mv || !mv.length) return gridHit;
    const movHit = PixiAdapterPure.hitTestMoving(mx, my, mv, filter);
    if (!movHit) return gridHit;
    if (!gridHit) return movHit;
    const zg = (gridHit.style && gridHit.style.zIndex) || 0, zm = (movHit.style && movHit.style.zIndex) || 0;
    return zm >= zg ? movHit : gridHit;
  }
  // graph-edge-flow: zoom 을 넘겨 곡선 근사 해상도를 화면 기준으로 맞춘다(줌아웃 시 샘플 절약).
  //   끝점은 `_resolvePos`(트윈 오버레이 우선) 로 해소한다 — 관계선은 트윈 중 **그려진 좌표**를 따라가므로
  //   판정도 같은 좌표여야 한다(모델 최종 좌표로 판정하면 보이는 선을 눌러도 빗나간다, codex review 2차 P2).
  _pickEdge(mx, my) { const posOf = (id) => this._resolvePos(id); return PixiAdapterPure.hitTestEdge(mx, my, this._built.edges || [], posOf, 6 / Math.max(0.2, this._cam.zoom), this._cam.zoom); }
  _isCombo(id) { return this._built.combos.some(c => c.id === id); }
  // 이슈#3: 미니맵 상호작용 — 스크린(canvas-relative) 점이 미니맵 박스 안인가.
  _inMinimap(sx, sy) {
    const mm = this._minimap; if (!mm || !mm.c) return false;
    const px = mm.c.position.x, py = mm.c.position.y, [mw, mh] = mm.size;
    return sx >= px && sx <= px + mw && sy >= py && sy <= py + mh;
  }
  // 이슈#3: 미니맵 위 점 → model 좌표 역투영 → 그 model 점을 화면 중앙에 오도록 카메라 이동.
  _minimapPanTo(sx, sy) {
    const mm = this._minimap; if (!mm || !mm._proj) return;
    const pr = mm._proj, [mw, mh] = mm.size;
    // NIT: 드래그가 미니맵 박스를 벗어나면 콘텐츠 밖으로 역투영돼 카메라가 극단으로 날아감 → 로컬 좌표를 박스로 클램프.
    const lx = Math.max(0, Math.min(mw, sx - mm.c.position.x)), ly = Math.max(0, Math.min(mh, sy - mm.c.position.y));
    const [mx, my] = PixiAdapterPure.minimapToModel(lx, ly, pr);
    const [vw, vh] = this.getSize(), cam = this._cam;
    this._userCamSeq += 1;   // graph-move-anim: 미니맵 클릭·드래그도 사용자 카메라 조작
    this._applyCam({ zoom: cam.zoom, x: vw / 2 - mx * cam.zoom, y: vh / 2 - my * cam.zoom });
  }
  // M2: graph-core 의 _metaElementDragEnable 을 G6-shape 이벤트로 호출(주입 시). 미주입이면 항상 허용.
  _elementDragEnable(hit, e) {
    const fn = this.cfg.elementDragEnable; if (typeof fn !== "function") return true;
    try { return fn({ target: { id: hit.id }, targetType: hit.__combo ? "combo" : "node", buttons: (e && e.buttons) || 1, button: (e && typeof e.button === "number") ? e.button : 0 }); } catch (_) { return true; }
  }
  _moveElement(id, ddx, ddy) {
    // graph-move-anim: **사용자 조작이 애니메이션을 이긴다**. 트윈이 살아 있는 채로 드래그하면 매 프레임
    //   트윈이 캡처한 from/to 로 되돌려 써서 손끝과 화면이 어긋나고, 종단 처리가 stale 목적지로 되돌린다
    //   (codex review 3차 P1). 정지 = 대상 전원을 최종 위치에 즉시 안착시키고 오버레이를 걷는 것이라,
    //   이후 드래그는 평시와 동일한 경로(모델 좌표 갱신)로 진행된다.
    if (this._moveTween) this._stopMoveTween();
    const n = this._built.nodes.find(x => x.id === id);
    if (n) { n.style.x += ddx; n.style.y += ddy; const o = this._objs.get(id); if (o) o.position.set(n.style.x, n.style.y); this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128); this._scheduleEdgeRefresh([id]); return; }   // B1: hit-grid 재구성(이동 후 클릭 유지). graph-edge-follow-drag: 이동 노드의 관계선 추종(perf: rAF 코얼레싱)
    // combo(스키마 배경) 드래그: 자식 노드 전체 + combo 카드 배경(자식 파생 bbox 이므로 같은 델타)을 함께 이동(M1)
    const moved = [];
    for (const cn of (this._built.nodes || [])) { if (cn.combo === id) { cn.style.x += ddx; cn.style.y += ddy; const o = this._objs.get(cn.id); if (o) o.position.set(cn.style.x, cn.style.y); moved.push(cn.id); } }
    const card = this._objs.get(id); if (card) { card.position.set(card.position.x + ddx, card.position.y + ddy); }   // M1: combo 배경 카드 추종
    this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128);   // B1
    this._scheduleEdgeRefresh(moved);   // graph-edge-follow-drag: 이동한 자식 노드들의 관계선 추종(perf: rAF 코얼레싱)
  }
  // graph-edge-follow-drag: 노드 드래그로 위치가 바뀐 노드에 연결된 관계선(엣지)만 증분 재그림.
  //   엣지는 절대 model 좌표(a,b)를 Graphics path 에 bake 한 독립 오브젝트라(_drawEdge) 노드 Container 이동으로
  //   따라오지 않는다 — 예전엔 오직 full draw()(줌 밴드 전이 rebuild 등)만 edgeSig(끝점 포함) 변경을 감지해
  //   재생성했다. 그래서 드래그 중에는 관계선이 옛 위치에 남고 "줌 아웃해야 갱신"되는 회귀가 있었다.
  //   여기서 이동 노드의 incident 엣지만 골라 재그려 드래그 중 실시간 추종시킨다(전체 draw() 보다 저렴 —
  //   콤보/전 노드/미니맵 재구성 없이 O(E) 스캔 + incident 엣지만 recreate). _objSig 도 갱신해 다음 full
  //   draw() 가 동일 서명을 재사용(중복 recreate 방지)하게 한다.
  //   판정 = source **또는** target 이 이동집합에 포함(OR). 이로써 두 케이스를 함께 처리한다:
  //     · 내부 엣지(양끝이 같은 제품 카테고리 구성원 — 둘 다 이동): 양끝 새 좌표로 재그림.
  //     · cross-category 엣지(한끝만 이동 — 다른 제품 카테고리로 가는 연결선): 이동 끝점은 새 좌표,
  //       미이동 끝점은 현재 좌표로 재그려 연결선 구조가 갱신된다(제품 카테고리를 옮겨도 타 카테고리
  //       연결선이 옛 위치에 남지 않게 — 사용자 정정 케이스).
  //   graph-edge-drag-perf(3 lever): ① 인접 인덱스(_edgeIndex, node→incident edges)로 O(E) 전량 스캔 →
  //   O(incident) ② 기존 엣지 Graphics **in-place 재사용**(_paintEdge: clear+재-path) — destroy/new Graphics
  //   재생성(GPU 지오메트리 재할당+GC churn) 회피 ③ 호출은 _scheduleEdgeRefresh 로 rAF 코얼레싱(프레임당 1회).
  _refreshIncidentEdges(movedIds) {
    if (!this.world) return;
    const moved = (movedIds instanceof Set) ? movedIds : new Set(movedIds || []);
    if (!moved.size) return;
    for (const e of this._incidentEdges(moved)) {
      const a = this._resolvePos(e.source), b = this._resolvePos(e.target);
      if (!a || !b) continue;
      const eid = PixiAdapterPure.edgeId(e);
      const old = this._objs.get(eid);
      if (old && old.parent === this.world && typeof old.clear === "function") {
        this._paintEdge(old, e, a, b);   // in-place 재사용: clear+재-path(destroy/recreate·GC 회피)
      } else {
        if (old) { try { old.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(old); } catch (_) {} }
        const g = this._drawEdge(e, a, b);
        this.world.addChild(g); this._objs.set(eid, g);
      }
      if (this._objSig) this._objSig.set(eid, PixiAdapterPure.edgeSig(e, a, b));
    }
  }
  // incident 엣지 후보: _edgeIndex 있으면 이동 노드의 인접 엣지만(dedup) 반환 = O(incident). 없으면 O(E) 폴백.
  _incidentEdges(moved) {
    const idx = this._edgeIndex;
    if (!idx) return (this._built.edges || []).filter(e => moved.has(e.source) || moved.has(e.target));
    const out = [], seen = new Set();
    for (const id of moved) {
      const arr = idx.get(id); if (!arr) continue;
      for (const e of arr) { const eid = PixiAdapterPure.edgeId(e); if (seen.has(eid)) continue; seen.add(eid); out.push(e); }
    }
    return out;
  }
  // graph-edge-drag-perf(P3): 끝점(node id) live 좌표 O(1) 해소. _nodeById 있으면 node.style 직접(드래그로 갱신된
  //   현재 좌표), 비-node(combo/장식) 또는 인덱스 부재는 getElementPosition(bbox 중심) 폴백. getElementPosition 의
  //   O(N) nodes.find 를 incident 엣지마다 2회 돌던 비용(O(incident×N)) 제거.
  _resolvePos(id) {
    // graph-move-anim: 이동 트윈 중에는 **화면에 보이는 좌표**가 관계선의 끝점이어야 한다. 모델
    //   (`n.style`)은 이미 최종 위치라, 이 오버레이가 없으면 선이 노드를 떠나 목적지에 먼저 가 붙는다.
    //   오버레이는 트윈 수명 동안만 존재하고(종료 시 null) 모델은 끝까지 건드리지 않는다 —
    //   `_metaG6Build` 의 배치 메모이즈·미니맵 서명·hit-grid 가 전부 모델을 읽기 때문이다.
    const tp = this._tweenPos;
    if (tp) { const p = tp.get(id); if (p) return [p[0], p[1]]; }
    const nb = this._nodeById;
    if (nb) { const n = nb.get(id); if (n) return [n.style.x, n.style.y]; }
    return this.getElementPosition(id);
  }

  // ── graph-move-anim: 재배치 이동 트윈 ─────────────────────────────────────────
  //   요청(REQ): "노드 위치 재배치가 깜빡이는 순식간이라 각 이동을 인지하기 어렵다 — 애니메이션으로
  //   사용자가 이동을 인지하게". 전역 G6 애니메이션은 레이아웃 셔플을 재유발하므로 켜지 않고
  //   (graph-core `_metaGraphAnimateFocus` 주석의 같은 근거), **결정론 배치는 그대로 둔 채** 어댑터가
  //   컨테이너 좌표만 `from → to` 로 옮긴다. 모델·서명·미니맵·hit-grid 는 최종 값을 유지한다.
  //   비활성 조건(전부 기존 즉시 반영으로 안전 폴백): prefers-reduced-motion · rAF 부재 ·
  //   씬 교체 · 이동 0 · 화면 밖 · 상한 초과. 관측은 `__META_GRAPH_PERF.move`.
  _startMoveTween(built) {
    const prev = this._prevPos; this._prevPos = null;
    if (!prev || !this.world) return;
    const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
    let reduced = false;
    try { reduced = !!(typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (_) {}
    if (!raf || reduced) { try { _pxPerf().move = { items: 0, reason: reduced ? "reduced-motion" : "no-raf" }; } catch (_) {} return; }
    // 가시 rect(model 좌표) — 화면 밖 이동은 트윈하지 않는다(보이지 않는 비용).
    let vis = null;
    try {
      const [vw, vh] = this.getSize(), cam = this._cam, m = MOVE_TWEEN_VIS_MARGIN;
      if (isFinite(vw) && isFinite(vh) && vw > 0 && vh > 0) {
        const a = PixiAdapterPure.screenToModel(-m, -m, cam), b = PixiAdapterPure.screenToModel(vw + m, vh + m, cam);
        vis = { x0: Math.min(a[0], b[0]), y0: Math.min(a[1], b[1]), x1: Math.max(a[0], b[0]), y1: Math.max(a[1], b[1]) };
      }
    } catch (_) { vis = null; }
    const plan = PixiAdapterPure.moveTweenPlan(prev, built.nodes || [], {
      vis, cap: MOVE_TWEEN_CAP, minOverlap: MOVE_TWEEN_MIN_OVERLAP });
    try { _pxPerf().move = { items: plan.items.length, moved: plan.moved, skipped: plan.skipped, reason: plan.reason, ms: MOVE_TWEEN_MS }; } catch (_) {}
    if (!plan.items.length) return;
    // 출발 위치로 되감기 + 관계선 끝점 오버레이 개시(첫 프레임부터 선이 노드에 붙어 있게).
    const live = [], movedIds = new Set(), tp = new Map(), movers = [];
    const byId = new Map();
    for (const n of (built.nodes || [])) byId.set(n.id, n);
    for (const it of plan.items) {
      const o = this._objs.get(it.id);
      if (!o || typeof o.position === "undefined") continue;
      o.position.set(it.from[0], it.from[1]);
      const at = [it.from[0], it.from[1]];   // 트윈이 제자리 갱신하는 좌표 — 관계선·hit-test 가 공유
      tp.set(it.id, at);
      movedIds.add(it.id);
      live.push({ o, from: it.from, to: it.to, id: it.id });
      const nd = byId.get(it.id); if (nd) movers.push({ n: nd, at });
    }
    if (!live.length) return;
    // 관계선 예산 — 프레임 비용의 지배항은 노드가 아니라 **따라 그릴 선의 수**다(허브 하나가 수백 선).
    //   초과하면 트윈을 열지 않고 즉시 최종 위치로 둔다(부분 애니메이션보다 정직한 즉시 반영).
    let incident = 0;
    try { incident = this._incidentEdges(movedIds).length; } catch (_) { incident = 0; }
    if (incident > MOVE_TWEEN_EDGE_CAP) {
      for (const it of live) { try { it.o.position.set(it.to[0], it.to[1]); } catch (_) {} }
      try { _pxPerf().move = { items: 0, moved: plan.moved, skipped: plan.moved, reason: "edge-cap", incident }; } catch (_) {}
      return;
    }
    try { _pxPerf().move.incident = incident; } catch (_) {}
    // 오버레이 개시 — 이 시점부터 관계선·hit-test·요소 bounds 가 **보이는 좌표**를 본다(첫 프레임 콜백
    //   이전에 들어오는 pointer 이벤트도 정합). hit-grid 는 건드리지 않는다: 이동 노드는 grid 에서
    //   제외되고 `_hitNodes` 의 선형 스캔이 맡는다(프레임당 O(전체노드) 재구성 제거 — codex 4차 P2).
    this._tweenPos = tp;
    this._tweenMovers = movers;
    // 드래그와 같은 상황(좌표가 매 프레임 바뀐다)이므로 같은 절약을 쓴다 — 트윈 동안 관계선은 저품질
    //   1가닥으로 그리고 종단에서 고품질로 되돌린다. 드래그 중 rebuild 로 진입한 경우를 위해 **직전 값을
    //   복원**한다(강제 false 로 드래그의 저품질 최적화를 깨지 않게).
    const prevLowFi = this._lowFi;
    this._lowFi = true;
    this._refreshIncidentEdges(movedIds);
    const t0 = _pxNow(), ease = (t) => 1 - Math.pow(1 - t, 3);
    const state = { raf: null, live, movedIds, prevLowFi };
    const step = () => {
      if (this._moveTween !== state) return;   // 새 draw/정지가 선점 — 세대 토큰(hover-flow 와 동일 어휘)
      const k = Math.min(1, (_pxNow() - t0) / MOVE_TWEEN_MS), e = ease(k);
      for (const it of live) {
        const x = it.from[0] + (it.to[0] - it.from[0]) * e, y = it.from[1] + (it.to[1] - it.from[1]) * e;
        // **매 프레임 오브젝트를 재조회**한다 — `setElementState`(busy 해제·선택 점등·분석 마커)는 트윈 도중에도
        //   노드를 파기하고 최종 위치로 새로 만든다. 캡처한 참조만 붙들면 그 순간부터 화면은 안 움직이는데
        //   관계선만 계속 보간돼 노드가 튀고 선이 떨어진다(codex review P1). 재조회 = 교체돼도 자가 치유.
        const o = this._objs.get(it.id) || it.o;
        it.o = o;
        try { o.position.set(x, y); } catch (_) {}
        const p = tp.get(it.id); if (p) { p[0] = x; p[1] = y; }
      }
      if (k < 1) {
        this._refreshIncidentEdges(movedIds);
        this._render();
        state.raf = raf(step);
        return;
      }
      this._finishMoveTween(state, true);
    };
    this._moveTween = state;
    state.raf = raf(step);
  }
  // 트윈 종단/중단 공통 — 오버레이를 **먼저** 걷어야 관계선이 모델 최종 좌표로 다시 구워진다(서명도 최종값
  //   복원: 중간 위치 서명이 남으면 다음 full draw 가 '동일 서명 = 재사용' 으로 옛 그림을 살린다).
  //   저품질 플래그도 여기서 되돌린 뒤 고품질로 1회 재페인트한다(드래그의 `_flushEdgeRefresh` 와 같은 역할).
  _finishMoveTween(state, render) {
    this._moveTween = null;
    this._tweenPos = null;
    this._tweenMovers = null;   // 오버레이 소멸 → hit-test·관계선·bounds 가 모델 최종 좌표로 복귀
    this._lowFi = state.prevLowFi;
    this._refreshIncidentEdges(state.movedIds);
    if (render) { this._renderMinimap(); this._render(); }
  }
  // 진행 중 트윈 정지 — 대상 노드를 **최종 위치로 즉시 안착**시키고 오버레이·저품질 플래그를 되돌린다.
  _stopMoveTween() {
    const st = this._moveTween;
    if (!st) { this._tweenPos = null; this._tweenMovers = null; return; }
    if (st.raf != null) { try { cancelAnimationFrame(st.raf); } catch (_) {} }
    // `step` 과 같은 이유로 **현재 오브젝트를 재조회**한다 — 프레임 사이에 `setElementState` 가 노드를
    //   교체했으면 캡처된 참조는 파기된 것이고, 그것만 최종 위치로 옮기면 화면에 남은 새 오브젝트는
    //   중간 위치에 굳는다(모델은 최종 → 화면·모델 불일치, codex review 6차 P2).
    for (const it of st.live) { const o = this._objs.get(it.id) || it.o; try { o.position.set(it.to[0], it.to[1]); } catch (_) {} }
    this._finishMoveTween(st, false);   // 렌더는 호출부(draw/destroy)가 이어서 수행
  }
  // 드래그 중 엣지 재그림 rAF 코얼레싱: pointermove 가 프레임보다 자주 발화하거나 한 프레임에 _moveElement +
  //   (graph-core 종속이동)translateElementTo 가 겹쳐 호출돼도 이동 id 를 누적해 **프레임당 1회** 재그림+렌더.
  //   노드 좌표/hit-grid 는 호출부에서 동기 갱신(getElementPosition·클릭 정확도 보존) — 비싼 엣지 재그림만 지연.
  //   비-rAF 환경(node vm 테스트 등)은 즉시 동기 폴백. dragend/destroy 는 _flushEdgeRefresh 로 즉시 반영.
  _scheduleEdgeRefresh(movedIds) {
    const raf = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : null;
    const m = (movedIds instanceof Set) ? movedIds : (movedIds || []);
    if (!raf) { this._refreshIncidentEdges(m instanceof Set ? m : new Set(m)); this._render(); return; }
    if (!this._pendingMoved) this._pendingMoved = new Set();
    for (const id of m) this._pendingMoved.add(id);
    // graph-edge-flow: 드래그 중 저품질(1가닥·저해상도)로 그린 엣지를 dragend 에서 되돌리기 위해
    //   대상 id 를 따로 누적한다 — flush 시점의 _pendingMoved 는 마지막 프레임분만이라 불충분.
    if (this._lowFi) { if (!this._lowFiTouched) this._lowFiTouched = new Set(); for (const id of m) this._lowFiTouched.add(id); }
    if (this._pendingRaf) return;
    this._pendingRaf = raf(() => {
      this._pendingRaf = 0;
      const ids = this._pendingMoved; this._pendingMoved = null;
      if (ids && ids.size) this._refreshIncidentEdges(ids);
      this._render();
    });
  }
  // graph-edge-flow: lowFi 해제 후 flush — 드래그 동안 저품질로 그린 엣지 전량을 고품질로 되돌린다.
  //   (_refreshIncidentEdges 가 _objSig 를 갱신하므로 여기서 복원하지 않으면 저품질 도형이 다음 full
  //   draw 에서 '서명 동일 = 재사용' 으로 그대로 살아남는다.)
  _flushEdgeRefresh() {
    if (this._pendingRaf) { try { cancelAnimationFrame(this._pendingRaf); } catch (_) {} this._pendingRaf = 0; }
    const ids = this._pendingMoved; this._pendingMoved = null;
    const wasLow = this._lowFi; this._lowFi = false;
    const touched = this._lowFiTouched; this._lowFiTouched = null;
    let target = ids;
    if (wasLow && touched && touched.size) { if (ids) for (const id of ids) touched.add(id); target = touched; }
    if (target && target.size) { this._refreshIncidentEdges(target); this._render(); }
  }
  // 드래그 이벤트 합성 — payload 에 target.id + buttons/button/targetType(_metaEventButtons·enable predicate 용).
  _emitDrag(phase, hit, e, s, mx, my) {
    // graph-move-anim: 드래그 개시 시점에 트윈을 **먼저** 끝낸다. graph-core 의 dragstart 핸들러가
    //   `getElementPosition`(모델=최종 좌표)으로 잡기 오프셋과 종속 노드 offset 을 계산하는데, 트윈이
    //   살아 있으면 화면상 노드는 다른 곳에 있어 첫 델타가 튀고 종속 이동 offset 이 어긋난다
    //   (codex review 5차 P2). 정지는 대상 전원을 최종 위치에 안착시키므로, 이후 드래그는 화면과
    //   모델이 일치한 상태에서 평시 경로로 진행된다("조작이 애니메이션을 이긴다" 규칙의 일관 적용).
    if (phase === "dragstart" && this._moveTween) this._stopMoveTween();
    const kind = hit.__combo ? "combo" : "node";
    const pl = this._payload(hit, s, mx, my, e);
    pl.targetType = hit.__combo ? "combo" : "node";
    pl.buttons = 1; pl.button = 0;
    this._emit(kind + ":" + phase, pl);
    // m4: 드래그 중엔 미니맵 뷰포트 사각형만 갱신(O(1)) — 콘텐츠 전량 재그림(O(N))은 dragend 로 지연.
    //   graph-edge-drag-perf: dragend 는 rAF 코얼레싱 중이던 엣지 재그림을 즉시 flush(최종 위치 동기 반영).
    // graph-edge-flow: 드래그 구간만 저품질(1가닥·저해상도 대시) — dragend 의 flush 가 고품질 복원.
    if (phase === "dragstart") { this._lowFi = true; this._lowFiTouched = null; }
    if (phase === "dragend") { this._flushEdgeRefresh(); this._renderMinimap(); } else if (phase === "drag") this._renderMinimapViewport();
  }
  _payload(hit, s, mx, my, e) {
    return { target: hit ? { id: hit.id, data: hit.data } : null, id: hit ? hit.id : null,
      canvas: s, client: (e ? { x: e.clientX, y: e.clientY } : s), model: { x: mx, y: my },
      buttons: (e && e.buttons) || 0, button: (e && typeof e.button === "number") ? e.button : 0 };
  }

  // ── 데이터/렌더 ──
  setData(built) {
    // graph-move-anim: **직전 씬의 노드 위치**를 교체 직전에 캡처한다 — draw() 의 diff 는 이동 노드를
    //   파기 후 최종 위치로 재생성하므로, 여기서 잡지 않으면 '어디서 왔는지'가 영영 사라진다.
    //   트윈 진행 중 재-setData 면 스냅샷은 `_tweenPos`(현재 화면상 위치) 우선 — 중간 위치에서 이어져
    //   연속 펼침이 순간이동으로 되돌아가지 않는다.
    try { this._prevPos = this._snapshotPos(this._built); } catch (_) { this._prevPos = null; }
    this._built = built || { nodes: [], edges: [], combos: [] }; this._edgeIndex = null; this._nodeById = null;   // graph-edge-drag-perf: 인접/노드 인덱스 무효화(draw 가 재구성)
  }
  _snapshotPos(built) {
    const m = new Map(), tp = this._tweenPos;
    for (const n of ((built && built.nodes) || [])) {
      const s = n.style || {};
      const cur = tp && tp.get(n.id);   // 트윈 중이면 화면에 실제로 보이는 좌표가 출발점이다
      if (cur) m.set(n.id, [cur[0], cur[1]]);
      else if (isFinite(s.x) && isFinite(s.y)) m.set(n.id, [s.x, s.y]);
    }
    return m;
  }
  async setScene(built) { this.setData(built); await this.draw(); return this; }

  // scene diff 오브젝트 풀(후속 최적화): 매 draw 전량 destroy/recreate 대신 id+서명 기반 재사용.
  //   서명 = 렌더 기하에 영향 주는 전량(node=combo+style+states, edge=끝점+style, combo=style+bbox).
  //   서명 동일 → 재사용(skip make), 변경 → 해당 1개만 recreate, 신규 → add, 소멸 → remove. world.sortableChildren=true
  //   라 zIndex 페인트 정렬은 자동(자식 순서 무관). 선택/상태변경(기하 동일) 리빌드에서 대다수 노드 재사용 = GC↓·draw↓.
  async draw() {
    await this._ready;
    if (!this.world) return;   // 비브라우저/미배선 — no-op
    this._stopMoveTween();   // graph-move-anim: 진행 중 이동 트윈을 **diff 앞에서** 정지 — 아래 재생성이 컨테이너를 파기하므로 stale rAF 가 파기된 객체에 쓰는 것을 차단.
    this._stopHoverFlow();   // detail-hover-flow: 좌표가 바뀌면 흐름 폴리라인이 stale — rAF 를 먼저 세운다(분리된 Graphics 에 계속 페인트하는 누수 차단).
    this._clearHoverLayer();   // detail-hover-fx: rebuild 로 노드 좌표가 바뀌면 stale 강조 제거(hover 는 transient — 재hover 시 재도출).
    this._clearLabelHover();   // graph-label-hover-expand: rebuild 로 좌표·라벨·폭이 바뀌면 stale 확장 카드 제거
    const drawT0 = _pxNow();
    this._labelStat = { created: 0, bitmap: 0, text: 0, ms: 0 };   // graph-perf: draw 단위 라벨 생성 비용
    const built = this._built;
    // 끝점 위치 O(1) 조회 맵(구 O(N·E) find 제거)
    const npos = new Map();
    // graph-edge-drag-perf(P3): node id → node 맵도 유지 → 드래그 중 _resolvePos 가 live 좌표를 O(1) 조회
    //   (getElementPosition 의 O(N) nodes.find 제거 — 허브 드래그 O(incident×N)→O(N+incident)). setData 무효화.
    this._nodeById = new Map();
    for (const n of (built.nodes || [])) { npos.set(n.id, [n.style.x, n.style.y]); this._nodeById.set(n.id, n); }
    const pos = (id) => { if (npos.has(id)) return npos.get(id); const bb = this.getElementRenderBounds(id); return bb ? [bb.x + bb.width / 2, bb.y + bb.height / 2] : null; };
    // spec 목록 + 서명
    const specs = [];
    for (const c of (built.combos || [])) { const bb = PixiAdapterPure.comboBBox(c.id, built.nodes, (c.style || {}).padding); if (!bb) continue;
      specs.push({ id: c.id, sig: PixiAdapterPure.comboShapeSig(c, bb), pos: [bb.x, bb.y], make: () => this._drawCombo(c, bb) }); }
    // graph-edge-drag-perf: 인접 인덱스(node id → incident edge[]) — 드래그 재그림이 O(E) 전량 스캔 대신 O(incident).
    //   토폴로지(source/target)만 의존 → 드래그(좌표만 변화) 동안 유효, setData 에서 무효화. 미해소 끝점 엣지도 포함(완전).
    this._edgeIndex = PixiAdapterPure.buildEdgeIndex(built.edges);
    for (const e of (built.edges || [])) {
      const a = pos(e.source), b = pos(e.target); if (!a || !b) continue;
      const eid = PixiAdapterPure.edgeId(e);
      specs.push({ id: eid, sig: PixiAdapterPure.edgeSig(e, a, b), edge: e, ea: a, eb: b, make: () => { const g = this._drawEdge(e, a, b); this._objs.set(eid, g); return g; } }); }
    for (const n of (built.nodes || [])) specs.push({ id: n.id, sig: PixiAdapterPure.nodeShapeSig(n), pos: [n.style.x, n.style.y], make: () => this._drawNode(n) });
    // diff
    if (!this._objSig) this._objSig = new Map();
    const nextIds = new Set(); for (const sp of specs) nextIds.add(sp.id);
    for (const [id, obj] of Array.from(this._objs)) { if (!nextIds.has(id)) { try { obj.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(obj); } catch (_) {} this._objs.delete(id); this._objSig.delete(id); } }
    let reused = 0, made = 0, moved = 0, repainted = 0;
    for (const sp of specs) {
      if (this._objSig.get(sp.id) === sp.sig && this._objs.has(sp.id)) {
        // graph-expand-perf: 모양 서명이 같으면 **이동만** 반영한다(파기·재생성 없음 = 라벨 재생성 0).
        //   위치를 서명에서 뺐으므로 여기서 명시적으로 동기화해야 화면과 모델이 어긋나지 않는다.
        if (sp.pos) {
          const o = this._objs.get(sp.id), p = o && o.position;
          if (p && (p.x !== sp.pos[0] || p.y !== sp.pos[1])) { try { o.position.set(sp.pos[0], sp.pos[1]); moved++; } catch (_) {} }
        }
        reused++; continue;
      }
      const old = this._objs.get(sp.id);
      // graph-expand-perf: 엣지는 **in-place 재-path**(clear+재그림)로 교체한다 — `_refreshIncidentEdges`(드래그)가
      //   이미 쓰는 경로다. destroy/new Graphics 는 GPU 지오메트리 재할당 + GC churn 을 부르는데, 엣지는
      //   끝점 좌표만 바뀌는 경우가 절대다수(형제 이동)라 그 비용이 통째로 낭비였다.
      if (old && sp.edge && old.parent === this.world && typeof old.clear === "function") {
        this._paintEdge(old, sp.edge, sp.ea, sp.eb);
        this._objSig.set(sp.id, sp.sig); repainted++; reused++; continue;
      }
      if (old) { try { old.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(old); } catch (_) {} }
      const obj = sp.make(); this.world.addChild(obj); this._objSig.set(sp.id, sp.sig); made++;
    }
    this._lastDrawStats = { reused, made, moved, repainted, total: specs.length };
    this._hitGrid = PixiAdapterPure.buildHitGrid(built.nodes, 128);
    this._renderMinimap();
    // graph-move-anim: 오브젝트가 **최종 위치로 생성된 직후** 출발 위치로 되돌리고 트윈을 건다.
    //   미니맵·hit-grid 는 최종 기하 기준 그대로다(클릭은 안착 지점에 떨어지고 미니맵은 튀지 않는다).
    this._startMoveTween(built);
    this._render();
    // graph-perf(사용자 요청 2026-07-28): 라벨·draw 비용을 라이브에서 그대로 읽을 수 있게 남긴다.
    //   label-lod 의 억제 통계(window.__META_GRAPH_PERF.label)와 같은 객체를 공유 — 억제가 실제로
    //   draw call·라벨 생성 비용을 얼마나 줄였는지 한 지점에서 대조 가능하다. 계측 전용(동작 분기 0).
    try {
      const perf = _pxPerf(), ls = this._labelStat;
      perf.render = { drawMs: Math.round((_pxNow() - drawT0) * 100) / 100,
        objects: specs.length, reused, made, moved, repainted,
        labelsCreated: ls.created, labelsBitmap: ls.bitmap, labelsText: ls.text,
        labelMs: Math.round(ls.ms * 100) / 100 };
    } catch (_) {}
    this._emit("afterdraw", { data: { stage: "data" } });   // graph-core 는 e.data.stage 를 읽는다(gap #16)
  }

  // 노드 body fill alpha — §18.8 M1 의 running desaturate(G6 running.fillOpacity 0.45) 포함.
  //   `_drawNode` 와 hover 확장 카드가 **공유**한다: 카드가 항상 불투명이면 running 노드를 hover 하는 순간
  //   채도가 되살아나, 앰버/주황 역할색 위에서 주황 점선 테두리가 위장되는 원 문제가 재발한다(codex review P2).
  _nodeFillAlpha(n) {
    const s = (n && n.style) || {}, states = (n && n.states) || [];
    const runSc = (states.indexOf("running") >= 0) ? (this._nodeState.running || { fillOpacity: 0.45 }) : null;
    return runSc ? (runSc.fillOpacity != null ? runSc.fillOpacity : 0.45) : (s.fillOpacity == null ? 1 : s.fillOpacity);
  }

  _drawNode(n) {
    const P = this.P, s = n.style || {}, c = new P.Container();
    c.zIndex = s.zIndex || 4; c.position.set(s.x, s.y);
    const g = new P.Graphics();
    const st = { color: s.stroke || "#ffffff", width: s.lineWidth || 1 };
    // §18.8 M1: running 상태의 fill desaturate(G6 running.fillOpacity 0.45 — 앰버/주황 역할색 위에서 주황 점선 테두리
    //   위장 방지)를 어댑터에 복원. state config 의 fillOpacity 는 node.style 에 bake 안 되므로 states 로 판정해 fill alpha 적용.
    const fillAlpha = this._nodeFillAlpha(n);
    if (n.type === "circle") { const r = (typeof s.size === "number" ? s.size : 11) / 2; g.circle(0, 0, r).fill({ color: s.fill || "#5c6773", alpha: fillAlpha }); if (s.lineWidth) g.stroke(st); }
    else { const w = Array.isArray(s.size) ? s.size[0] : (s.size || 100), h = Array.isArray(s.size) ? s.size[1] : 24;
      g.roundRect(-w / 2, -h / 2, w, h, s.radius || 0).fill({ color: s.fill || "#0f7d8c", alpha: fillAlpha });
      if (s.lineWidth) {
        if (Array.isArray(s.lineDash)) {   // m2: 노드 lineDash(그룹 배경 GB 점선) 소비 — rect 4변 대시
          const D = PixiAdapterPure.dashSegments, dd = s.lineDash;
          for (const seg of [].concat(D(-w/2,-h/2,w/2,-h/2,dd), D(w/2,-h/2,w/2,h/2,dd), D(w/2,h/2,-w/2,h/2,dd), D(-w/2,h/2,-w/2,-h/2,dd))) g.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
          g.stroke(st);
        } else g.stroke(st);
      } }
    c.addChild(g);
    if (s.roleBadge) c.addChild(this._roleBadge(s, fillAlpha));   // graph-role-badge: 좌측 역할색 타일(+아이콘) — body 와 같은 alpha
    if (s.labelText) c.addChild(this._label(s.labelText, s));
    // 상태 오버레이 (selected 테두리·match glow·analyzed/running 마커) — base 는 이미 style 에 bake(dim=opacity)
    this._applyNodeStates(c, n);
    if (s.opacity != null) c.alpha = s.opacity;   // dim bake (ADR-028)
    this._objs.set(n.id, c);
    return c;
  }

  // 라벨 팩토리(§80): BitmapText(dynamic font, white-base + tint 로 glyph atlas 색-무관 공유 → 렌더 draw call 17×↓,
  //   render-on-demand 팬 매 프레임 재렌더에 직결) 기본, 실패/미지원 시 PIXI.Text 폴백(품질 동일). fill 은 tint(hex→number).
  _makeText(text, o) {
    const t0 = _pxNow();
    const r = this._makeTextInner(text, o);
    const st = this._labelStat;
    st.created += 1; st.ms += (_pxNow() - t0);
    if (r && this.P && this.P.BitmapText && r instanceof this.P.BitmapText) st.bitmap += 1; else st.text += 1;
    return r;
  }

  _makeTextInner(text, o) {
    const P = this.P, size = o.size || 12, fill = o.fill || "#ffffff", weight = String(o.weight || 400);
    const engine = this.cfg.labelEngine || "bitmap";
    const col = PixiAdapterPure.hexToTint(fill);
    // bitmap 은 white-base glyph + tint 로 색을 낸다 → tint 로 표현 불가한 색(비-hex rgb()/named)은 Text 로 강등(m1).
    // graph-emoji-color(fix): 색 이모지 포함 라벨도 Text 로 강등한다 — BitmapText(alpha 마스크 + tint)는 색 채널을
    //   잃어 검은/흰 단색 실루엣만 남기므로(테이블 역할 아이콘 📊/👤/💳 등이 실루엣으로 보이던 버그). Text 는 canvas
    //   색 이모지 폰트로 네이티브 렌더. 이모지 없는 대다수 라벨(컬럼·테이블명)은 BitmapText 경로 유지(draw-call 최적화 보존).
    if (engine === "bitmap" && P.BitmapText && col.valid && !PixiAdapterPure.hasEmoji(text)) {
      try {
        const b = new P.BitmapText({ text: String(text), style: { fontFamily: "system-ui, 'Segoe UI', sans-serif", fontSize: size, fill: "#ffffff", fontWeight: weight } });
        b.tint = col.tint;
        // M2: dynamic-font glyph 래스터화는 지연(첫 width/render)이라 생성 try 밖에서 throw 시 폴백 무력 →
        //   여기서 강제 measure 로 실패를 생성 시점으로 당긴다(성공하면 이후 경로 안전, 실패면 catch→Text).
        void b.width;
        return b;
      } catch (_) { /* dynamic font 래스터화 실패 → Text 폴백(아래) */ }
    }
    // graph-emoji-color(fix): 폴백 폰트 스택에 색 이모지 폰트를 명시 추가 — 색 이모지가 캔버스에서 확실히 컬러 글리프로
    //   렌더되도록(브라우저 per-glyph 폰트 폴백: 텍스트는 Segoe UI, 이모지 코드포인트만 이모지 폰트로). 색 이모지는
    //   fillStyle 을 무시하고 고유 색으로 그려지므로 fill 은 주변 텍스트에만 적용된다.
    return new P.Text({ text: String(text), style: { fontFamily: "system-ui, 'Segoe UI', 'Segoe UI Emoji', 'Noto Color Emoji', 'Apple Color Emoji', sans-serif", fontSize: size, fill: fill, fontWeight: weight }, resolution: this._labelRes });
  }

  _label(text, s) {
    const place = s.labelPlacement || "center";
    const t = this._makeText(text, { size: s.labelFontSize || 12, fill: s.labelFill || "#ffffff", weight: s.labelFontWeight || 400 });
    if (s.labelMaxWidth && t.width > s.labelMaxWidth) this._ellipsize(t, s.labelMaxWidth);
    if (place === "right") { t.anchor.set(0, 0.5); t.position.set((typeof s.size === "number" ? s.size / 2 : 6) + (s.labelOffsetX || 4), 0); }
    else if (place === "top") { t.anchor.set(0, 1); t.position.set((Array.isArray(s.size) ? -s.size[0] / 2 : 0) + 4, (Array.isArray(s.size) ? -s.size[1] / 2 : 0) - 4); }
    // graph-role-badge(2026-07-28): center 라벨도 labelOffsetX 를 소비한다 — 좌측 역할 배지가 차지한 몫만큼
    //   라벨 중심을 오른쪽으로 밀어 잔여 영역의 중앙에 놓는다(배지 없는 노드는 키 부재 = 종전과 동일).
    else { t.anchor.set(0.5, 0.5); if (s.labelOffsetX) t.position.set(s.labelOffsetX, 0); }
    return t;
  }

  // graph-role-badge(2026-07-28 사용자 리포트): 테이블 노드 좌측 역할 배지 = 역할색 라운드 타일 + 역할 아이콘.
  //   역할색의 적용 면적을 노드 전면(150×24)에서 이 타일(18×18)로 줄여 노드 간 본체색 정합을 회복한다
  //   (설계 근거는 graph-roleviz.js `_META_ROLE_BADGE` 주석). 아이콘은 label-lod 가 판독 하한 미만에서
  //   `icon: ""` 로 비우므로 그 구간엔 색 타일만 남는다.
  //   타일에 흰 테두리를 두르는 이유: teal 본체 위에서 진한 역할색(#0072B2 등)의 경계가 묻히지 않게 —
  //   노드 stroke(#ffffff)와 같은 어휘라 시각적으로 "본체 안에 얹힌 칩" 으로 읽힌다.
  //   `fillAlpha` — 노드 body 와 **같은** alpha(`_nodeFillAlpha`). running(AI 분석 중) 상태는 body fill 을
  //   0.45 로 desaturate 하는데(§18.8 M1), 배지를 불투명으로 두면 역할 타일만 채도가 살아 "분석 중" 구분이
  //   약해지고, 주황 계열 역할색(log #E69F00 · config #D55E00)이 주황 running 점선 테두리와 섞인다
  //   (codex review P2, 2026-07-28 — 종전 본체 역할색 시절의 U2 위장 문제가 배지로 옮겨온 형태).
  _roleBadge(s, fillAlpha) {
    const P = this.P, rb = s.roleBadge || {};
    const w = Array.isArray(s.size) ? s.size[0] : (s.size || 100);
    const side = rb.size > 0 ? rb.size : 18;
    const cx = PixiAdapterPure.roleBadgeCX(w, side);
    const c = new P.Container();
    // alpha 는 **컨테이너 단위**로 적용한다 — 타일 fill·흰 테두리·아이콘(PIXI.Text)이 한 번에 같은 비율로
    //   흐려져야 running desaturate 가 배지 전체에 성립한다(개별 fill alpha 로 주면 이모지만 선명하게 남는다,
    //   codex review P2 2차). 컨테이너 alpha 라 hover 카드가 `paint` 에서 값만 갱신할 수도 있다(재생성 불요).
    c.alpha = (fillAlpha == null) ? 1 : fillAlpha;
    const g = new P.Graphics();
    g.roundRect(cx - side / 2, -side / 2, side, side, 4).fill({ color: rb.color || "#6e7681" });
    g.stroke({ color: "#ffffff", width: 0.75, alpha: 0.85 });
    c.addChild(g);
    if (rb.icon) {
      // 아이콘은 색 이모지 — `_makeText` 가 hasEmoji 판정으로 PIXI.Text 경로를 타 고유 색으로 렌더된다
      //   (BitmapText 는 alpha 마스크라 단색 실루엣이 됨 — graph-emoji-color 주석 참조).
      const t = this._makeText(rb.icon, { size: rb.fontSize || 12, fill: "#ffffff", weight: 400 });
      t.anchor.set(0.5, 0.5); t.position.set(cx, 0);
      c.addChild(t);
    }
    return c;
  }
  _ellipsize(t, maxW) { const s = String(t.text); let lo = 1, hi = s.length; while (lo < hi) { const mid = (lo + hi + 1) >> 1; t.text = s.slice(0, mid) + "…"; (t.width <= maxW) ? lo = mid : hi = mid - 1; } t.text = s.slice(0, lo) + "…"; }

  _applyNodeStates(c, n) {
    const states = n.states || []; if (!states.length) return;
    const P = this.P;
    const conf = this._nodeState;
    // 상태 = **테두리(halo)** — G6 원본 node.state 계약과 동일(analyzed/running 을 뱃지 dot 으로 렌더하던 회귀 수정, 사용자 리포트 2026-07-13).
    //   §18.8 B1 수정: `_metaNodeStates` 는 [match, analyzed, running, selected, dimmed] 순으로 상태를 만들고, G6 는
    //   **나중에 적용된 상태(=selected)의 stroke 가 이긴다**. 겹치는 동일-rect halo 는 나중에 페인트된(=자식 배열
    //   더 뒤) 것이 위에 보이므로, halo 를 states 순서대로 body 아래에 **증가 인덱스**로 삽입한다 → selected(마지막)가
    //   halo 중 최상위(body 직전)로 페인트되어 analyzed/running 위에서 보인다. (앞서 addChildAt(_,0) 은 순서를 뒤집어
    //   analyzed 가 selected 를 가렸음.) 인셋을 상태별로 벌려 동시 표기(concentric)도 가능케 한다 — 인셋 폭·
    //   두께·모양은 haloGeom 이 노드 크기에 비례해 산출(graph-analyzed-halo-fit).
    let hi = 0, seen = 0;   // hi=halo 삽입 인덱스(body 아래), seen=인셋 단계
    for (const st of states) {
      const sc = conf[st] || {};
      if (st === "selected" || st === "match" || st === "busy" || st === "analyzed" || st === "running") {
        const DEF = { selected: { stroke: "#161b22", lineWidth: 3 }, match: { stroke: "#e8a400", lineWidth: 2 },
          busy: { stroke: "#0a5b66", lineWidth: 3, lineDash: [2, 2] }, analyzed: { stroke: "#7b2fbe", lineWidth: 3 },
          running: { stroke: "#e08a1e", lineWidth: 2, lineDash: [4, 3] } };
        const d = DEF[st], col = sc.stroke || d.stroke, dash = sc.lineDash || d.lineDash;
        const halo = new P.Graphics();
        // graph-analyzed-halo-fit: 기하는 PixiAdapterPure.haloGeom 이 노드 모양(circle/rect)·크기에 비례해
        //   산출한다(rect 는 k=1 이라 종전 수치 그대로). `seen` = 동심링 단계(다중 상태 동시 표기).
        const G = PixiAdapterPure.haloGeom(n, seen, sc.lineWidth || d.lineWidth), lw = G.lw;
        const alpha = st === "match" ? 0.8 : 0.9;
        if (Array.isArray(dash)) {   // 점선 테두리(busy/running)
          if (G.shape === "circle") {   // 원형 4변이 없으므로 호 대시(dashArcs)로 등가 처리
            for (const [a0, a1] of PixiAdapterPure.dashArcs(G.r, dash)) halo.moveTo(Math.cos(a0) * G.r, Math.sin(a0) * G.r).arc(0, 0, G.r, a0, a1);
          } else {
            const D = PixiAdapterPure.dashSegments, rx = G.x, ry = G.y, rw = G.w, rh = G.h;
            for (const seg of [].concat(D(rx, ry, rx + rw, ry, dash), D(rx + rw, ry, rx + rw, ry + rh, dash), D(rx + rw, ry + rh, rx, ry + rh, dash), D(rx, ry + rh, rx, ry, dash))) halo.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
          }
          halo.stroke({ color: col, width: lw, alpha: 0.9 });
        } else if (G.shape === "circle") {
          halo.circle(0, 0, G.r).stroke({ color: col, width: lw, alpha });
        } else {
          halo.roundRect(G.x, G.y, G.w, G.h, G.radius).stroke({ color: col, width: lw, alpha });
        }
        c.addChildAt(halo, hi++); seen++;   // body 아래·states 순서 → selected(마지막) 최상위 halo
      }
    }
  }

  _drawCombo(c, bb) {
    const P = this.P, s = c.style || {}, cont = new P.Container();
    cont.zIndex = (s.zIndex != null ? s.zIndex : 0); cont.position.set(bb.x, bb.y);
    const g = new P.Graphics();
    g.roundRect(0, 0, bb.w, bb.h, s.radius || 12).fill({ color: s.fill || "#3f4b8c", alpha: s.fillOpacity == null ? 0.045 : s.fillOpacity });
    if (s.lineDash) { const P2 = PixiAdapterPure; const per = [[0, 0, bb.w, 0], [bb.w, 0, bb.w, bb.h], [bb.w, bb.h, 0, bb.h], [0, bb.h, 0, 0]];
      for (const [a1, b1, a2, b2] of per) for (const seg of P2.dashSegments(a1, b1, a2, b2, s.lineDash)) g.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
      g.stroke({ color: s.stroke || "#aab3c5", width: s.lineWidth || 1 }); }
    else g.roundRect(0, 0, bb.w, bb.h, s.radius || 12).stroke({ color: s.stroke || "#aab3c5", width: s.lineWidth || 1 });
    cont.addChild(g);
    if (s.labelText) { const t = this._makeText(s.labelText, { size: s.labelFontSize || 13, fill: s.labelFill || "#3f4b8c", weight: 700 }); t.anchor.set(0, 1); t.position.set(4, -4); cont.addChild(t); }
    this._objs.set(c.id, cont);
    return cont;
  }

  _drawEdge(e, a, b) { return this._paintEdge(new this.P.Graphics(), e, a, b); }
  // graph-edge-drag-perf: 주어진 Graphics 에 엣지 기하(선/대시/화살표/라벨)를 in-place 페인트. 신규(_drawEdge)와
  //   드래그 재사용(_refreshIncidentEdges) 공용. 재사용 시 g.clear()+라벨 자식 destroy 로 이전 상태를 지운다
  //   (라벨 없는 대다수 엣지는 children 비어 오버헤드 0). 신규 Graphics 는 clear/자식정리가 no-op → 종전 동작 동일.
  //   graph-edge-flow(§83): 직선 → 방향성 곡선. 세 가지가 동시에 성립한다.
  //   ① 곡률은 진행방향 왼쪽 고정 → 같은 두 객체의 읽기(테이블→루틴)와 쓰기(루틴→테이블)가 서로
  //      반대편 호로 갈라져 겹치지 않는다(관계선 2개가 자연히 분리 — 사용자 요구 ①).
  //   ② 선은 가늘고 반투명(style.strokeOpacity)이라 **겹칠수록 alpha 가 누적**돼 허브 노드 주변이
  //      점점 진해진다(요구 ②). 가닥마다 stroke() 를 개별 호출하는 이유도 이것 — 한 번에 몰아
  //      stroke 하면 자기 교차 구간이 균일해져 누적 대비가 사라진다.
  //   ③ style.strands(가닥 수)로 상위 부모가 품은 관계 수를 '다발 볼륨'으로 표현한다(요구 ③).
  //   최적화: 실선은 Pixi 네이티브 quadraticCurveTo(내부 tessellation) — 샘플링 0. 대시만 화면
  //   픽셀 기준 adaptive 샘플. 드래그 중(_lowFi)엔 1가닥·저해상도로 강등하고 dragend 에서 복원한다.
  _paintEdge(g, e, a, b) {
    const P = this.P, s = e.style || {};
    g.clear();
    if (g.children && g.children.length) { for (const ch of g.removeChildren()) { try { ch.destroy(); } catch (_) {} } }
    g.zIndex = (s.zIndex != null ? s.zIndex : 2);
    const color = s.stroke || "#cbd2db";
    const lowFi = !!this._lowFi;
    const zoom = (this._cam && this._cam.zoom) || 1;
    // §86: style.lineWidth 는 **화면 픽셀** 기준값 — 줌 정책(줌인 고정·줌아웃 비례)을 태워 model 로 환산.
    // §87: 그 결과가 1물리픽셀 미만이면 hairline 처리 — 폭은 1물리픽셀, 부족분은 alpha(fade)로.
    const dpr = (this.app && this.app.renderer && this.app.renderer.resolution)
      || (typeof window !== "undefined" && window.devicePixelRatio) || 1;
    const hair = edgeHairline(s.lineWidth || 1.4, zoom, dpr);
    const lw = hair.w;
    const alpha = (s.strokeOpacity == null ? 1 : s.strokeOpacity) * hair.fade;
    const sc = lw / (s.lineWidth || 1.4);   // 화살촉·다발 간격에 같은 정책을 태우기 위한 실효 배율
    const arc = PixiAdapterPure.edgeArc(a, b, s.curve || 0, s.curveMax, s.curveMin);
    const nStrand = lowFi ? 1 : Math.max(1, Math.min(6, (s.strands | 0) || 1));
    // 다발 간격도 화면 기준 — model 로 두면 줌아웃에서 가닥이 겹쳐 볼륨 표현이 사라진다(§85).
    const offs = nStrand > 1 ? PixiAdapterPure.strandOffsets(nStrand, (s.strandGap || 3.2) * sc) : EDGE_NO_STRAND;
    const segs = (arc.off || nStrand > 1) && s.lineDash ? PixiAdapterPure.curveSegs(arc.len, zoom, lowFi) : 0;
    let tipAng = Math.atan2(b[1] - a[1], b[0] - a[0]), tailAng = tipAng + Math.PI;
    for (let i = 0; i < offs.length; i++) {
      const o = offs[i];
      // 가닥 편차는 컨트롤 포인트에 크게(다발이 벌어짐), 끝점에는 작게(노드에서 수렴) 준다.
      const cx = arc.cx + arc.px * o * 2, cy = arc.cy + arc.py * o * 2;
      const sa = o ? [a[0] + arc.px * o * 0.35, a[1] + arc.py * o * 0.35] : a;
      const sb = o ? [b[0] + arc.px * o * 0.35, b[1] + arc.py * o * 0.35] : b;
      const curved = !!(arc.off || o);
      if (s.lineDash) {
        const pts = curved ? PixiAdapterPure.quadPoints(sa, [cx, cy], sb, segs) : [sa, sb];
        for (const seg of PixiAdapterPure.dashPolyline(pts, s.lineDash)) g.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
      } else if (curved) g.moveTo(sa[0], sa[1]).quadraticCurveTo(cx, cy, sb[0], sb[1]);
      else g.moveTo(sa[0], sa[1]).lineTo(sb[0], sb[1]);
      g.stroke({ color, width: lw, alpha });   // 가닥별 개별 stroke → 겹침 구간 alpha 누적(밀도=명시성)
      if (i === 0 && curved) { tipAng = Math.atan2(sb[1] - cy, sb[0] - cx); tailAng = Math.atan2(sa[1] - cy, sa[0] - cx); }
    }
    // 화살촉은 곡선 **끝 접선**을 따른다(직선 각도로 그리면 호와 어긋나 꺾여 보인다). 선이 얇아진
    //   만큼 촉도 작게(선 굵기 연동), 대신 alpha 는 선보다 올려 방향 가독성을 유지한다.
    //   촉 크기도 화면 기준(§85) — 줌인에서 촉만 거대해지는 리본 현상의 원인이었다.
    const headA = Math.min(1, alpha * 1.6);
    const headSz = sc * Math.max(4.5, Math.min(9, 3.6 + (s.lineWidth || 1.4) * 1.9));
    if (s.endArrow) this._arrow(g, b[0], b[1], tipAng, color, headA, headSz);
    if (s.startArrow) this._arrow(g, a[0], a[1], tailAng, color, headA, headSz);
    if (s.labelText) {
      // 라벨은 곡선 중점 Q(0.5) = (a + 2c + b)/4 — 직선 중점에 두면 호에서 떠 보인다.
      const mx = (a[0] + 2 * arc.cx + b[0]) / 4, my = (a[1] + 2 * arc.cy + b[1]) / 4;
      if (s.labelBackground) { const bg = new P.Graphics(); const tw = String(s.labelText).length * (s.labelFontSize || 9) * 0.6;
        bg.roundRect(mx - tw / 2 - 3, my - 7, tw + 6, 14, 3).fill({ color: s.labelBackgroundFill || "#f6f8fb", alpha: 0.85 }); g.addChild(bg); }
      const t = this._makeText(s.labelText, { size: s.labelFontSize || 9, fill: s.labelFill || "#64748b", weight: 400 }); t.anchor.set(0.5, 0.5); t.position.set(mx, my); g.addChild(t); }
    return g;
  }
  _arrow(g, x, y, ang, color, alpha, size) {
    const sz = size || 8, a1 = ang + Math.PI - 0.42, a2 = ang + Math.PI + 0.42;
    g.moveTo(x, y).lineTo(x + Math.cos(a1) * sz, y + Math.sin(a1) * sz).lineTo(x + Math.cos(a2) * sz, y + Math.sin(a2) * sz).closePath().fill({ color: color || "#cbd2db", alpha: alpha == null ? 1 : alpha });
  }

  // 상태 갱신 (G6 호환) — 상태 배열 변이 + 해당 노드 오브젝트만 즉시 재렌더(gap #13, 증분 경로 ctxmenu:2011).
  setElementState(id, states) {
    const n = this._built.nodes.find(x => x.id === id); if (!n) return;
    n.states = Array.isArray(states) ? states : [states];
    const old = this._objs.get(id);
    if (old && this.world) { const idx = this.world.getChildIndex(old); const fresh = this._drawNode(n); try { old.destroy({ children: true }); } catch (_) {} this.world.removeChild(old); this.world.addChildAt(fresh, Math.max(0, Math.min(idx, this.world.children.length)));
      // graph-move-anim: 이 노드가 트윈 중이면 새 오브젝트를 **현재 보이는 좌표**에 놓는다. `_drawNode` 는
      //   모델(최종) 위치로 만들므로 그대로 두면 상태 변경 순간 노드만 목적지로 점프한다(다음 프레임에
      //   재조회로 회복되지만 그 1프레임이 눈에 띈다 — codex review P1 의 잔여 깜빡임).
      { const tp = this._tweenPos, p = tp && tp.get(id); if (p) { try { fresh.position.set(p[0], p[1]); } catch (_) {} } }
      if (this._objSig) this._objSig.delete(id);   // 풀 서명 무효화(증분 갱신 — 다음 full draw 가 재계산)
      // graph-label-hover-expand: hover 중인 노드의 상태가 바뀌면 확장 카드의 halo 도 즉시 동기화한다
      //   (카드를 지우면 커서가 멎은 채 확장이 사라져 깜빡임 — 폭 유지 + 재페인트가 정답).
      if (id === this._hoverId && this._hoverCard) { try { this._hoverCard.paint(this._hoverCard.w); } catch (_) {} }
      this._render(); }
  }
  // z-index: graph-core(roleviz)는 **단일 map 인자** {id:z} 로 부른다(gap #3). (id,z) 2인자도 겸용.
  setElementZIndex(a, b) {
    if (a && typeof a === "object") { for (const id in a) { const o = this._objs.get(id); if (o) o.zIndex = a[id]; } this._render(); return; }
    const o = this._objs.get(a); if (o) { o.zIndex = b; this._render(); }
  }
  getElementZIndex(id) { const o = this._objs.get(id); return o ? (o.zIndex || 0) : 0; }   // gap #4
  getEdgeData() { return this._built.edges || []; }   // gap #5
  // 요소 절대이동 (드래그 종속 동반이동, gap #6). map {id:[x,y]} — 모델 좌표.
  translateElementTo(map, anim) {
    if (!map || typeof map !== "object") return;
    if (this._moveTween) this._stopMoveTween();   // graph-move-anim: 절대이동(드래그 종속 동반이동)도 조작 — 트윈보다 우선
    const moved = [];
    for (const id in map) {
      const p = map[id]; if (!Array.isArray(p)) continue;
      const n = this._built.nodes.find(x => x.id === id);
      if (n) { n.style.x = p[0]; n.style.y = p[1]; moved.push(id); }
      const o = this._objs.get(id); if (o) o.position.set(p[0], p[1]);
    }
    this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128);   // B1: 종속 이동 후 hit-grid 갱신
    this._scheduleEdgeRefresh(moved);   // graph-edge-follow-drag: 종속 노드(컬럼·장식) 이동 시 관계선 추종(perf: rAF 코얼레싱)
  }
  // graph-move-anim: 이 요소가 **아직 이동 중**인가. 카메라 보정(`_metaGraphKeepInView`)이 "지금 보인다"
  //   만으로 종료하지 않게 하는 신호다 — 트윈 시작 시점의 노드는 **출발(=직전에 보이던) 위치**에 있어
  //   보정이 0 으로 수렴해 즉시 끝나고, 그 뒤 트윈이 노드를 화면 밖으로 데려가면 아무도 따라가지
  //   않는다(codex review 5차 P1 — 요청의 주 시나리오가 그대로 재현되던 경로).
  //   id 생략 시 "트윈이 하나라도 살아 있는가". G6 폴백 어댑터엔 부재 → 호출측 feature-detect.
  isElementAnimating(id) {
    if (!this._moveTween) return false;
    if (id == null) return true;
    return !!(this._tweenPos && this._tweenPos.has(id));
  }
  // graph-move-anim: 사용자가 카메라를 직접 조작한 횟수. `_metaGraphKeepInView` 가 시작 시점 값을 기억했다가
  //   달라지면 추종을 그만둔다 — 펼침 직후 사용자가 팬/줌 하는데 카메라가 다시 노드 쪽으로 끌어당기면
  //   "조작이 애니메이션을 이긴다" 규칙이 깨진다(codex review 6차 P2). 프로그램 이동은 이 값을 올리지 않는다.
  getUserCameraSeq() { return this._userCamSeq || 0; }
  getPluginInstance(key) { return key === "minimap" ? (this._minimap || null) : null; }   // G6 minimap 플러그인 호환(자체 렌더)
  // detail-hover-fx: 상세 패널 하위 항목 hover 시 비커밋 강조. spec={nodes:[id],edges:[[idA,idB]],color?}.
  //   노드=bbox 강조 링, 엣지=끝점 사이 굵은 강조선(+양끝 노드 링). world-space 라 팬/줌 자동 정합.
  //   G6 폴백 어댑터엔 본 메서드가 부재 → graph-core 가 feature-detect 로 no-op(카메라 이동은 양쪽 동작).
  setHoverHighlight(spec) {
    if (!this.world || !this._hoverLayer || !this.P) return;
    const P = this.P, layer = this._hoverLayer, color = (spec && spec.color) || 0x2563eb;
    this._stopHoverFlow();   // 직전 hover 의 흐름 애니메이션 선점 종료(새 spec 이 소유권을 가져간다)
    this._clearHoverLayer();
    // §85 정책 정합: 강조선 굵기·화살촉도 **화면 픽셀** 기준 — model 고정이면 줌인에서 리본처럼 부풀고
    //   줌아웃에서 사라진다(관계선 본선은 이미 화면 기준). world.scale = zoom 이므로 px/zoom 이 model 폭.
    const zoom = Math.max(0.05, (this._cam && this._cam.zoom) || 1), k = 1 / zoom;
    const flows = [];
    for (const ent of ((spec && spec.edges) || [])) {
      // 계약: `[idA,idB]`(레거시 · 방향 미상) 또는 `{source,target,relType}`(방향·읽기/쓰기 명시).
      //   graph-edge-flow(§83 C1) 이후 같은 두 노드 사이에 읽기/쓰기가 **별개 관계선 2개**로 존재하고,
      //   REFERENCES 도 왕복(A→B / B→A)이 반대편 호로 갈라지므로, 어느 선을 가리키는지는 (방향, 종류)
      //   두 축이 결정한다. 종전엔 첫 매칭 엣지를 잡아 늘 같은 호만 강조됐다(사용자 리포트).
      const isPair = Array.isArray(ent);
      const sid = isPair ? ent[0] : (ent && ent.source), tid = isPair ? ent[1] : (ent && ent.target);
      const relType = isPair ? null : ((ent && ent.relType) || null);
      const a = this.getElementPosition(sid), b = this.getElementPosition(tid);
      if (!a || !b) continue;
      const st = (this._edgeMatchBetween(sid, tid, relType) || {}).style || {};
      const arc = PixiAdapterPure.edgeArc(a, b, st.curve || 0, st.curveMax, st.curveMin);
      // 데이터 흐름 방향 = 실제 관계선의 화살촉이 가리키는 쪽(PixiAdapterPure.flowForward 참조).
      const fwd = PixiAdapterPure.flowForward(st);
      const head = fwd ? b : a, tail = fwd ? a : b;
      const g = new P.Graphics();
      // graph-edge-flow: 실제 관계선과 **같은 호** 위에 겹쳐 그린다 — 직선으로 그리면 곡선 관계선
      //   옆을 스치는 별개 선이 되어 "어느 선을 가리키는지" 신호가 무너진다.
      const path = () => { if (arc.off) g.moveTo(a[0], a[1]).quadraticCurveTo(arc.cx, arc.cy, b[0], b[1]); else g.moveTo(a[0], a[1]).lineTo(b[0], b[1]); };
      path(); g.stroke({ color, width: 7 * k, alpha: 0.16 });   // 헤일로 — 대시 사이 구간에서도 경로가 끊겨 보이지 않게
      path(); g.stroke({ color, width: 3.2 * k, alpha: 0.9 });  // 본선
      // 방향 화살촉은 **흐름이 도착하는 끝**에. 곡선이면 그 끝의 접선을 따른다(직선 각도로 그리면 꺾여 보인다).
      const ang = arc.off
        ? (fwd ? Math.atan2(b[1] - arc.cy, b[0] - arc.cx) : Math.atan2(a[1] - arc.cy, a[0] - arc.cx))
        : Math.atan2(head[1] - tail[1], head[0] - tail[0]);
      this._arrow(g, head[0], head[1], ang, color, 0.95, 9 * k);
      layer.addChild(g);
      // 흐름 애니메이션용 샘플 폴리라인 — 흐름 방향으로 정렬해 두면 위상 부호를 한 곳에서만 다룬다.
      const segs = arc.off ? Math.max(18, Math.min(64, PixiAdapterPure.curveSegs(arc.len, zoom, false) * 3)) : 1;
      const pts = arc.off ? PixiAdapterPure.quadPoints(a, [arc.cx, arc.cy], b, segs) : [a, b];
      flows.push({ pts: fwd ? pts : pts.slice().reverse(), g: null });
    }
    for (const id of ((spec && spec.nodes) || [])) {
      const bb = this._boundsOf(id); if (!bb) continue;
      const g = new P.Graphics(), pad = 4;
      g.roundRect(bb.x - pad, bb.y - pad, bb.width + 2 * pad, bb.height + 2 * pad, 8).stroke({ color, width: 3 * k, alpha: 0.95 });
      layer.addChild(g);
    }
    if (flows.length) this._startHoverFlow(flows, color, k);
    this._render();
  }
  // ── detail-hover-flow: 강조 연결선 위 **데이터 흐름** 대시 애니메이션 ────────────────────────
  //   요청: "하이라이트 처리된 부분은 실제 데이터 흐름을 나타내는 애니메이션". 흐름 방향은 관계선의
  //   화살표 의미(읽기=테이블→루틴 / 쓰기=루틴→테이블 / 참조=선언 방향)를 그대로 따른다.
  //   render-on-demand(autoStart:false) 라 자체 rAF 로 프레임을 몰고, hover 해제·재빌드·destroy 에서 정지한다.
  //   비용 상한: hover 중 강조선(보통 1개)만 · 대시 Graphics 만 재페인트(본선·헤일로·노드 링은 정적).
  _startHoverFlow(flows, color, k) {
    const P = this.P;
    if (!P || !this._hoverLayer) return;
    for (const f of flows) { f.g = new P.Graphics(); f.g.zIndex = 1; this._hoverLayer.addChild(f.g); }
    const DASH = 9 * k, GAP = 9 * k, SPEED = 46 * k;   // 화면 기준(px/s) — 줌과 무관하게 같은 속도로 보인다
    const paint = (phase) => {
      for (const f of flows) {
        f.g.clear();
        // 위상을 **음수**로 밀면 대시가 pts[끝](=흐름 도착점) 쪽으로 흐른다.
        for (const s of PixiAdapterPure.dashPolyline(f.pts, [DASH, GAP], -phase)) f.g.moveTo(s[0], s[1]).lineTo(s[2], s[3]);
        f.g.stroke({ color: 0xffffff, width: 2.0 * k, alpha: 0.92 });
      }
    };
    // 접근성: prefers-reduced-motion 이면 흐름을 멈추고 정적 대시만 남긴다(방향은 화살촉이 유지).
    let reduced = false;
    try { reduced = !!(typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (_) {}
    paint(0);
    if (reduced || typeof requestAnimationFrame !== "function") { this._hoverFlow = { flows, raf: null }; return; }
    const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
    const state = { flows, raf: null };
    const step = () => {
      if (this._hoverFlow !== state) return;   // 새 hover/해제가 선점 — 조용히 종료(세대 토큰)
      const now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
      paint(((now - t0) / 1000) * SPEED);
      this._render();
      state.raf = requestAnimationFrame(step);
    };
    this._hoverFlow = state;
    state.raf = requestAnimationFrame(step);
  }
  _stopHoverFlow() {
    const st = this._hoverFlow;
    this._hoverFlow = null;   // 세대 무효화 — 이미 예약된 프레임은 위 가드에서 자진 종료
    if (st && st.raf != null) { try { cancelAnimationFrame(st.raf); } catch (_) {} }
  }
  // graph-edge-flow: 두 노드 사이 관계선 조회(hover 강조가 **실제 그 선**의 호·방향에 정합하도록).
  //   인접 인덱스가 있으면 O(incident). 순위: ① 방향 일치(더 강한 신호 — 왕복 REFERENCES 를 가른다)
  //   ② 그 안에서 relation_type 일치(같은 방향에 읽기/쓰기 2선이 공존하는 ROUTINE_USES 를 가른다).
  //   역방향(t→s)으로 등록된 엣지면 곡률 부호를 뒤집고 화살표 키를 교환해 (sid→tid) 프레임으로 정규화한다
  //   — 곡률은 진행방향 기준 왼쪽 고정이므로 방향을 뒤집으면 반대편 호가 된다.
  _edgeMatchBetween(sid, tid, relType) {
    const idx = this._edgeIndex;
    const arr = (idx && idx.get(sid)) || this._built.edges || [];
    const want = relType ? (relType === "write" ? "write" : "read") : null;
    const kindOf = (e) => (((e.data && e.data.relation_type) === "write") ? "write" : "read");
    let best = null, bestScore = 0;
    for (const e of arr) {
      const fwd = (e.source === sid && e.target === tid), rev = (e.source === tid && e.target === sid);
      if (!fwd && !rev) continue;
      const hit = want ? (kindOf(e) === want) : false;
      const score = (fwd ? 2 : 0) + (hit ? 1 : 0) + 1;   // 방향(2) > 종류(1), 매칭 자체 1
      if (score <= bestScore) continue;
      const st = e.style || {};
      best = fwd
        ? { style: st, reversed: false, edge: e }
        : { style: { curve: -(st.curve || 0), curveMax: st.curveMax, curveMin: st.curveMin, startArrow: st.endArrow, endArrow: st.startArrow }, reversed: true, edge: e };
      bestScore = score;
      if (score === 4 || (!want && fwd)) break;   // 최상위 매칭 — 더 볼 필요 없음
    }
    return best;
  }
  // 호환 유지(A10 계약): 스타일만 필요할 때의 얇은 래퍼.
  _edgeStyleBetween(sid, tid, relType) { const m = this._edgeMatchBetween(sid, tid, relType); return m ? m.style : null; }
  clearHoverHighlight() {
    if (!this._hoverLayer) return;
    this._stopHoverFlow();
    this._clearHoverLayer();
    this._render();
  }
  // detail-hover-flow: 오버레이 Graphics 는 **파기까지** 한다. hover 는 행마다 발생(스윕 1회에 수십 번)하고
  //   흐름 레이어가 매 hover 새 Graphics 를 만들므로, detach 만 하면 GPU 지오메트리가 누적된다
  //   (_paintEdge 의 자식 정리와 동일 어휘). 호출 전 반드시 _stopHoverFlow() — 파기된 Graphics 에
  //   프레임이 그려지지 않게.
  _clearHoverLayer() {
    if (!this._hoverLayer) return;
    for (const ch of this._hoverLayer.removeChildren()) { try { ch.destroy({ children: true }); } catch (_) {} }
  }
  // 무인자(gap #10)=컨테이너 추종, (w,h)=명시. graph-core 는 무인자로 부른다(core:1833,2090).
  resize(w, h) { if (!this.app) return; if (w == null) this._resizeToContainer(); else { this.app.renderer.resize(w, h); this._positionMinimap(); this._renderMinimapViewport(); this._repaintHoverCard(); } this._render(); }
  destroy() {
    try { if (this._tweenRaf) cancelAnimationFrame(this._tweenRaf); } catch (_) {}
    try { this._stopMoveTween(); } catch (_) {}   // graph-move-anim: 이동 트윈 rAF 정리(파기된 컨테이너 접근 차단)
    try { if (this._pendingRaf) cancelAnimationFrame(this._pendingRaf); } catch (_) {}   // graph-edge-drag-perf: 코얼레싱 rAF 정리
    try { if (this._edgeZoomRaf) cancelAnimationFrame(this._edgeZoomRaf); } catch (_) {}   // §85: 줌 재페인트 rAF 정리
    try { this._stopHoverFlow(); } catch (_) {}   // detail-hover-flow: 강조선 흐름 애니메이션 rAF 정리
    try { this._cancelHoverProbe(false); } catch (_) {}   // graph-label-hover-expand: 대기 프로브 rAF 정리
    try { this._clearLabelHover(); } catch (_) {}   // graph-label-hover-expand: 예약 타이머·트윈 rAF·카드 정리
    try { if (this._ro) this._ro.disconnect(); } catch (_) {}   // m1: ResizeObserver 정리
    try { if (this._winListeners) for (const [ev, fn] of this._winListeners) window.removeEventListener(ev, fn); } catch (_) {}   // m1: window 리스너 정리
    try { if (this.app) this.app.destroy(true, { children: true }); } catch (_) {}
    this._objs.clear(); this._handlers.clear();
  }
}

// 렌더러 팩토리 — B-late seam(_META_RENDERER)에서 G6.Graph 대신 이걸 선택.
export function createGraphRenderer(cfg) { return new PixiGraphAdapter(cfg); }
