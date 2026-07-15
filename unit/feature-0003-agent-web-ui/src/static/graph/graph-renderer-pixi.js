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

  // 노드 bbox (모델 좌표, 좌상단 기준). rect=[w,h] 중심, circle=지름 중심.
  nodeBBox(n) {
    const s = n.style || {};
    if (n.type === "circle") { const r = (typeof s.size === "number" ? s.size : 11) / 2; return { x: s.x - r, y: s.y - r, w: 2 * r, h: 2 * r }; }
    const w = Array.isArray(s.size) ? s.size[0] : (s.size || 100), h = Array.isArray(s.size) ? s.size[1] : 24;
    return { x: s.x - w / 2, y: s.y - h / 2, w, h };
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

  // edge 히트: 점-선분 거리 ≤ tol(model px)인 최근접 엣지(우클릭 컨텍스트 메뉴용, gap #12).
  hitTestEdge(mx, my, edges, posOf, tol) {
    const t = tol || 6; let best = null, bestD = t;
    for (const e of edges) {
      const a = posOf(e.source), b = posOf(e.target); if (!a || !b) continue;
      const d = this._segDist(mx, my, a[0], a[1], b[0], b[1]);
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
  nodeSig(n) { return "N|" + (n.type || "") + "|" + (n.combo || "") + "|" + JSON.stringify(n.style || {}) + "|" + ((n.states || []).join(",")); },
  edgeSig(e, a, b) { return "E|" + e.source + "|" + e.target + "|" + JSON.stringify(e.style || {}) + "|" + a[0].toFixed(1) + "," + a[1].toFixed(1) + "," + b[0].toFixed(1) + "," + b[1].toFixed(1); },
  comboSig(c, bb) { return "C|" + JSON.stringify(c.style || {}) + "|" + bb.x.toFixed(1) + "," + bb.y.toFixed(1) + "," + bb.w.toFixed(1) + "," + bb.h.toFixed(1); },
  edgeId(e) { return e.id != null ? e.id : ("__e:" + e.source + ">" + e.target); },

  // §80 BitmapText tint: "#rgb"/"#rrggbb"/number → {tint, valid}. 비-hex(rgb()/named)면 valid=false(Text 폴백 유도).
  hexToTint(hex) {
    if (typeof hex === "number") return { tint: hex, valid: true };
    const s = String(hex).trim();
    if (!/^#?[0-9a-fA-F]{3}$|^#?[0-9a-fA-F]{6}$/.test(s)) return { tint: 0xffffff, valid: false };
    const h = s.replace("#", ""); const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
    return { tint: parseInt(full, 16), valid: true };
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
    this._labelRes = Math.min((typeof window !== "undefined" ? (window.devicePixelRatio || 1) : 1) * 2, 4);
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
    this._render();
  }

  // render-on-demand: 변경 지점마다 명시 렌더(ticker autoStart:false). rAF-throttle 무관 즉시 페인트.
  _render() { if (this.app && this.app.renderer && this.world) { try { this.app.renderer.render(this.app.stage); } catch (_) {} } }
  // ── 카메라 상태 헬퍼 ──
  get _cam() { return this.world ? { zoom: this.world.scale.x, x: this.world.position.x, y: this.world.position.y } : { zoom: 1, x: 0, y: 0 }; }
  _applyCam(c) { if (!this.world) return; this.world.scale.set(c.zoom); this.world.position.set(c.x, c.y); this._renderMinimapViewport(); this._render(); this._emitTransform(); }
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
    if (n) { const b = PixiAdapterPure.nodeBBox(n); return { x: b.x, y: b.y, width: b.w, height: b.h }; }
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
      const s = scr(e); this._applyCam(PixiAdapterPure.zoomAroundCursor(this._cam, e.deltaY < 0 ? 1.12 : 0.9, s, this.zoomRange)); }, { passive: false });
    const onDown = (e) => {
      const s = scr(e);
      // 이슈#3: 미니맵 영역 클릭/드래그 = 카메라 이동(그래프 드래그·선택보다 우선).
      if (this._inMinimap(s.x, s.y)) { down = { minimap: true }; mode = "minimap"; this._minimapPanTo(s.x, s.y); return; }
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
      }
      if (mode === "pan") this._applyCam({ zoom: this._cam.zoom, x: down.ox + dx, y: down.oy + dy });
      else if (mode === "nodedrag") {
        // grabbed 요소를 델타만큼 이동(모델 좌표) — graph-core 핸들러가 종속을 translateElementTo 로 따라 옮긴다.
        const ddx = mx - down.lmx, ddy = my - down.lmy; down.lmx = mx; down.lmy = my;
        this._moveElement(down.hit.id, ddx, ddy);
        this._emitDrag("drag", down.hit, e, s, mx, my);
      }
    };
    window.addEventListener("pointermove", onMove);
    const up = (e) => {
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
    el.addEventListener("contextmenu", (e) => e.preventDefault());
    this._winListeners = [["pointermove", onMove], ["pointerup", up]];   // m1: destroy 시 정리
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
    // tier1: 실 요소(카드·테이블·GB/GH/GX·CATH/CATX 등, cat-bg 제외) — z 최상위
    const n = this._hitGrid ? PixiAdapterPure.hitTest(mx, my, this._hitGrid, this._built.nodes, (nd) => !this._isCatBg(nd)) : null;
    if (n) return n;
    // tier2: 스키마 클러스터 배경(combo) — 카테고리 밴드보다 우선
    const c = PixiAdapterPure.hitTestCombo(mx, my, this._built.combos || [], this._built.nodes || []);
    if (c) return Object.assign({ __combo: true }, c);
    // tier3: 카테고리 밴드 배경(cat-bg) — 밴드 고유 여백/헤더밖 영역 우클릭·드래그만 카테고리로
    const cb = this._hitGrid ? PixiAdapterPure.hitTest(mx, my, this._hitGrid, this._built.nodes, (nd) => this._isCatBg(nd)) : null;
    return cb || null;
  }
  _pickEdge(mx, my) { const posOf = (id) => { const p = this.getElementPosition(id); return p; }; return PixiAdapterPure.hitTestEdge(mx, my, this._built.edges || [], posOf, 6 / Math.max(0.2, this._cam.zoom)); }
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
    this._applyCam({ zoom: cam.zoom, x: vw / 2 - mx * cam.zoom, y: vh / 2 - my * cam.zoom });
  }
  // M2: graph-core 의 _metaElementDragEnable 을 G6-shape 이벤트로 호출(주입 시). 미주입이면 항상 허용.
  _elementDragEnable(hit, e) {
    const fn = this.cfg.elementDragEnable; if (typeof fn !== "function") return true;
    try { return fn({ target: { id: hit.id }, targetType: hit.__combo ? "combo" : "node", buttons: (e && e.buttons) || 1, button: (e && typeof e.button === "number") ? e.button : 0 }); } catch (_) { return true; }
  }
  _moveElement(id, ddx, ddy) {
    const n = this._built.nodes.find(x => x.id === id);
    if (n) { n.style.x += ddx; n.style.y += ddy; const o = this._objs.get(id); if (o) o.position.set(n.style.x, n.style.y); this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128); this._refreshIncidentEdges([id]); this._render(); return; }   // B1: hit-grid 재구성(이동 후 클릭 유지). graph-edge-follow-drag: 이동 노드의 관계선 즉시 추종
    // combo(스키마 배경) 드래그: 자식 노드 전체 + combo 카드 배경(자식 파생 bbox 이므로 같은 델타)을 함께 이동(M1)
    const moved = [];
    for (const cn of (this._built.nodes || [])) { if (cn.combo === id) { cn.style.x += ddx; cn.style.y += ddy; const o = this._objs.get(cn.id); if (o) o.position.set(cn.style.x, cn.style.y); moved.push(cn.id); } }
    const card = this._objs.get(id); if (card) { card.position.set(card.position.x + ddx, card.position.y + ddy); }   // M1: combo 배경 카드 추종
    this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128);   // B1
    this._refreshIncidentEdges(moved);   // graph-edge-follow-drag: 이동한 자식 노드들의 관계선 즉시 추종
    this._render();
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
  _refreshIncidentEdges(movedIds) {
    if (!this.world) return;
    const moved = (movedIds instanceof Set) ? movedIds : new Set(movedIds || []);
    if (!moved.size) return;
    for (const e of (this._built.edges || [])) {
      if (!moved.has(e.source) && !moved.has(e.target)) continue;
      const a = this.getElementPosition(e.source), b = this.getElementPosition(e.target);
      if (!a || !b) continue;
      const eid = PixiAdapterPure.edgeId(e);
      const old = this._objs.get(eid);
      if (old) { try { old.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(old); } catch (_) {} }
      const g = this._drawEdge(e, a, b);
      this.world.addChild(g); this._objs.set(eid, g);
      if (this._objSig) this._objSig.set(eid, PixiAdapterPure.edgeSig(e, a, b));
    }
  }
  // 드래그 이벤트 합성 — payload 에 target.id + buttons/button/targetType(_metaEventButtons·enable predicate 용).
  _emitDrag(phase, hit, e, s, mx, my) {
    const kind = hit.__combo ? "combo" : "node";
    const pl = this._payload(hit, s, mx, my, e);
    pl.targetType = hit.__combo ? "combo" : "node";
    pl.buttons = 1; pl.button = 0;
    this._emit(kind + ":" + phase, pl);
    // m4: 드래그 중엔 미니맵 뷰포트 사각형만 갱신(O(1)) — 콘텐츠 전량 재그림(O(N))은 dragend 로 지연.
    if (phase === "dragend") this._renderMinimap(); else if (phase === "drag") this._renderMinimapViewport();
  }
  _payload(hit, s, mx, my, e) {
    return { target: hit ? { id: hit.id, data: hit.data } : null, id: hit ? hit.id : null,
      canvas: s, client: (e ? { x: e.clientX, y: e.clientY } : s), model: { x: mx, y: my },
      buttons: (e && e.buttons) || 0, button: (e && typeof e.button === "number") ? e.button : 0 };
  }

  // ── 데이터/렌더 ──
  setData(built) { this._built = built || { nodes: [], edges: [], combos: [] }; }
  async setScene(built) { this.setData(built); await this.draw(); return this; }

  // scene diff 오브젝트 풀(후속 최적화): 매 draw 전량 destroy/recreate 대신 id+서명 기반 재사용.
  //   서명 = 렌더 기하에 영향 주는 전량(node=combo+style+states, edge=끝점+style, combo=style+bbox).
  //   서명 동일 → 재사용(skip make), 변경 → 해당 1개만 recreate, 신규 → add, 소멸 → remove. world.sortableChildren=true
  //   라 zIndex 페인트 정렬은 자동(자식 순서 무관). 선택/상태변경(기하 동일) 리빌드에서 대다수 노드 재사용 = GC↓·draw↓.
  async draw() {
    await this._ready;
    if (!this.world) return;   // 비브라우저/미배선 — no-op
    if (this._hoverLayer) this._hoverLayer.removeChildren();   // detail-hover-fx: rebuild 로 노드 좌표가 바뀌면 stale 강조 제거(hover 는 transient — 재hover 시 재도출).
    const built = this._built;
    // 끝점 위치 O(1) 조회 맵(구 O(N·E) find 제거)
    const npos = new Map();
    for (const n of (built.nodes || [])) npos.set(n.id, [n.style.x, n.style.y]);
    const pos = (id) => { if (npos.has(id)) return npos.get(id); const bb = this.getElementRenderBounds(id); return bb ? [bb.x + bb.width / 2, bb.y + bb.height / 2] : null; };
    // spec 목록 + 서명
    const specs = [];
    for (const c of (built.combos || [])) { const bb = PixiAdapterPure.comboBBox(c.id, built.nodes, (c.style || {}).padding); if (!bb) continue;
      specs.push({ id: c.id, sig: PixiAdapterPure.comboSig(c, bb), make: () => this._drawCombo(c, bb) }); }
    for (const e of (built.edges || [])) { const a = pos(e.source), b = pos(e.target); if (!a || !b) continue;
      const eid = PixiAdapterPure.edgeId(e);
      specs.push({ id: eid, sig: PixiAdapterPure.edgeSig(e, a, b), make: () => { const g = this._drawEdge(e, a, b); this._objs.set(eid, g); return g; } }); }
    for (const n of (built.nodes || [])) specs.push({ id: n.id, sig: PixiAdapterPure.nodeSig(n), make: () => this._drawNode(n) });
    // diff
    if (!this._objSig) this._objSig = new Map();
    const nextIds = new Set(); for (const sp of specs) nextIds.add(sp.id);
    for (const [id, obj] of Array.from(this._objs)) { if (!nextIds.has(id)) { try { obj.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(obj); } catch (_) {} this._objs.delete(id); this._objSig.delete(id); } }
    let reused = 0, made = 0;
    for (const sp of specs) {
      if (this._objSig.get(sp.id) === sp.sig && this._objs.has(sp.id)) { reused++; continue; }   // 서명 동일 → 재사용
      const old = this._objs.get(sp.id); if (old) { try { old.destroy({ children: true }); } catch (_) {} try { this.world.removeChild(old); } catch (_) {} }
      const obj = sp.make(); this.world.addChild(obj); this._objSig.set(sp.id, sp.sig); made++;
    }
    this._lastDrawStats = { reused, made, total: specs.length };
    this._hitGrid = PixiAdapterPure.buildHitGrid(built.nodes, 128);
    this._renderMinimap();
    this._render();
    this._emit("afterdraw", { data: { stage: "data" } });   // graph-core 는 e.data.stage 를 읽는다(gap #16)
  }

  _drawNode(n) {
    const P = this.P, s = n.style || {}, c = new P.Container();
    c.zIndex = s.zIndex || 4; c.position.set(s.x, s.y);
    const g = new P.Graphics();
    const st = { color: s.stroke || "#ffffff", width: s.lineWidth || 1 };
    // §18.8 M1: running 상태의 fill desaturate(G6 running.fillOpacity 0.45 — 앰버/주황 역할색 위에서 주황 점선 테두리
    //   위장 방지)를 어댑터에 복원. state config 의 fillOpacity 는 node.style 에 bake 안 되므로 states 로 판정해 fill alpha 적용.
    const runSc = ((n.states || []).indexOf("running") >= 0) ? (this._nodeState.running || { fillOpacity: 0.45 }) : null;
    const fillAlpha = runSc ? (runSc.fillOpacity != null ? runSc.fillOpacity : 0.45) : (s.fillOpacity == null ? 1 : s.fillOpacity);
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
    const P = this.P, size = o.size || 12, fill = o.fill || "#ffffff", weight = String(o.weight || 400);
    const engine = this.cfg.labelEngine || "bitmap";
    const col = PixiAdapterPure.hexToTint(fill);
    // bitmap 은 white-base glyph + tint 로 색을 낸다 → tint 로 표현 불가한 색(비-hex rgb()/named)은 Text 로 강등(m1).
    if (engine === "bitmap" && P.BitmapText && col.valid) {
      try {
        const b = new P.BitmapText({ text: String(text), style: { fontFamily: "system-ui, 'Segoe UI', sans-serif", fontSize: size, fill: "#ffffff", fontWeight: weight } });
        b.tint = col.tint;
        // M2: dynamic-font glyph 래스터화는 지연(첫 width/render)이라 생성 try 밖에서 throw 시 폴백 무력 →
        //   여기서 강제 measure 로 실패를 생성 시점으로 당긴다(성공하면 이후 경로 안전, 실패면 catch→Text).
        void b.width;
        return b;
      } catch (_) { /* dynamic font 래스터화 실패 → Text 폴백(아래) */ }
    }
    return new P.Text({ text: String(text), style: { fontFamily: "system-ui, 'Segoe UI', sans-serif", fontSize: size, fill: fill, fontWeight: weight }, resolution: this._labelRes });
  }

  _label(text, s) {
    const place = s.labelPlacement || "center";
    const t = this._makeText(text, { size: s.labelFontSize || 12, fill: s.labelFill || "#ffffff", weight: s.labelFontWeight || 400 });
    if (s.labelMaxWidth && t.width > s.labelMaxWidth) this._ellipsize(t, s.labelMaxWidth);
    if (place === "right") { t.anchor.set(0, 0.5); t.position.set((typeof s.size === "number" ? s.size / 2 : 6) + (s.labelOffsetX || 4), 0); }
    else if (place === "top") { t.anchor.set(0, 1); t.position.set((Array.isArray(s.size) ? -s.size[0] / 2 : 0) + 4, (Array.isArray(s.size) ? -s.size[1] / 2 : 0) - 4); }
    else t.anchor.set(0.5, 0.5);
    return t;
  }
  _ellipsize(t, maxW) { const s = String(t.text); let lo = 1, hi = s.length; while (lo < hi) { const mid = (lo + hi + 1) >> 1; t.text = s.slice(0, mid) + "…"; (t.width <= maxW) ? lo = mid : hi = mid - 1; } t.text = s.slice(0, lo) + "…"; }

  _applyNodeStates(c, n) {
    const states = n.states || []; if (!states.length) return;
    const P = this.P, s = n.style || {};
    const w = Array.isArray(s.size) ? s.size[0] : (s.size || 24), h = Array.isArray(s.size) ? s.size[1] : 24;
    const conf = this._nodeState;
    // 상태 = **테두리(halo)** — G6 원본 node.state 계약과 동일(analyzed/running 을 뱃지 dot 으로 렌더하던 회귀 수정, 사용자 리포트 2026-07-13).
    //   §18.8 B1 수정: `_metaNodeStates` 는 [match, analyzed, running, selected, dimmed] 순으로 상태를 만들고, G6 는
    //   **나중에 적용된 상태(=selected)의 stroke 가 이긴다**. 겹치는 동일-rect halo 는 나중에 페인트된(=자식 배열
    //   더 뒤) 것이 위에 보이므로, halo 를 states 순서대로 body 아래에 **증가 인덱스**로 삽입한다 → selected(마지막)가
    //   halo 중 최상위(body 직전)로 페인트되어 analyzed/running 위에서 보인다. (앞서 addChildAt(_,0) 은 순서를 뒤집어
    //   analyzed 가 selected 를 가렸음.) rect 인셋을 상태별로 2px 씩 벌려 동시 표기(concentric)도 가능케 한다.
    let hi = 0, seen = 0;   // hi=halo 삽입 인덱스(body 아래), seen=인셋 단계
    for (const st of states) {
      const sc = conf[st] || {};
      if (st === "selected" || st === "match" || st === "busy" || st === "analyzed" || st === "running") {
        const DEF = { selected: { stroke: "#161b22", lineWidth: 3 }, match: { stroke: "#e8a400", lineWidth: 2 },
          busy: { stroke: "#0a5b66", lineWidth: 3, lineDash: [2, 2] }, analyzed: { stroke: "#7b2fbe", lineWidth: 3 },
          running: { stroke: "#e08a1e", lineWidth: 2, lineDash: [4, 3] } };
        const d = DEF[st], col = sc.stroke || d.stroke, lw = sc.lineWidth || d.lineWidth, dash = sc.lineDash || d.lineDash;
        const halo = new P.Graphics();
        const inset = seen * 2;   // 다중 상태 동시 표기: 바깥으로 2px 씩 확장(concentric 링, 서로 안 가림)
        const rx = -w / 2 - 3 - inset, ry = -h / 2 - 3 - inset, rw = w + 6 + 2 * inset, rh = h + 6 + 2 * inset, rr = (s.radius || 4) + 2 + inset;
        if (Array.isArray(dash)) {   // 점선 테두리(busy/running) — rect 4변 대시
          const D = PixiAdapterPure.dashSegments;
          for (const seg of [].concat(D(rx, ry, rx + rw, ry, dash), D(rx + rw, ry, rx + rw, ry + rh, dash), D(rx + rw, ry + rh, rx, ry + rh, dash), D(rx, ry + rh, rx, ry, dash))) halo.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
          halo.stroke({ color: col, width: lw, alpha: 0.9 });
        } else {
          halo.roundRect(rx, ry, rw, rh, rr).stroke({ color: col, width: lw, alpha: st === "match" ? 0.8 : 0.9 });
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

  _drawEdge(e, a, b) {
    const P = this.P, s = e.style || {}, g = new P.Graphics();
    g.zIndex = (s.zIndex != null ? s.zIndex : 2);
    const alpha = s.strokeOpacity == null ? 1 : s.strokeOpacity;
    if (s.lineDash) { for (const seg of PixiAdapterPure.dashSegments(a[0], a[1], b[0], b[1], s.lineDash)) g.moveTo(seg[0], seg[1]).lineTo(seg[2], seg[3]);
      g.stroke({ color: s.stroke || "#cbd2db", width: s.lineWidth || 1.4, alpha }); }
    else { g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ color: s.stroke || "#cbd2db", width: s.lineWidth || 1.4, alpha }); }
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
    if (s.endArrow) this._arrow(g, b[0], b[1], ang, s.stroke, alpha);
    if (s.startArrow) this._arrow(g, a[0], a[1], ang + Math.PI, s.stroke, alpha);
    if (s.labelText) { const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      if (s.labelBackground) { const bg = new P.Graphics(); const tw = String(s.labelText).length * (s.labelFontSize || 9) * 0.6;
        bg.roundRect(mx - tw / 2 - 3, my - 7, tw + 6, 14, 3).fill({ color: s.labelBackgroundFill || "#f6f8fb", alpha: 0.85 }); g.addChild(bg); }
      const t = this._makeText(s.labelText, { size: s.labelFontSize || 9, fill: s.labelFill || "#64748b", weight: 400 }); t.anchor.set(0.5, 0.5); t.position.set(mx, my); g.addChild(t); }
    return g;
  }
  _arrow(g, x, y, ang, color, alpha) {
    const size = 8, a1 = ang + Math.PI - 0.42, a2 = ang + Math.PI + 0.42;
    g.moveTo(x, y).lineTo(x + Math.cos(a1) * size, y + Math.sin(a1) * size).lineTo(x + Math.cos(a2) * size, y + Math.sin(a2) * size).closePath().fill({ color: color || "#cbd2db", alpha: alpha == null ? 1 : alpha });
  }

  // 상태 갱신 (G6 호환) — 상태 배열 변이 + 해당 노드 오브젝트만 즉시 재렌더(gap #13, 증분 경로 ctxmenu:2011).
  setElementState(id, states) {
    const n = this._built.nodes.find(x => x.id === id); if (!n) return;
    n.states = Array.isArray(states) ? states : [states];
    const old = this._objs.get(id);
    if (old && this.world) { const idx = this.world.getChildIndex(old); const fresh = this._drawNode(n); try { old.destroy({ children: true }); } catch (_) {} this.world.removeChild(old); this.world.addChildAt(fresh, Math.max(0, Math.min(idx, this.world.children.length)));
      if (this._objSig) this._objSig.delete(id);   // 풀 서명 무효화(증분 갱신 — 다음 full draw 가 재계산)
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
    const moved = [];
    for (const id in map) {
      const p = map[id]; if (!Array.isArray(p)) continue;
      const n = this._built.nodes.find(x => x.id === id);
      if (n) { n.style.x = p[0]; n.style.y = p[1]; moved.push(id); }
      const o = this._objs.get(id); if (o) o.position.set(p[0], p[1]);
    }
    this._hitGrid = PixiAdapterPure.buildHitGrid(this._built.nodes, 128);   // B1: 종속 이동 후 hit-grid 갱신
    this._refreshIncidentEdges(moved);   // graph-edge-follow-drag: 종속 노드(컬럼·장식) 이동 시 관계선 추종
    this._render();
  }
  getPluginInstance(key) { return key === "minimap" ? (this._minimap || null) : null; }   // G6 minimap 플러그인 호환(자체 렌더)
  // detail-hover-fx: 상세 패널 하위 항목 hover 시 비커밋 강조. spec={nodes:[id],edges:[[idA,idB]],color?}.
  //   노드=bbox 강조 링, 엣지=끝점 사이 굵은 강조선(+양끝 노드 링). world-space 라 팬/줌 자동 정합.
  //   G6 폴백 어댑터엔 본 메서드가 부재 → graph-core 가 feature-detect 로 no-op(카메라 이동은 양쪽 동작).
  setHoverHighlight(spec) {
    if (!this.world || !this._hoverLayer || !this.P) return;
    const P = this.P, layer = this._hoverLayer, color = (spec && spec.color) || 0x2563eb;
    layer.removeChildren();
    for (const pair of ((spec && spec.edges) || [])) {
      const a = this.getElementPosition(pair[0]), b = this.getElementPosition(pair[1]);
      if (!a || !b) continue;
      const g = new P.Graphics();
      g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ color, width: 3.5, alpha: 0.95 });
      // 방향 화살촉(끝점 b) — 어느 쪽으로 이어지는 연결인지 명확화.
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      this._arrow(g, b[0], b[1], ang, color, 0.95);
      layer.addChild(g);
    }
    for (const id of ((spec && spec.nodes) || [])) {
      const bb = this._boundsOf(id); if (!bb) continue;
      const g = new P.Graphics(), pad = 4;
      g.roundRect(bb.x - pad, bb.y - pad, bb.width + 2 * pad, bb.height + 2 * pad, 8).stroke({ color, width: 3, alpha: 0.95 });
      layer.addChild(g);
    }
    this._render();
  }
  clearHoverHighlight() {
    if (!this._hoverLayer) return;
    this._hoverLayer.removeChildren();
    this._render();
  }
  // 무인자(gap #10)=컨테이너 추종, (w,h)=명시. graph-core 는 무인자로 부른다(core:1833,2090).
  resize(w, h) { if (!this.app) return; if (w == null) this._resizeToContainer(); else { this.app.renderer.resize(w, h); this._positionMinimap(); this._renderMinimapViewport(); } this._render(); }
  destroy() {
    try { if (this._tweenRaf) cancelAnimationFrame(this._tweenRaf); } catch (_) {}
    try { if (this._ro) this._ro.disconnect(); } catch (_) {}   // m1: ResizeObserver 정리
    try { if (this._winListeners) for (const [ev, fn] of this._winListeners) window.removeEventListener(ev, fn); } catch (_) {}   // m1: window 리스너 정리
    try { if (this.app) this.app.destroy(true, { children: true }); } catch (_) {}
    this._objs.clear(); this._handlers.clear();
  }
}

// 렌더러 팩토리 — B-late seam(_META_RENDERER)에서 G6.Graph 대신 이걸 선택.
export function createGraphRenderer(cfg) { return new PixiGraphAdapter(cfg); }
