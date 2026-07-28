// ITEM-09 batch3 — graph.js L3192~L5414 pure move: graph-ctxmenu: 우클릭 상호작용·상세/관계 패널.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { adminState, apiFetch, can, showToast } from "../admin.js?v=dev";
import { _META_SEARCH_CAP, _META_TERMS_COMBO, _metaComboName, _metaGraph, _metaNatSort, _metaSchemaComboOf } from "./graph-state.js?v=dev";
import { _META_ROLE, _metaFocusAdjacency, _metaFocusKeyFor, _metaRoleChipHTML, _metaRoleOf } from "./graph-roleviz.js?v=dev";
import { _metaApplyState, _metaCacheSig, _metaSetBusy, _metaSigRole, _metaStateSig, _metaYieldPaint } from "./graph-util.js?v=dev";
import { _metaRelAdjacency } from "./graph-rellayout.js?v=dev";
import { _metaSimGroups } from "./graph-simgroups.js?v=dev";
import { _META_GRAPH_COLOR, _META_LABEL_KO, _metaAncestorKindKo, _metaCatParent, _metaG6Apply, _metaGraphAnimateFocus, _metaGraphClearHoverHighlight, _metaGraphFitClamped, _metaGraphHoverPan, _metaGraphHoverPanCancel, _metaGraphLoadRoots, _metaGraphResetModel, _metaGraphSetHoverHighlight, _metaGraphStatus, _metaRenderedAncestorFor, _metaRenderedIdFor, _metaRoutineIcon, _metaRoutineKo, _metaRoutineParamList } from "./graph-core.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)

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
  // graph-analyze-perm(Critical §12.3, 2026-07-14): AI 능동 분석 실행은 metadata.graph.analyze 게이트 —
  //   미보유 시 메뉴 항목 미노출(요청: 권한 없으면 버튼 UI 미표시). 실 거부는 백엔드 403 이 최종 경계.
  if ((typeof can === "function") && can("metadata.graph.analyze")) {
    items.push({
      // graph-funcproc(REQ ④): '재분석' 라벨 제거 — 능동 분석 재실행이 곧 재분석(UX 중복 정리).
      icon: "✨", label: "AI 능동 분석", hint: "관련 노드 자동 분석 · 상세 패널 버튼 hover 로 지침 입력",
      // 상세 카드를 먼저 열어 AI box 에 진행이 보이게 한 뒤 트리거(ShowDetail 은 내부 catch 라 항상 resolve).
      // §18.8 패널(MINOR): ctxmenu 경로는 지침 미전송 — 이전 노드의 stale 지침이 화면 표시 없이 암묵
      // 적용되는 것을 차단. 지침은 popover(입력이 눈에 보이는 경로)로만 전송한다.
      onClick: () => { _metaGraphShowDetail(key).then(() => _metaGraphAnalyze(key, scope)); },
    });
  }
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
  // graph-analyze-perm(Critical §12.3, 2026-07-14): metadata.graph.analyze 게이트 — 미보유 시 미노출.
  if ((typeof can === "function") && can("metadata.graph.analyze")) {
    items.push({ icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(schemaKey) });
  }
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
    // graph-analyze-perm(Critical §12.3, 2026-07-14): metadata.graph.analyze 게이트 — 미보유 시 미노출.
    (isTerms || !((typeof can === "function") && can("metadata.graph.analyze"))) ? null : { icon: "✨", label: "DB 전체 AI 능동 분석", hint: "미분석 테이블·함수·프로시저", onClick: () => _metaGraphAnalyzeSchema(comboId) },
    isTerms ? null : { icon: "📑", label: "스키마명 복사", onClick: () => _metaGraphCopyText(name) },
  ], x, y);
}

// graph-category(§55 A): 제품 카테고리 밴드(CAT:/CATH:/CATX:) 우클릭 메뉴 — 밴드는 합성 요소(모델 노드 아님)라
//   노드/클러스터(combo) 메뉴가 부적합하다. 이전 node:contextmenu 는 _metaGraphCtxHide() stopgap 으로 숨겼고
//   (그 이전 배포본은 hit-test 가 combo 로 fall-through 해 "스키마 클러스터" 메뉴가 오노출됐다), 이제 카테고리
//   전용 액션(상세·접기/펼치기·복사)만 노출한다. catKey = cat.key(예: "PC:<id>" / "PC:__none__").
function _metaGraphCtxForCategory(catKey, x, y) {
  if (!catKey) { _metaGraphCtxHide(); return; }
  const label = _metaGraph.catLabelOf.get(catKey) || (catKey === "PC:__none__" ? "미분류" : catKey);
  const collapsed = _metaGraph.catCollapsed.has(catKey);
  const members = _metaGraph.catMembers.get(catKey) || [];
  _metaGraphCtxShow([
    { head: true, badge: "카테고리", badgeColor: "#8a5a1f", label: label },
    { icon: "🗂", label: "카테고리 상세", hint: `제품 정보 · 멤버 DB ${members.length}개`, onClick: () => _metaGraphShowCategoryDetail(catKey) },
    { icon: collapsed ? "▸" : "▾", label: collapsed ? "펼치기 (밴드)" : "접기 (밴드)", hint: "멤버 스키마 클러스터 표시/숨김", onClick: () => {
      if (_metaGraph.catCollapsed.has(catKey)) _metaGraph.catCollapsed.delete(catKey);
      else _metaGraph.catCollapsed.add(catKey);
      _metaG6Apply(false);
    } },
    { icon: "📑", label: "카테고리명 복사", onClick: () => _metaGraphCopyText(label) },
  ], x, y);
}

// graph-content-category(band-wins 철회 2026-07-15): 컨텐츠 카테고리 = 스키마 클러스터 **내부** sim-group
//   (유사 테이블 그룹 — 이름 affix 가족 = "컨텐츠 신호"로 내부 노드를 묶은 클러스터, graph-simgroups). GB/GH/GX 우클릭 전용.
//   그래프 3층 우클릭 대상 중 세 번째: ①제품 카테고리 밴드(cat-bg, 제품 단위)=카테고리 메뉴 · ②스키마 클러스터(combo, DB 단위)=스키마 메뉴
//   · ③컨텐츠 카테고리(sim-group)=이 메뉴. 사용자 정정("제품 카테고리 밴드↔컨텐츠 카테고리 착각") 반영 — 각 대상이 자기 메뉴로 정합.
//   gk = groupKey(형식 "<schemaKey>\u0001<token>"). 그룹 label/멤버수는 build 시 _metaGraph.groupInfo 에 적재(카테고리의 catLabelOf 동형).
function _metaGraphCtxForContentCategory(gk, x, y) {
  if (!gk) { _metaGraphCtxHide(); return; }
  const key = String(gk);
  const sep = key.indexOf("\u0001");
  const schemaKey = sep >= 0 ? key.slice(0, sep) : null;
  const info = _metaGraph.groupInfo && _metaGraph.groupInfo.get(key);
  const label = (info && info.label) || (sep >= 0 ? key.slice(sep + 1) : key);   // groupInfo miss 시 token 폴백
  const cnt = (info && typeof info.n === "number") ? info.n : ((_metaGraph.groupMembers.get(key) || []).length || null);
  const collapsed = _metaGraph.groupCollapsed.has(key);
  const items = [
    { head: true, badge: "컨텐츠 카테고리", badgeColor: "#8a3f7a", label: cnt != null ? `${label} · 테이블 ${cnt}` : label },
  ];
  // 소속 스키마 상세(멤버 테이블 목록) — GB/GH 좌클릭 파리티(_metaGraphShowClusterDetailById). sim-group 은 스키마의 부분집합이라 소속 스키마로 앵커.
  //   graph-catcluster-scroll: 좌클릭과 동일하게 **이 컨텐츠 카테고리 위치로 목록 스크롤**(fam = 구분자 뒤).
  if (schemaKey) items.push({ icon: "📋", label: "소속 스키마 상세", hint: "이 카테고리 위치로 목록 이동", onClick: () => _metaGraphShowClusterDetailById(schemaKey, key.slice(sep + 1)) });
  // 컨텐츠 묶음 접기/펼치기 — GX 컨트롤 좌클릭과 동일 경로(groupCollapsed 토글 + _metaG6Apply). 지속 의도라 검색 시만 build 가 강제 펼침.
  items.push({ icon: collapsed ? "▸" : "▾", label: collapsed ? "펼치기 (묶음)" : "접기 (묶음)", hint: "컨텐츠 묶음 멤버 표시/숨김", onClick: () => {
    if (_metaGraph.groupCollapsed.has(key)) _metaGraph.groupCollapsed.delete(key);
    else _metaGraph.groupCollapsed.add(key);
    _metaG6Apply(false);
  } });
  items.push({ icon: "📑", label: "묶음명 복사", onClick: () => _metaGraphCopyText(label) });
  _metaGraphCtxShow(items, x, y);
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
    // graph-search-detail: 검색어가 비면 상세 패널의 검색결과 뷰만 해제(사용자가 결과를 클릭해 노드
    //   상세로 들어간 경우는 마커 부재라 보존). 노드 상세/클러스터 상세 렌더는 마커를 만들지 않는다.
    if (document.getElementById("metaGraphSearchResults")) _metaGraphRenderDetailEmpty();
    if (_metaGraph._searchGroupCollapsed) _metaGraph._searchGroupCollapsed.clear();   // graph-search-groups: 접힘 상태 초기화
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
  // graph-search-detail: 검색어 갱신 시 상세 패널에 검색 결과 구성(스키마 클러스터→컨텐츠 카테고리 2단 접기, 클릭 → 상세).
  _metaGraphRenderSearchResults(data.nodes, q);
  _metaGraphRecordSearch(q, data.nodes);   // graph-search-groups(item2): 검색을 방문 이력에 편입(뒤로/앞으로).
  // §54③: preserve 시 첫 매칭 렌더 노드로 부드러운 팬(fit 없이) — 하이라이트 가시화.
  if (preserve && matchNodes.size) {
    const first = Array.from(matchNodes).find((k) => _metaRenderedIdFor(k));
    if (first) _metaGraphAnimateFocus(first, seq);
  }
  // item3(단순명료): 상태줄은 "질의 — N건" + 필요 시 짧은 실행가능 힌트만(상한/숨김 필터). 자세한 설명은 패널 그룹 구조가 대신.
  const capNote = _metaGraph.searchCapped ? " · 상한(검색어를 좁혀보세요)" : "";
  const anyHiddenRoutineMatch = (data.nodes || []).some((nd) => nd && nd.label === "Routine"
    && _metaGraph.hiddenKinds.has((nd.routine_type === "function") ? "function" : "procedure"));
  const hiddenNote = anyHiddenRoutineMatch ? " · 함수/프로시저 일부 숨김(ƒ/⚙ 토글)" : "";
  if (!nRaw) _metaGraphStatus("검색 결과 없음.");
  else _metaGraphStatus(`'${q}' — ${nRaw}건${capNote}${hiddenNote}`);
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
// graph-detail-scroll: 상세 패널 스크롤 컨테이너 = aside.admin-meta-graph-detail(overflow-y:auto).
//   렌더 함수는 자식 #metadataGraphDetailBody 의 innerHTML 만 교체하므로 aside 의 scrollTop 은
//   프레임 자체엔 살아있지만, 화면(이력 항목)마다 콘텐츠 높이가 달라 이전 위치가 clamp/유실된다.
//   → 이력 항목별로 scrollTop 을 스냅샷·복원해 뒤로/앞으로 시 보던 위치를 되살린다.
function _metaGraphDetailScrollEl() {
  return document.getElementById("metadataGraphDetail");   // #metadataGraphDetailBody(내용)이 아닌 스크롤 aside
}
// 현재 이력 항목에 스크롤 위치를 스냅샷(현 화면을 떠나기 직전 — 새 방문 push 또는 뒤로/앞으로 이동 전).
//   _histNavBusy(네비 렌더 in-flight)면 스킵 — 패널 콘텐츠가 아직 이전 화면이라 현 항목에 남의 scrollTop 을
//   기록하는 오정합(연타)을 방지한다.
function _metaGraphHistoryCaptureScroll() {
  if (_metaGraph._histNavBusy) return;
  const cur = _metaGraph.detailHist[_metaGraph.detailHistIdx];
  if (!cur) return;                                        // 비어 있음(-1) — 스냅샷 대상 없음
  const el = _metaGraphDetailScrollEl();
  if (el) cur.scroll = el.scrollTop;
}
// 대상 이력 항목의 스크롤 위치를 복원(대상 화면 렌더 완료 후). 미저장이면 0(맨 위).
//   rAF 로 다음 프레임에 적용 — 교체된 (동기) 콘텐츠 높이가 레이아웃에 반영된 뒤 설정해 clamp 회피.
//   노드 상세는 AI 박스(_metaGraphLoadNodeAnalysis)가 async 로 나중에 높이를 키우므로, 목표를
//   _pendingDetailScroll{key,top} 로 남겨 그 박스가 로드된 뒤 1회 재적용(하단부 복원)한다.
function _metaGraphHistoryRestoreScroll(ent) {
  const el = _metaGraphDetailScrollEl();
  if (!el) return;
  const top = (ent && typeof ent.scroll === "number") ? ent.scroll : 0;
  _metaGraph._pendingDetailScroll = (ent && ent.v === "node") ? { key: ent.k, top } : null;
  requestAnimationFrame(() => { try { el.scrollTop = top; } catch (_) {} });
}
// graph-detail-scroll(m3): 노드 상세 AI 박스가 async 로 로드돼 패널이 커진 직후, 진행 중인 복원 목표를
//   1회 재적용한다(첫 rAF 복원이 짧은 콘텐츠로 clamp 됐던 하단부를 되살림). key 일치 시에만 — 다른 화면
//   렌더의 AI 로드가 남의 스크롤을 건드리지 않게. 재적용 후 소진(1회성).
function _metaGraphReapplyPendingScroll(key) {
  const p = _metaGraph._pendingDetailScroll;
  if (!p || p.key !== key) return;
  _metaGraph._pendingDetailScroll = null;
  const el = _metaGraphDetailScrollEl();
  if (el) requestAnimationFrame(() => { try { el.scrollTop = p.top; } catch (_) {} });
}
function _metaGraphHistoryRecord(key, view) {
  if (!key || _metaGraph._histNav) return;              // 뒤로/앞으로 네비 중 재기록 금지
  const v = view || "node";
  const h = _metaGraph.detailHist;
  const cur = h[_metaGraph.detailHistIdx];
  if (cur && cur.k === key && cur.v === v) return;      // 같은 화면 연속 재선택 — 중복 억제
  _metaGraphHistoryCaptureScroll();                     // graph-detail-scroll: 현 화면 스크롤 스냅샷(새 방문으로 떠나기 전)
  h.splice(_metaGraph.detailHistIdx + 1);               // 앞으로 분기 절단(새 방문이 forward 이력을 덮음)
  h.push({ v, k: key });
  if (h.length > _META_HIST_CAP) h.shift();             // 상한 초과 시 오래된 앞부분 제거
  _metaGraph.detailHistIdx = h.length - 1;
  _metaGraphHistoryUpdateUI();
}
// graph-search-groups(item2): 검색을 방문 이력에 편입 — 노드/클러스터/관계 상세처럼 뒤로/앞으로로 되돌아온다.
//   키스트로크마다 새 항목을 쌓지 않도록, 이력 top 이 이미 검색 항목이면 in-place 갱신(질의·결과 교체).
//   결과 노드를 항목에 캐시해 복원 시 재fetch 없이 패널만 재구성. finding#5(검색뷰 스크롤 오스냅샷)도 검색이
//   자기 이력 항목이 됨으로써 자연 해소(스크롤 캡처는 항상 현재 화면=현재 항목에 정합).
function _metaGraphRecordSearch(q, nodes) {
  if (_metaGraph._histNav) return;
  const h = _metaGraph.detailHist;
  const cur = h[_metaGraph.detailHistIdx];
  if (cur && cur.v === "search") {
    cur.k = q; cur.nodes = nodes;
    // C1: 뒤로로 검색 항목에 돌아와 질의를 수정하면 질의 문맥이 바뀌므로 forward(구 문맥 노드 등)를 절단
    //   (노드/클러스터 경로의 새 방문 절단과 동형). top 에서의 in-place 갱신은 splice no-op.
    if (_metaGraph.detailHistIdx < h.length - 1) h.splice(_metaGraph.detailHistIdx + 1);
    _metaGraphHistoryUpdateUI();
    return;
  }
  _metaGraphHistoryCaptureScroll();                     // 떠나는(비-검색) 화면 스크롤 스냅샷
  h.splice(_metaGraph.detailHistIdx + 1);
  h.push({ v: "search", k: q, nodes });
  if (h.length > _META_HIST_CAP) h.shift();
  _metaGraph.detailHistIdx = h.length - 1;
  _metaGraphHistoryUpdateUI();
}
// 검색 이력 항목 복원 — 재fetch 없이 입력값만 세팅(input 이벤트 미발화=재검색 트리거 없음) + 캐시 노드로 결과 재구성.
//   P1: 검색 컨텍스트 상태(mode·searchMatchNodes)도 복원해, 이후 검색어 클리어 판정(mode/searchMatchNodes 의존)이
//   드리프트하지 않게 한다(캔버스 앰버 글로우 재적용은 back-nav 재렌더 비용 회피 위해 생략 — 상태만 정합).
function _metaGraphRestoreSearch(ent) {
  const s = document.getElementById("metadataGraphSearch");
  if (s) s.value = ent.k || "";
  _metaGraph.lastQuery = ent.k || "";
  _metaGraph.mode = "search";
  _metaGraph.searchMatchNodes = new Set((ent.nodes || []).map((n) => n && n.key).filter(Boolean));
  _metaGraphRenderSearchResults(ent.nodes || [], ent.k || "");
}
async function _metaGraphHistoryGo(dir) {
  const ni = _metaGraph.detailHistIdx + dir;
  if (ni < 0 || ni >= _metaGraph.detailHist.length) return;
  _metaGraphHistoryCaptureScroll();                     // graph-detail-scroll: 떠나는 화면 스크롤 스냅샷(idx 변경·busy 세팅 전)
  _metaGraph._histNavBusy = true;                       // 이후 캡처 스킵(연타 시 in-flight 화면에 오정합 방지, m4)
  _metaGraph.detailHistIdx = ni;
  const ent = _metaGraph.detailHist[ni];
  // 클러스터 복원은 반드시 ById — Local 은 모델-로컬이라 중심보기(resetModel) 후 빈 목록을 렌더.
  _metaGraph._histNav = true;                           // 각 show 함수의 Record(첫 await 이전 동기 구간)가 재기록하지 않게
  const p = (ent.v === "cluster") ? _metaGraphShowClusterDetailById(ent.k)
    : (ent.v === "rel") ? _metaGraphShowRelations(ent.k)
      : (ent.v === "search") ? Promise.resolve(_metaGraphRestoreSearch(ent))
        : _metaGraphShowDetail(ent.k);
  _metaGraph._histNav = false;                          // M1: 억제창을 show 동기 접두부로 한정(Record 는 위 호출에서 이미 실행·억제).
                                                        //   전체 await 동안 유지하면 네비 중 사용자 클릭이 이력에서 누락되는 회귀.
  const seq = _metaGraph._opSeq;                        // await 이전 캡처(세대 가드 보존)
  try { await p; }                                      // 렌더 완료 대기(스크롤 복원 타이밍)
  catch (_) { /* m2: 렌더 예외(fetch 흡수 외 DOM 조립 throw)를 삼켜 아래 tail 을 항상 실행 */ }
  _metaGraph._histNavBusy = false;
  _metaGraphHistoryRestoreScroll(ent);                  // graph-detail-scroll: 대상 화면 스크롤 복원(렌더 완료 후)
  // 카메라 재현(fire-and-forget) — 미렌더(접힘/모델 제거)면 skip, 패널은 API 재조회로 복원됨.
  //   P2: search 항목의 ent.k 는 질의문자열이라 노드 focus 대상 아님(우연히 렌더 id 와 일치 시 오팬 방지).
  if (ent.v !== "search" && _metaRenderedIdFor(ent.k)) _metaGraphAnimateFocus(ent.k, seq);
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
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || [], { truncated: !!data.truncated });
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
  const focusEl = direct || _metaRenderedAncestorFor(targetKey);   // 미렌더 시 테이블→컨텐츠 카테고리→스키마→제품 카테고리 순 승격
  if (!focusEl) { _metaGraphStatus("대상이 아직 화면에 로드되지 않았습니다 — 더블클릭하면 펼쳐 상세로 전환합니다."); return; }
  // 선택은 대상(컬럼/테이블) 키 기준. (a) 자기 자신이 렌더됐거나 (b) 미렌더 컬럼이 소속 테이블/카드로 승격된 경우
  //   대상 키를 선택 — 펼쳐 렌더돼 있으면 노드 하이라이트, 미렌더면 선택 상태만 기록 + 하이라이트는 소속 테이블
  //   폴백(_metaGraphSetSelected). 접힌 스키마 카드(SC:)로만 승격된 경우(대상=스키마)는 기존대로 선택 없이 팬만.
  const renderedSelf = _metaGraph.renderedIds && _metaGraph.renderedIds.has(targetKey);
  if (renderedSelf || !direct) _metaGraphSetSelected(targetKey);
  const seq = _metaGraph._opSeq;
  _metaGraphAnimateFocus(focusEl, seq);   // 승격된 렌더 요소(노드/카드) 내부 해소 후 카메라 팬
  const nm = (_metaGraph.nodes.get(targetKey) || {}).name || _metaKeyDisplayNode(targetKey).name || targetKey;
  // graph-catcluster-focus: 승격 안내는 **실제 승격 대상**을 명시한다(종전 "소속 테이블" 단정은 컨텐츠
  //   카테고리·스키마 클러스터·제품 카테고리로 갔을 때 오안내였다).
  _metaGraphStatus(direct
    ? `→ ${nm} 로 카메라 이동 (더블클릭 = 상세 패널 전환).`
    : `→ ${nm} 의 ${_metaAncestorKindKo(focusEl)}로 카메라 이동 · 선택됨 (더블클릭 = 펼쳐 상세 전환).`);
}
// graph-node-reveal(사용자 요구 2026-07-23): 대상 노드가 화면에 없을 때 **차단하지 않고 부모 체인을
//   활성화(펼침)** 해 노출한다. 노드 계층은 `scope:schema.table.column` — 렌더 게이트는 두 Set:
//   schemaExpanded(접힌 스키마 카드 SC:↔combo)·expanded(테이블 컬럼). 소속 스키마를 펼치고
//   (_metaGraphExpandSchema — 테이블·함수 Routine 로드), 컬럼이면 소속 테이블의 컬럼도 펼친다
//   (_metaGraphToggleColumns). 두 확장 함수는 각각 _opSeq bump·busy·fetch 를 관리하는 기존 async op
//   이므로 순차 await(경합 없음 — 앞 op 가 완주한 뒤 뒤 op 시작). 반환: 활성화 후 노드가 렌더됐으면
//   true, 아니면 false(호출측이 조상 승격 폴백 처리).
//   scope 가드 — _metaGraphExpandSchema 는 현재 scope(데이터소스) 소속 스키마만 펼친다(교차-scope
//   fetch 오염 방지, 그 함수 내부 가드와 동형). 타 데이터소스 노드는 여기서 false 를 반환해 조상
//   승격/검색 유도로 위임한다.
// 재진입 가드(리뷰 REV-20260723T083434 #1): 버튼 핸들러가 async 라 확장 fetch 대기 중 연타하면
//   _metaGraphToggleColumns 는 in-flight 가드가 없어(colsByTable 는 ingest 후에야 채워짐) 중복
//   /columns fetch + 같은 seq 이중 팬이 발생할 수 있다. 모듈 플래그로 진행 중 재진입을 차단한다.
let _metaGraphFocusSelBusy = false;
async function _metaGraphRevealNode(key) {
  if (!_metaGraph.graph || !key) return false;
  if (_metaRenderedIdFor(key)) return true;   // 이미 렌더(자신 또는 SC: 카드) — 활성화 불필요
  const gn = _metaGraph.nodes.get(key);
  const fqn = gn && gn.fqn;
  const cidx = key.indexOf(":");
  const kscope = cidx >= 0 ? key.slice(0, cidx) : "";
  if (!kscope || kscope !== (adminState.metadata.scopeKey || "")) return false;   // 타 데이터소스 — 펼침 불가
  // 1) 소속 스키마 펼치기 — 접힌 카드(SC:)를 combo 로 전환, 테이블·함수(Routine) 로드.
  const sc = _metaCatParent(key, fqn);
  if (sc && !_metaGraph.schemaExpanded.has(sc)) {
    await _metaGraphExpandSchema(sc);
    if (_metaRenderedIdFor(key)) return true;   // 테이블·함수면 스키마 펼침만으로 렌더됨
  }
  // 2) 컬럼이면 소속 테이블의 컬럼 펼치기(테이블 노드는 위 스키마 펼침으로 이미 렌더돼 있음).
  const tk = _metaColParent(key, fqn);
  if (tk && tk !== key && !_metaTableHasCols(tk)) {
    await _metaGraphToggleColumns(tk);   // 비-Table 이면 내부 label 가드로 no-op(무해)
  }
  return !!_metaRenderedIdFor(key);
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

// ── detail-hover-fx: 상세 패널 하위 항목 hover 시각 효과 바인딩(비커밋 — 클릭 라우팅과 독립·병존) ──
//   사용자 요청: 하위 항목 hover 시 시각적 명확성 부여. mouseenter/leave + focus/blur(키보드 파리티).
//   pan=카메라 이동(intent 지연·leave 취소), highlight=캔버스 오버레이 강조(leave 시 해제). 렌더러 미지원
//   (G6 폴백)이면 하이라이트는 no-op, 카메라는 동작. 클릭/더블클릭(선택·추적)은 기존 바인딩이 그대로 담당.
function _metaBindHoverPan(row, key) {
  if (!row || !key) return;
  const on = () => _metaGraphHoverPan(key);
  const off = () => _metaGraphHoverPanCancel();
  row.addEventListener("mouseenter", on);
  row.addEventListener("mouseleave", off);
  row.addEventListener("focus", on);
  row.addEventListener("blur", off);
}
function _metaBindHoverHighlight(row, spec) {
  if (!row || !spec) return;
  const on = () => _metaGraphSetHoverHighlight(spec);
  const off = () => _metaGraphClearHoverHighlight();
  row.addEventListener("mouseenter", on);
  row.addEventListener("mouseleave", off);
  row.addEventListener("focus", on);
  row.addEventListener("blur", off);
}
// 상세 패널 컨테이너 전체에 hover 강조 바인딩(공용): 컬럼 선택=노드 강조, 참조/사용 행=연결선 강조.
//   selfKey 는 ROUTINE_USES(data-rtuse) 의 self 끝점 폴백. 참조 행(.amgr-trace)·관계 행(.amgr-row[data-key])은
//   data-edge-self 를 self 끝점으로(없으면 selfKey) 사용 — 컬럼 단위 FK 도 정확한 연결선을 강조한다.
function _metaGraphBindDetailHover(el, selfKey) {
  if (!el) return;
  el.querySelectorAll(".amgr-col-select[data-col]").forEach((b) => {
    _metaBindHoverHighlight(b, { nodeKeys: [b.getAttribute("data-col")] });
  });
  el.querySelectorAll(".amgr-trace[data-trace]").forEach((r) => {
    _metaBindHoverHighlight(r, { edgeKeyPairs: [[r.getAttribute("data-edge-self") || selfKey, r.getAttribute("data-trace")]] });
  });
  el.querySelectorAll("[data-rtuse]").forEach((b) => {
    _metaBindHoverHighlight(b, { edgeKeyPairs: [[b.getAttribute("data-edge-self") || selfKey, b.getAttribute("data-rtuse")]] });
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
  // graph-funcproc(cluster-detail-routines): 함수·프로시저(Routine)도 소속 클러스터의 컨텐츠 카테고리 목록에
  //   포함한다 — build(graph-core §64 `g.tables`)가 Table+Routine 을 함께 sim-group 화하므로, 패널이 Table 만
  //   집계하면 함수·프로시저만 있는 컨텐츠 카테고리(예: "상점 아이템 명칭")가 캔버스엔 보여도 목록에서 누락된다.
  //   membership 판정은 _metaSchemaComboOf(Routine)==_metaCatParent(...) 와 동일 predicate 라 테이블과 정합.
  //   kind 필터(hiddenKinds, §54②) 도 build(graph-core L74-75)와 동형으로 적용 — 사용자가 'ƒ 함수'/'⚙ 프로시저'
  //   를 숨기면 캔버스에서 빠진 routine 이 패널에도 안 나와 sim-group·목록이 캔버스와 계속 일치한다.
  const routines = [];
  let childCols = 0;
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n);
    else if (n.label === "Routine" && _metaCatParent(n.key, n.fqn) === comboId && !_metaGraph.hiddenKinds.has((n.routine_type === "function") ? "function" : "procedure")) routines.push(n);
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  tables.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  routines.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const snode = _metaGraph.nodes.get(comboId);
  const total = (snode && typeof snode.table_count === "number" && snode.table_count > tables.length)
    ? snode.table_count : null;
  const truncated = _metaGraph.schemaTruncated.has(comboId);
  _metaGraphRenderClusterDetail(nm, nm, tables, tables.length, childCols, total, truncated, comboId, routines);
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
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || [], { truncated: !!data.truncated });
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
  _metaGraphRenderDetail(self, data.nodes || [], data.edges || [], { truncated: !!data.truncated });
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
    // Phase C(semantic-embed): 의미 클러스터 id/라벨 → _metaSimGroups 가 be: 그룹으로 소비(affix 폴백).
    //   analysis-freshness(2026-07-23): 필드가 payload 에 **존재하면 null 포함 항상 반영** — 종전
    //   `!= null` 가드는 백엔드 재클러스터로 클러스터 해제/변경 시 열린 세션 모델이 stale 값을
    //   영구 보존해, 캔버스 밴드(모델 stale)와 상세 패널(신선한 API 노드)이 어긋나는 원인.
    //   필드 자체가 없는 payload(neighborhood 등 비클러스터 응답)는 기존값 보존.
    if ("cluster_id" in n) rec.cluster_id = n.cluster_id;
    if ("cluster_label" in n) rec.cluster_label = n.cluster_label;
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

// graph-noise-reduce(사용자 요구 2026-07-28): 상세 패널의 "한 번 읽으면 끝" 조작 설명을 상시 문단 대신
//   섹션 제목 옆 hover 툴팁(ⓘ)으로 축약하는 공용 마커. 설명문이 실제 데이터(컬럼·관계·루틴 목록)를
//   아래로 밀어내던 시각 노이즈를 제거하되 정보 자체는 hover 로 보존한다(조작 안내 정본은 ❓ 도움말).
function _metaSecHelp(tip) {
  const t = String(tip == null ? "" : tip)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  return ` <span class="amgr-sec-help" tabindex="0" role="note" aria-label="${t}" title="${t}">ⓘ</span>`;
}

function _metaGraphRenderDetailEmpty() {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  _metaDbGrpLazy.clear();   // detail-db-groups(review MINOR-3): 패널 비우기 — 미펼침 payload 도 함께 정리(누수 방지).
  // graph-noise-reduce: 다른 pane 의 empty-state(.admin-detail-empty = 1줄) 컨벤션에 맞춤.
  //   조작 안내(우클릭 메뉴 등)는 ❓ 도움말 오버레이가 정본이라 여기서 중복 설명하지 않는다.
  el.innerHTML = '<div class="admin-detail-empty">노드를 클릭하면 상세가 여기에 표시됩니다.</div>';
}

// graph-search-detail: 검색어 갱신 시 상세 패널에 **검색 결과**를 구성한다(트리거 = _metaGraphSearch).
//   백엔드 search_nodes 가 반환한 노드(이름/FQN + 컨텐츠 카테고리 + AI 능동 분석 매칭)를 그래프 3층 구조대로
//   **스키마 클러스터 → 컨텐츠 카테고리 → 노드** 2단으로 구분·정렬하고, 각 단을 접기/펼치기 한다(graph-search-groups).
//   행에 매칭 근거 배지(match_via: 이름/카테고리/AI분석)·유사도를 붙이고, 클릭 시 그 노드 상세로 이동.
//   접힘 상태는 _metaGraph._searchGroupCollapsed(재렌더·키스트로크 간 유지, 검색 해제 시 초기화).
//   컨테이너 id=metaGraphSearchResults 는 검색 해제 시 "검색결과 뷰인지" 판별 마커(노드 상세는 보존).
function _metaGraphRenderSearchResults(nodes, q) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  _metaDbGrpLazy.clear();   // detail-db-groups(review MINOR-3): 검색 결과로 패널 교체 — 미펼침 payload 정리(누수 방지).
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const list = (nodes || []).filter((n) => n && n.key);
  if (!list.length) {
    el.innerHTML = `<div id="metaGraphSearchResults" class="admin-detail-empty admin-meta-graph-searchres">`
      + `<p><strong>'${esc(q)}'</strong> — 결과 없음.</p></div>`;
    return;
  }
  const VIA = { name: ["이름", "amgr-via-name"], category: ["카테고리", "amgr-via-category"], analysis: ["AI 분석", "amgr-via-analysis"] };
  const collapsed = _metaGraph._searchGroupCollapsed || (_metaGraph._searchGroupCollapsed = new Set());
  const CAT_NONE = "none";   // cluster_label 없는 노드 sentinel(카테고리 미분류)
  // 2단 그룹 빌드: schemaCombo -> { label, count, cats: catLabel -> node[] }
  const schemas = new Map();
  list.forEach((n) => {
    const sc = _metaSchemaComboOf(n) || _META_TERMS_COMBO;
    if (!schemas.has(sc)) schemas.set(sc, { label: _metaComboName(sc), count: 0, cats: new Map() });
    const g = schemas.get(sc); g.count += 1;
    const cat = (n.cluster_label && String(n.cluster_label).trim()) ? String(n.cluster_label) : CAT_NONE;
    if (!g.cats.has(cat)) g.cats.set(cat, []);
    g.cats.get(cat).push(n);
  });
  // 정렬: 스키마=매칭수↓→이름 / 카테고리=수↓→이름(미분류 맨끝) / 노드=유사도↓→이름
  const scArr = Array.from(schemas.entries()).sort((a, b) => b[1].count - a[1].count || _metaNatSort(a[1].label, b[1].label));
  const rowHtml = (n) => {
    const via = Array.isArray(n.match_via) ? n.match_via : [];
    const badges = via.map((v) => VIA[v] ? `<span class="amgr-via ${VIA[v][1]}">${VIA[v][0]}</span>` : "").join("");
    const scorePct = (typeof n.score === "number" && n.score > 0)
      ? ` <span class="admin-meta-graph-muted amgr-searchscore">유사도 ${Math.round(n.score * 100)}%</span>` : "";
    const color = _META_GRAPH_COLOR[n.label] || "#5c6773";
    const labelKo = _META_LABEL_KO[n.label] || n.label || "";
    return `<li class="amgr-row amgr-searchres" data-goto="${esc(n.key)}" role="button" tabindex="0" title="${esc(n.fqn || n.name || n.key)}">`
      + `<div class="amgr-main"><span class="admin-meta-graph-badge" style="background:${color}">${esc(labelKo)}</span> <code>${esc(n.name || n.fqn || n.key)}</code>${scorePct}</div>`
      + (badges ? `<div class="amgr-searchsub">${badges}</div>` : "")
      + `</li>`;
  };
  const grpHead = (cls, id, coll, icon, label, n) =>
    `<div class="amgr-ct-group ${cls}" role="button" tabindex="0" aria-expanded="${!coll}" data-toggle="${esc(id)}" title="접기/펼치기">`
    + `<span class="amgr-ct-group-caret" aria-hidden="true">${coll ? "▸" : "▾"}</span>`
    + `<span class="amgr-ct-group-label">${icon}${esc(label)}</span><span class="amgr-ct-group-n">${n}</span></div>`;
  const parts = [], currentIds = new Set();   // C2: 이번 렌더의 그룹 id 집합 — stale(다른 질의) collapsed id prune 용
  scArr.forEach(([scKey, g]) => {
    const scId = "sc:" + scKey;
    currentIds.add(scId);
    const scColl = collapsed.has(scId);
    parts.push(`<div class="amgr-srch-sc${scColl ? " is-collapsed" : ""}" data-box="${esc(scId)}">`);
    parts.push(grpHead("amgr-srch-head", scId, scColl, "🗂 ", g.label, g.count));
    parts.push(`<div class="amgr-srch-sc-body">`);
    const catArr = Array.from(g.cats.entries()).sort((a, b) => {
      if (a[0] === CAT_NONE) return 1; if (b[0] === CAT_NONE) return -1;
      return b[1].length - a[1].length || _metaNatSort(a[0], b[0]);
    });
    catArr.forEach(([cat, arr]) => {
      arr.sort((x, y) => (y.score || 0) - (x.score || 0) || _metaNatSort(x.name || x.key, y.name || y.key));
      const catId = "cat:" + scKey + "" + cat;
      currentIds.add(catId);
      const catColl = collapsed.has(catId);
      const isNone = cat === CAT_NONE;
      parts.push(`<div class="amgr-srch-cat${catColl ? " is-collapsed" : ""}${isNone ? " amgr-srch-cat-none" : ""}" data-box="${esc(catId)}">`);
      parts.push(grpHead("amgr-srch-subhead", catId, catColl, isNone ? "" : "🏷 ", isNone ? "(카테고리 미분류)" : cat, arr.length));
      parts.push(`<ul class="amgr-list amgr-srch-cat-body">${arr.map(rowHtml).join("")}</ul>`);
      parts.push(`</div>`);
    });
    parts.push(`</div></div>`);
  });
  // C2: 현재 렌더에 없는 stale group id 제거(다른 질의 잔재) — "모두 접기/펼치기" 라벨 오표시·유령 부활 방지.
  for (const id of Array.from(collapsed)) { if (!currentIds.has(id)) collapsed.delete(id); }
  const anyCollapsed = collapsed.size > 0;
  el.innerHTML = `<div id="metaGraphSearchResults" class="admin-meta-graph-card admin-meta-graph-searchres">`
    + `<div class="admin-meta-graph-card-head"><strong>🔎 검색 결과</strong> <span class="admin-meta-graph-relbadge">${list.length}건</span>`
    + ` <button type="button" class="amgr-link amgr-srch-collapse-all" id="metaGraphSearchCollapseAll">${anyCollapsed ? "모두 펼치기" : "모두 접기"}</button></div>`
    + parts.join("") + `</div>`;
  const root = document.getElementById("metaGraphSearchResults");
  // 그룹 토글(스키마·카테고리 헤딩) — 재렌더 없이 class·caret·collapsed Set 만 갱신.
  root.querySelectorAll(".amgr-ct-group[data-toggle]").forEach((h) => {
    const tg = () => {
      const id = h.getAttribute("data-toggle");
      const nowColl = !collapsed.has(id);
      if (nowColl) collapsed.add(id); else collapsed.delete(id);
      const box = h.parentElement; if (box) box.classList.toggle("is-collapsed", nowColl);
      const caret = h.querySelector(".amgr-ct-group-caret"); if (caret) caret.textContent = nowColl ? "▸" : "▾";
      h.setAttribute("aria-expanded", String(!nowColl));
      const ca = document.getElementById("metaGraphSearchCollapseAll");
      if (ca) ca.textContent = collapsed.size > 0 ? "모두 펼치기" : "모두 접기";
    };
    h.addEventListener("click", tg);
    h.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); tg(); } });
  });
  // 행 클릭 → 노드 상세.
  root.querySelectorAll(".amgr-searchres[data-goto]").forEach((r) => {
    const go = () => { const k = r.getAttribute("data-goto"); if (k) _metaGraphShowDetail(k); };
    r.addEventListener("click", go);
    r.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } });
  });
  // 모두 접기/펼치기.
  const collAll = document.getElementById("metaGraphSearchCollapseAll");
  if (collAll) collAll.addEventListener("click", () => {
    if (collapsed.size > 0) collapsed.clear();
    else root.querySelectorAll(".amgr-ct-group[data-toggle]").forEach((h) => collapsed.add(h.getAttribute("data-toggle")));
    _metaGraphRenderSearchResults(nodes, q);   // 상태 반영 재렌더
  });
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
// ── detail-db-groups(사용자 요구 2026-07-27) ────────────────────────────────────────────────
//   상세 패널이 보여주는 **관련성 있는 다른 노드 목록**(사용하는 함수·프로시저, 참조함/참조받음)을
//   ① 소속 **DB(스키마) 단위로 그룹**해 접기/펼치기 하고, ② 종전의 조용한 상한 절단("… 외 N건" 으로
//   목록이 숨겨지던 이슈)을 제거해 **전량**을 그룹 안에서 볼 수 있게 한다.
//
//   그룹 축 = `_metaCatParent(key, fqn)` = `"<scope>:<db>"` — 캔버스의 스키마 클러스터와 **동일 축**이라
//   패널 구획이 화면 구획과 1:1 로 대응한다(밴드=제품 카테고리 / 스키마 클러스터=DB / sim-group=컨텐츠 카테고리).
//
//   성능 — 상한 제거로 한 섹션이 수백~수천 행이 될 수 있으므로 **접힌 그룹은 DOM 을 만들지 않는다**(lazy).
//   행 HTML 문자열만 `_metaDbGrpLazy` 에 보관했다가 사용자가 펼칠 때 body 컨테이너에 주입 + 그 컨테이너에
//   한정해 행 바인딩(bind 콜백)을 수행한다. 기본 규칙(선택 노드와 같은 DB 만 펼침)과 맞물려 초기 렌더의
//   DOM·리스너 비용이 종전(상한 30/60 행)과 같은 수준으로 유지된다.
const _META_DBGRP_ROW_CAP = 4000;   // 비현실 극단 전용 안전 가드(브라우저 행 폭주 방지). 실사용은 사실상 무제한.
const _META_DBGRP_FLAT_MAX = 60;    // 총 항목이 이 개수 이하면 전 그룹 기본 펼침(짧은 목록은 절대 숨기지 않는다).
const _META_DBGRP_BIG = 300;        // 이 개수를 넘는 그룹은 초기 렌더에서 접힘(DOM·리스너 폭주 방지).
const _metaDbGrpLazy = new Map();   // gid -> { html, bind } — 접힌 그룹의 지연 렌더 payload(패널 재렌더마다 초기화)
let _metaDbGrpSeq = 0;

// 노드 키의 DB(스키마) 그룹 key. 스키마 세그먼트가 없으면(스키마 노드 자신·용어 등) "".
//   review m1: 용어(GlossaryTerm) 등 비-스키마 노드는 fqn 에 "." 이 있으면 유령 DB 그룹(예: "v1.0레벨" → "v1")을
//   만들 수 있어, 호출부가 label 을 넘기면 스키마 소속 라벨(Table/Column/Routine)만 그룹 축으로 인정한다.
const _META_DBGRP_LABELS = { Table: 1, Column: 1, Routine: 1 };
function _metaDbGroupKeyOf(key, fqn, label) {
  if (label && !_META_DBGRP_LABELS[label]) return "";
  return _metaCatParent(key, fqn) || "";
}

// 그룹 펼침 여부 — 우선순위(review B1·M1·M2 반영):
//   ① 대형 그룹(> _META_DBGRP_BIG)은 **사용자 기록보다 우선해 접힘** — 노드 전환 때마다 수천 행이 동기 렌더되며
//      행별 리스너를 다는 것을 막는다(펼침은 그 패널 안에서 유지되고, 재렌더 시 다시 접힌 채 시작).
//   ② 사용자가 조작한 적 있으면 그 상태.
//   ③ 총 항목이 적으면(≤ _META_DBGRP_FLAT_MAX) **전 그룹 펼침** — 다중 DB 라는 이유로 3건짜리 목록이
//      머리글 뒤로 숨는 퇴행(종전보다 덜 보임)을 차단한다.
//   ④ 선택 노드와 같은 DB 는 펼침. self DB 그룹이 아예 없으면 **첫 그룹**을 펼쳐 빈 화면을 만들지 않는다.
//   ⑤ 그 외 접힘.
function _metaDbGroupOpen(gkey, selfDbKey, n, ctx) {
  if ((n || 0) > _META_DBGRP_BIG) return false;
  const st = _metaGraph.panelDbGroupState;
  if (st && st.has(gkey)) return st.get(gkey) === true;
  if (ctx && ctx.total <= _META_DBGRP_FLAT_MAX) return true;
  if (gkey && gkey === selfDbKey) return true;
  return !!(ctx && ctx.isFirst && !ctx.hasSelfGroup);
}

// 관련 노드 목록을 DB 그룹 <li> 시퀀스로 조립한다(호출부의 <ul class="amgr-list"> 안에 그대로 삽입).
//   items: [{ key, fqn, label?, html }] — html 은 호출부가 만든 완성 행(<li>…</li>) 문자열.
//   opts : { selfDbKey, esc, bind } — bind(containerEl) 는 lazy 주입 시 그 컨테이너에만 적용할 행 바인딩.
//   단일 DB + 짧은 목록(≤ _META_DBGRP_FLAT_MAX)이면 머리글 없이 평면으로 반환한다(짧은 목록에 클릭 단계를
//   늘리지 않음 — 기존 UX 유지). 그 외에는 [모두 펼치기 컨트롤] + DB 머리글 + 본문 <li> 를 방출한다.
function _metaDbGroupedRowsHTML(items, opts) {
  const list = items || [];
  if (!list.length) return "";
  // NIT(review): 기본 esc 는 항등이 아니라 escaping — 이 값들은 속성(data-*/aria-label)에 들어간다.
  const esc = (opts && opts.esc) || ((s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"));
  const selfDbKey = (opts && opts.selfDbKey) || "";
  const bind = (opts && opts.bind) || null;
  const groups = new Map();   // gkey -> items[]
  list.forEach((it) => {
    const gk = _metaDbGroupKeyOf(it.key, it.fqn, it.label);
    if (!groups.has(gk)) groups.set(gk, []);
    groups.get(gk).push(it);
  });
  // 전부 같은 DB + 짧은 목록이면 평면 — 클릭 단계를 늘리지 않는다(기존 UX 유지).
  //   같은 단일 DB 라도 길면(> FLAT_MAX) 머리글을 만들어 접기/펼치기 + lazy 렌더 대상으로 삼는다.
  if (groups.size <= 1 && list.length <= _META_DBGRP_FLAT_MAX) {
    return list.map((it) => it.html).join("");
  }
  // 그룹 순서: 스키마 미상("")은 항상 마지막 → 선택 노드와 같은 DB 최우선 → 나머지 DB 명 자연정렬.
  //   (review n1: "" 검사를 self 검사보다 먼저 — selfDbKey 가 "" 인 상세에서 미상 그룹이 맨 앞으로 오던 모순 제거.)
  const order = [...groups.keys()].sort((a, b) => {
    if (!a) return 1;
    if (!b) return -1;
    if (a === selfDbKey) return -1;
    if (b === selfDbKey) return 1;
    return _metaNatSort(_metaComboName(a), _metaComboName(b));
  });
  // review m2: 서로 다른 datasource 의 동명 DB 가 같은 머리글로 두 번 보이지 않게, scope 가 섞였을 때만 병기.
  const scopeOf = (k) => { const i = String(k).indexOf(":"); return i >= 0 ? String(k).slice(0, i) : ""; };
  const multiScope = new Set(order.filter(Boolean).map(scopeOf)).size > 1;
  const hasSelfGroup = groups.has(selfDbKey) && !!selfDbKey;
  const setId = `dbs${++_metaDbGrpSeq}`;   // '모두 펼치기/접기' 가 다루는 그룹 세트(섹션마다 독립)
  const heads = [];
  let emitted = 0, anyCollapsed = false;
  order.forEach((gk, idx) => {
    const members = groups.get(gk);
    const gid = `dbg${++_metaDbGrpSeq}`;
    const open = _metaDbGroupOpen(gk, selfDbKey, members.length, { total: list.length, isFirst: idx === 0, hasSelfGroup });
    if (!open) anyCollapsed = true;
    const base = gk ? _metaComboName(gk) : "스키마 미상";
    const label = (multiScope && gk) ? `${scopeOf(gk)} · ${base}` : base;
    const panKey = members[0] ? members[0].key : "";
    // review B2: ROW_CAP 예산은 **실제 DOM 을 만드는 펼친 그룹만** 소비한다. 접힌 그룹이 예산을 깎아
    //   payload 가 빈 문자열이 되면, 펼쳤을 때 아무것도 없는 목록이 나오는 무음 실패가 된다.
    const shown = open ? Math.min(members.length, Math.max(0, _META_DBGRP_ROW_CAP - emitted)) : members.length;
    const cut = members.length - shown;
    const trunc = cut > 0 ? ` <span class="amgr-ct-group-trunc">(${shown}/${members.length})</span>` : "";
    heads.push(
      `<li class="amgr-ct-group amgr-dbgrp${open ? "" : " is-collapsed"}" role="button" tabindex="0" aria-expanded="${open}" ` +
      `data-dbgrp="${gid}" data-dbgrp-set="${setId}" data-dbgrp-key="${esc(gk)}"${panKey ? ` data-pan-key="${esc(panKey)}"` : ""} ` +
      `aria-controls="amgr-dbgrp-body-${gid}" ` +
      `aria-label="${esc(label)} DB · 항목 ${members.length}개${cut > 0 ? ` (표시 상한으로 ${shown}개만 표시)` : ""}">` +
      `<span class="amgr-ct-group-caret" aria-hidden="true">${open ? "▾" : "▸"}</span>` +
      `<span class="amgr-ct-group-label">${esc(label)}</span>` +
      `<span class="amgr-ct-group-n">${members.length}</span>${trunc}</li>`
    );
    const rowsHTML = members.slice(0, shown).map((it) => it.html).join("")
      + (cut > 0 ? `<li class="admin-meta-graph-muted amgr-more">… 외 ${cut}건 (표시 상한 ${_META_DBGRP_ROW_CAP})</li>` : "");
    // 펼침이면 즉시 렌더(호출부의 일괄 바인딩이 그대로 적용), 접힘이면 비운 채 payload 만 보관(lazy).
    if (open) {
      emitted += shown;
      heads.push(`<li class="amgr-dbgrp-body" id="amgr-dbgrp-body-${gid}" data-dbgrp-body="${gid}"><ul class="amgr-list">${rowsHTML}</ul></li>`);
    } else {
      _metaDbGrpLazy.set(gid, { html: rowsHTML, bind });
      heads.push(`<li class="amgr-dbgrp-body" id="amgr-dbgrp-body-${gid}" data-dbgrp-body="${gid}" hidden><ul class="amgr-list"></ul></li>`);
    }
  });
  // review M3: '모두 펼치기/접기' — 클러스터 상세(metaGraphCtCollapseAll)와 같은 편의 컨트롤. DB 가 여럿인
  //   목록에서 그룹 수만큼 클릭해야 전체를 보던 마찰을 없애고, 기본 접힘·상태 고착의 탈출로가 된다.
  const allCtl = `<li class="amgr-dbgrp-allctl"><button type="button" class="amgr-link amgr-dbgrp-all" data-dbgrp-all="${setId}" ` +
    `title="이 목록의 모든 DB 를 한 번에 접거나 펼칩니다">${anyCollapsed ? "▾ 모두 펼치기" : "▸ 모두 접기"}</button></li>`;
  return allCtl + heads.join("");
}

// DB 그룹 헤딩 토글 바인딩(노드 상세·관계 상세 공통). rootEl 은 패널 body — 매 렌더 innerHTML 로 교체되므로
//   리스너가 누적되지 않는다(직전 DOM 은 리스너와 함께 GC).
function _metaBindDbGroups(rootEl) {
  if (!rootEl) return;
  rootEl.querySelectorAll(".amgr-dbgrp[data-dbgrp]").forEach((h) => {
    const act = () => _metaToggleDbGroup(h, rootEl);
    h.addEventListener("click", act);
    h.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
      e.preventDefault(); act();
    });
    // review m3: 머리글 hover 카메라 팬은 걸지 않는다 — 클러스터 상세의 컨텐츠 카테고리와 달리 이 머리글은
    //   **다른 DB**(캔버스 반대편)를 가리켜, 어느 그룹을 펼칠지 고르며 훑는 동안 화면이 크게 튄다. 대상 이동은
    //   그룹을 펼친 뒤 개별 행 hover/클릭으로 한다.
  });
  // '모두 펼치기/접기' — 같은 세트의 그룹을 일괄 토글(하나라도 접혀 있으면 전부 펼치고, 아니면 전부 접는다).
  rootEl.querySelectorAll(".amgr-dbgrp-all[data-dbgrp-all]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation(); ev.preventDefault();
      const setId = btn.getAttribute("data-dbgrp-all");
      const hs = [...rootEl.querySelectorAll(`.amgr-dbgrp[data-dbgrp-set="${setId}"]`)];
      if (!hs.length) return;
      const expand = hs.some((h) => h.classList.contains("is-collapsed"));
      hs.forEach((h) => { if (h.classList.contains("is-collapsed") === expand) _metaToggleDbGroup(h, rootEl); });
      _metaSyncDbGrpAllLabel(rootEl, setId);
    });
  });
}

// review MAJOR-4: 컬럼 아코디언 본문(관계 행)의 지연 렌더 payload 등록 — 반환값은 body 의 data-collazy 토큰.
//   DB 그룹의 lazy 기계(_metaDbGrpLazy)를 그대로 재사용해 상태·정리 경로를 하나로 유지한다.
function _metaColBodyLazy(html, selfKey) {
  const gid = `dbcol${++_metaDbGrpSeq}`;
  _metaDbGrpLazy.set(gid, {
    html,
    bind: (c) => { _metaGraphBindTraceRows(c); _metaGraphBindDetailHover(c, selfKey); _metaBindDbGroups(c); },
  });
  return gid;
}

// 컬럼 아코디언 첫 펼침 — payload 주입 + 그 컨테이너 한정 바인딩(1회). payload 가 이미 소비됐으면 no-op.
function _metaColBodyReveal(body, selfKey) {
  if (!body) return;
  const gid = body.getAttribute("data-collazy");
  if (!gid) return;
  const pend = _metaDbGrpLazy.get(gid);
  if (pend) {
    body.innerHTML = pend.html;
    if (typeof pend.bind === "function") { try { pend.bind(body); } catch (_) { /* 바인딩 실패가 표시를 막지 않음 */ } }
    _metaDbGrpLazy.delete(gid);
    return;
  }
  // payload 가 없고 본문도 비어 있으면 = 패널 재렌더/예외로 payload 가 정리된 stale DOM. 무음 대신 안내.
  if (!body.firstChild) body.innerHTML = `<p class="admin-meta-graph-desc admin-meta-graph-muted">목록을 다시 불러오세요 — 패널이 갱신되었습니다.</p>`;
}

// review MAJOR-1: 백엔드 이웃 투영이 `_NEIGHBOR_NODE_CAP`(300)에 걸려 **부분 이웃**을 돌려준 경우의 고지 배너.
//   프론트 상한을 전부 없애도 이 상한이 남아 있으므로, 알리지 않으면 종전과 같은 "무음 절단" 이 된다.
//   (백엔드가 `truncated: true` 를 세팅하는 경로에서만 뜬다 — 정상 응답에는 노출 없음.)
function _metaDbGrpTruncNotice(meta) {
  if (!meta || !meta.truncated) return "";
  // graph-noise-reduce: 상시 노출 4줄 → 1줄 경고 + 상세는 hover 툴팁(경고 자체는 무음 절단 방지라 유지).
  return `<p class="admin-meta-detail-note amgr-trunc-note" title="백엔드 이웃 조회 상한에 걸려 일부만 불러왔습니다. 아래 목록은 불러온 범위 안에서는 생략 없이 전부 표시합니다. 더 보려면 '🕸 그래프에 펼치기' 로 이웃을 단계적으로 확장하세요.">⚠ 이웃 조회 상한 — <strong>일부만</strong> 불러옴</p>`;
}

// '모두 펼치기/접기' 라벨을 현재 그룹 상태로 재동기화(개별 토글 후 라벨-동작 불일치 방지).
function _metaSyncDbGrpAllLabel(rootEl, setId) {
  if (!rootEl || !setId) return;
  const btn = rootEl.querySelector(`.amgr-dbgrp-all[data-dbgrp-all="${setId}"]`);
  if (!btn) return;
  const hs = [...rootEl.querySelectorAll(`.amgr-dbgrp[data-dbgrp-set="${setId}"]`)];
  if (!hs.length) return;
  btn.textContent = hs.some((h) => h.classList.contains("is-collapsed")) ? "▾ 모두 펼치기" : "▸ 모두 접기";
}

function _metaToggleDbGroup(h, rootEl, syncSiblings) {
  if (syncSiblings === undefined) syncSiblings = true;
  if (!h || !rootEl) return;
  const gid = h.getAttribute("data-dbgrp");
  const gkey = h.getAttribute("data-dbgrp-key") || "";
  const open = !h.classList.contains("is-collapsed");   // 현재 펼침 → 이번 클릭은 접기
  const body = gid ? rootEl.querySelector(`.amgr-dbgrp-body[data-dbgrp-body="${gid}"]`) : null;
  h.classList.toggle("is-collapsed", open);
  h.setAttribute("aria-expanded", String(!open));
  const caret = h.querySelector(".amgr-ct-group-caret");
  if (caret) caret.textContent = open ? "▸" : "▾";
  if (body) {
    if (!open) {
      // 펼치는 중 — lazy payload 가 남아 있으면 이때 주입하고 그 컨테이너에만 행 바인딩을 건다(1회).
      const pend = gid ? _metaDbGrpLazy.get(gid) : null;
      const ul = body.querySelector("ul");
      if (pend) {
        if (ul) {
          ul.innerHTML = pend.html;
          if (typeof pend.bind === "function") { try { pend.bind(ul); } catch (_) { /* 바인딩 실패는 표시를 막지 않음 */ } }
        }
        _metaDbGrpLazy.delete(gid);
      } else if (ul && !ul.firstChild) {
        // review MINOR-1: payload 가 없고 본문도 비었다 = 렌더 도중 예외 등으로 payload 만 정리된 stale DOM.
        //   빈 목록을 조용히 보여주는 것이 이번 작업이 없애려던 무음 실패이므로, 상태를 명시한다.
        ul.innerHTML = `<li class="admin-meta-graph-muted">목록을 다시 불러오세요 — 패널이 갱신되었습니다.</li>`;
      }
    }
    body.hidden = open;
  }
  // 사용자 조작 기록 — 다음 렌더·다른 상세 뷰에서도 이 DB 의 펼침/접힘 의도가 유지된다.
  //   (대형 그룹은 _metaDbGroupOpen 이 이 기록보다 우선해 접힌 채 시작한다 — review M2 성능 가드.)
  //   review MINOR-5: 스키마 미상("") 버킷은 모든 패널이 한 슬롯을 공유해 의미가 뒤섞이므로 기록하지 않는다.
  if (gkey && _metaGraph.panelDbGroupState) _metaGraph.panelDbGroupState.set(gkey, !open);
  // review MINOR-6: 같은 렌더 안에 같은 DB 머리글이 여럿(읽기/쓰기·방향별·컬럼별)일 수 있다 — 형제도 같이 맞춘다.
  //   `syncSiblings === false` 로 재진입해 무한 재귀를 막는다(형제 토글이 다시 형제를 찾지 않음).
  if (gkey && syncSiblings) {
    const want = !open;   // 이번 조작 후의 목표 상태(true=펼침)
    rootEl.querySelectorAll(".amgr-dbgrp[data-dbgrp-key]").forEach((sib) => {
      if (sib === h || sib.getAttribute("data-dbgrp-key") !== gkey) return;
      if (!sib.classList.contains("is-collapsed") !== want) _metaToggleDbGroup(sib, rootEl, false);
    });
  }
  // 같은 세트의 '모두 펼치기/접기' 라벨을 현재 상태로 재동기화(개별 토글 후 라벨-동작 불일치 방지).
  _metaSyncDbGrpAllLabel(rootEl, h.getAttribute("data-dbgrp-set"));
}

function _metaGraphRenderDetail(self, nodes, edges, meta) {
  // graphux5-panelmove: 노드 상세는 body 서브컨테이너에만 렌더(진행 패널은 aside 상단에 유지).
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  _metaGraphHoverPanCancel(); _metaGraphClearHoverHighlight();   // detail-hover-fx: 패널 재렌더 시 직전 hover 잔여(예약 팬·강조) 정리(mouseleave 미발화 경로 대비).
  _metaDbGrpLazy.clear();   // detail-db-groups: 직전 패널의 미펼침 payload 폐기(재렌더로 gid 가 무효화되므로 누수 방지).
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
  // detail-db-groups: 선택 노드가 속한 DB — 그룹 정렬(최우선)·기본 펼침 판정 기준.
  const selfDbKey = _metaDbGroupKeyOf(selfKey, self.fqn || (_metaGraph.nodes.get(selfKey) || {}).fqn);
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
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || self.key)}</strong>${relPct != null ? ` <span class="admin-meta-graph-relbadge" title="검색어 유사도(pg_trgm)">유사도 ${relPct}%</span>` : ""} <button type="button" class="amgr-link" id="metaGraphRelBtn" title="이 노드의 관계를 방향·신뢰도·근거별로 자세히 봅니다 (노드 우클릭 메뉴에서도 열림)">🔗 관계 상세</button> <button type="button" class="amgr-link" id="metaGraphFocusSelBtn" style="margin-left:0" title="선택한 이 노드로 그래프 카메라를 이동합니다. 화면에 없으면 상위 스키마·테이블을 펼쳐 노출합니다.">🎯 이 노드로 이동</button></div>`);
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
    // detail-hover-fx: self 끝점 키(방향별 e.source/e.target) — hover 연결선 강조가 정확한 컬럼↔상대 엣지를 그린다.
    const selfEndKey = dir === "out" ? e.source : e.target;
    return `<li class="amgr-row amgr-trace" data-trace="${esc(other)}" data-edge-self="${esc(selfEndKey)}" role="button" tabindex="0" ` +
      `title="${esc(tip)}">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span> <code>${esc(otherFqn)}</code>` +
      `${e.cardinality ? " [" + esc(e.cardinality) + "]" : ""}` +
      `${e.edge_source && e.edge_source !== "fk_introspect" ? " <span class=\"admin-meta-graph-muted\">(" + esc(_META_EDGE_SOURCE_KO[e.edge_source] || e.edge_source) + ")</span>" : ""}` +
      `${_metaEdgeTrustBadge(e)} <span class="amgr-tracehint">🔎 추적</span></div></li>`;
  };
  // detail-db-groups: 방향 그룹 안의 상대 노드를 **소속 DB 단위**로 다시 묶는다(크로스-DB 참조가 섞이면
  //   어느 DB 의 무엇을 참조하는지 한눈에 구분). 단일 DB 면 그룹 계층 없이 평면(기존 UX 동일).
  const dirGroup = (list, dir) => {   // 방향 그룹(참조함/참조받음) + 개수
    if (!list.length) return "";
    const label = dir === "out" ? "참조함" : "참조받음";
    const arrow = dir === "out" ? "→" : "←";
    const rows = _metaDbGroupedRowsHTML(
      list.map((it) => {
        const on = byKey[it.other] || _metaGraph.nodes.get(it.other) || {};
        return { key: it.other, fqn: on.fqn, label: on.label, html: relRow(it, dir) };
      }),
      { selfDbKey, esc, bind: (c) => { _metaGraphBindTraceRows(c); _metaGraphBindDetailHover(c, selfKey); } }
    );
    return `<div class="amgr-dir"><div class="amgr-dir-head"><span class="amgr-arrow">${arrow}</span> ${label} (${list.length})</div>` +
      `<ul class="amgr-list">${rows}</ul></div>`;
  };

  if (columns.length || selfIsColumn) {
    // 전체 관계 요약(방향별 개수).
    const relSummary = (totOut + totIn) > 0
      ? ` <span class="admin-meta-graph-relbadge" title="이 노드의 관계 방향별 개수">관계 ${totOut + totIn} · 참조함 ${totOut} · 참조받음 ${totIn}</span>`
      : "";
    if (selfIsColumn) {
      // 컬럼 상세: 컬럼 자신의 관계를 방향별로 바로 표시(아코디언 불필요).
      const cr = colRel.get(selfKey) || { out: [], in: [] };
      parts.push(`<div class="admin-meta-graph-sec"><h4>관계${relSummary}${_metaSecHelp("행 hover = 관계 의미, 클릭 = 대상 추적(상세 + 카메라 이동).")}</h4>`);
      if (cr.out.length || cr.in.length) {
        parts.push(dirGroup(cr.out, "out"));
        parts.push(dirGroup(cr.in, "in"));
      } else {
        parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다.</p>`);
      }
      parts.push(`</div>`);
    } else {
      // 테이블 상세: 컬럼 목록 — 관계 있는 컬럼은 아코디언(클릭 펼침).
      parts.push(`<div class="admin-meta-graph-sec"><h4>컬럼 (${columns.length})${relSummary}${_metaSecHelp("컬럼 클릭 = 상세로 전환 + 그래프에서 강조. 관계가 있는 컬럼(🔗)은 캐럿(▸)으로 참조함/참조받음을 그 자리에서 펼칩니다(상대가 여러 DB 면 DB 머리글로 묶임). 관계 행 hover = 의미, 클릭 = 대상 추적.")}</h4>`);
      parts.push(`<ul class="amgr-collist">`);
      // detail-db-groups: 종전 80개 **무음** 절단(헤더 개수와 실제 행 수가 조용히 어긋남) 제거 — 전량 렌더.
      //   컬럼은 선택 노드 자신의 소속이라 DB 그룹 축이 무의미하므로 그룹핑 없이 전량, 안전 가드만 유지.
      columns.slice(0, _META_DBGRP_ROW_CAP).forEach((c) => {
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
          `<div class="amgr-col-body" id="amgr-colbody-${esc(c.key)}" data-colbody="${esc(c.key)}" data-collazy="${_metaColBodyLazy(dirGroup(cr.out, "out") + dirGroup(cr.in, "in"), selfKey)}" hidden></div>` +
          `</li>`
        );
      });
      if (columns.length > _META_DBGRP_ROW_CAP) parts.push(`<li class="amgr-col amgr-col-plain admin-meta-graph-muted">… 외 ${columns.length - _META_DBGRP_ROW_CAP}개 (표시 상한)</li>`);
      parts.push(`</ul></div>`);
    }
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul>`);
    // detail-db-groups: 종전 30건 무음 절단 제거 — 용어는 DB 소속이 아니라 그룹 축이 없으므로 전량 나열.
    terms.slice(0, _META_DBGRP_ROW_CAP).forEach((t) => parts.push(`<li><strong>${esc(t.name)}</strong>${t.description ? " — " + esc(t.description) : ""}</li>`));
    if (terms.length > _META_DBGRP_ROW_CAP) parts.push(`<li class="admin-meta-graph-muted">… 외 ${terms.length - _META_DBGRP_ROW_CAP}건 (표시 상한)</li>`);
    parts.push(`</ul></div>`);
  }
  // graph-funcproc(ADR-016): ROUTINE_USES — Routine 상세엔 "사용 테이블", Table 상세엔 "사용하는 함수·프로시저".
  //   graph-rw-group(사용자 요구): 사용(참조) 관계를 읽기/쓰기(relation_type)로 **그룹 분리**한다 —
  //   평면 목록 + 항목별 읽기/쓰기 꼬리표 대신, 읽기/쓰기 소그룹 헤더(개수)로 묶어 데이터 흐름을
  //   한눈에 구분한다(REFERENCES 방향 그룹 dirGroup 과 동일한 amgr-dir 스타일 재사용). relation_type
  //   "write"=루틴→테이블(씀), 그 외("read"·미상)=테이블→루틴(읽음, 기존 kindKo 기본값과 정합).
  //   detail-db-groups(사용자 요구 2026-07-27): 종전 그룹당 30건 상한 + "… 외 N건" 으로 **목록이 숨겨지던**
  //   이슈를 제거한다 — 읽기/쓰기 각 그룹 안에서 상대 노드를 **소속 DB 단위**로 다시 묶고(접기/펼치기),
  //   각 DB 그룹은 멤버 전량을 담는다. 크로스-DB 사용 관계가 많은 테이블에서 "어느 DB 의 어떤 루틴이
  //   이 테이블을 읽고/쓰는가" 가 DB 별로 분리돼 보이고, 조용한 절단이 사라진다.
  if (routineUses.length) {
    const isRoutineSelf = self.label === "Routine";
    const rtOther = (e) => (e.source === selfKey ? e.target : e.source);
    const rtRow = (e) => {
      const other = rtOther(e);
      const on = byKey[other] || _metaGraph.nodes.get(other) || {};
      const disp = on.label === "Routine"
        ? `${_metaRoutineIcon(on.routine_type)} ${on.name || nm(other)}` : nm(other);
      return `<li><button type="button" class="amgr-link" data-rtuse="${esc(other)}" title="상세 보기">${esc(disp)}</button></li>`;
    };
    // lazy 주입되는 DB 그룹 body 에도 원래의 행 동작(클릭=상세+카메라, hover=연결선 강조)을 그대로 건다.
    const rtBind = (c) => {
      c.querySelectorAll("[data-rtuse]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const k = btn.getAttribute("data-rtuse");
          if (!k) return;
          _metaGraphPanToRelation(k);
          _metaGraphShowDetail(k);
        });
      });
      _metaGraphBindDetailHover(c, selfKey);
    };
    const rtGroup = (list, label) => {   // 읽기/쓰기 소그룹(개수 + DB 단위 하위 그룹, 절단 없음)
      if (!list.length) return "";
      const rows = _metaDbGroupedRowsHTML(
        list.map((e) => {
          const other = rtOther(e);
          const on = byKey[other] || _metaGraph.nodes.get(other) || {};
          return { key: other, fqn: on.fqn, label: on.label, html: rtRow(e) };
        }),
        { selfDbKey, esc, bind: rtBind }
      );
      return `<div class="amgr-dir"><div class="amgr-dir-head">${label} (${list.length})</div>` +
        `<ul class="amgr-list">${rows}</ul></div>`;
    };
    const rtWrites = routineUses.filter((e) => e.relation_type === "write");
    const rtReads = routineUses.filter((e) => e.relation_type !== "write");
    // 조사는 앞 명사 종성에 따라 분기(테이블→'을', 함수·프로시저→'를').
    const rtHelp = `${isRoutineSelf ? "이 함수·프로시저가 사용하는 테이블을" : "이 테이블을 사용하는 함수·프로시저를"} 읽기/쓰기로 나눠 표시하며 목록을 잘라내지 않습니다. 대상이 여러 DB 에 걸치면 DB 머리글로 묶이며(머리글 클릭 = 그 DB 접기/펼치기, '모두 펼치기' 로 일괄), 접힌 DB 도 머리글의 개수가 실제 총계입니다. 행 클릭 = 대상 상세 + 카메라 이동.`;
    parts.push(`<div class="admin-meta-graph-sec"><h4>${isRoutineSelf ? "사용 테이블" : "사용하는 함수·프로시저"} (${routineUses.length}) <span class="admin-meta-graph-muted">· 읽기 ${rtReads.length} · 쓰기 ${rtWrites.length}</span>${_metaSecHelp(rtHelp)}</h4>`);
    parts.push(_metaDbGrpTruncNotice(meta));
    parts.push(rtGroup(rtReads, "읽기"));
    parts.push(rtGroup(rtWrites, "쓰기"));
    parts.push(`</div>`);
  }
  // 항목2: AI 능동 분석 섹션 — 버튼으로 트리거(백그라운드 재귀), box 에 진행/결과 렌더.
  //   graph-funcproc(ADR-017, REQ ⑤): 버튼 hover 시 지침 입력 popover(툴팁형) — 입력하면 LLM 이
  //   자율 판단해 분석에 반영. 입력 없이 클릭하면 기존과 동일(지침 없는 분석).
  //   graph-analyze-perm(Critical §12.3, 2026-07-14): **게이트 분리** — 결과 조회는 metadata.graph.read,
  //   실행(버튼·지침 popover)은 하위 권한 metadata.graph.analyze. 섹션 컨테이너·결과 box(metaGraphAiBox)는
  //   항상 렌더해 조회 권한자가 기존 AI 분석 결과·진행 상태를 열람하고(백엔드 GET /graph/analyze/node 도
  //   graph.read 게이트, graph.read 설명의 "결과·진행 상태 열람" 계약과 정합), '능동 분석'/'분석 시작' 실행
  //   컨트롤만 _canAnalyze 로 게이트한다(요청: 권한 없으면 버튼 UI 미표시). 실 거부는 백엔드 403 이 최종 경계.
  const _canAnalyze = (typeof can === "function") && can("metadata.graph.analyze");
  parts.push(`<div class="admin-meta-graph-sec admin-meta-graph-ai" id="metaGraphAiSec">`);
  // graph-noise-reduce: 상시 안내문(재귀 분석 설명 · 지침 반영 설명)을 컨트롤 hover 툴팁으로 이관.
  //   결과 box 는 "아직 결과 없음" 이라는 상태만 1줄로 남긴다(설명이 아니라 상태).
  parts.push(`<div class="admin-meta-graph-ai-head"><h4>AI 능동 분석</h4>${_canAnalyze ? `<button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiBtn" title="이 노드에서 시작해 관련 노드를 AI가 재귀적으로 분석합니다(백그라운드). hover 로 분석 지침 입력.">✨ 능동 분석</button>` : ``}</div>`);
  if (_canAnalyze) {
    parts.push(`<div class="admin-meta-ai-pop" id="metaGraphAiPop" hidden>` +
      `<label for="metaGraphAiPrompt" title="지침은 AI가 자율 판단해 분석 내용·탐색 방향에 반영합니다.">분석 지침 (선택, ≤400자)</label>` +
      `<textarea id="metaGraphAiPrompt" rows="2" maxlength="400" title="지침은 AI가 자율 판단해 분석 내용·탐색 방향에 반영합니다." placeholder="예: 결제 흐름 관점에서 연관 테이블 위주로 분석"></textarea>` +
      `<div class="admin-meta-ai-pop-foot">` +
      `<button type="button" class="btn-secondary admin-meta-ai-btn" id="metaGraphAiPopGo">✨ 분석 시작</button></div></div>`);
  }
  parts.push(`<div class="admin-meta-graph-ai-box" id="metaGraphAiBox"><span class="admin-meta-graph-muted">분석 결과 없음</span></div>`);
  parts.push(`</div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // 실행 컨트롤 바인딩(+hover 지침 popover) — _canAnalyze 일 때만(버튼·popover 미렌더 시 skip). 결과 로드는 아래 무조건.
  if (_canAnalyze) _metaGraphBindAiPopover(self.key, selfScopeKey);
  // graph-focus-selected: 상세 패널의 선택 노드로 카메라를 팬한다(_metaGraphPanToRelation 패턴 재사용).
  //   graph-node-reveal(사용자 요구 2026-07-23): 렌더 안 된 노드(접힌 스키마 소속 테이블·함수, 미펼침
  //   테이블의 컬럼 등)여도 차단하지 않고, 부모 스키마·테이블을 펼쳐 화면에 노출한 뒤 팬한다. 이미
  //   렌더된 노드는 기존대로 구조 불변·팬만(비동기 확장 없음).
  const focusSelBtn = document.getElementById("metaGraphFocusSelBtn");
  if (focusSelBtn) focusSelBtn.addEventListener("click", async () => {
    const key = self.key;
    if (!_metaGraph.graph || !key) return;
    if (_metaGraphFocusSelBusy) return;   // 진행 중 재진입 차단(연타 시 중복 fetch·이중 팬 방지 — 리뷰 #1)
    const nm = (_metaGraph.nodes.get(key) || {}).name || self.name || key;
    let rel = _metaRenderedIdFor(key);   // 렌더 노드, 접힌 스키마면 카드(SC:)
    if (!rel) {
      // 미렌더 — 부모 체인 활성화(펼침)로 노출 시도(차단하지 않음).
      _metaGraphFocusSelBusy = true;
      _metaGraphStatus(`'${nm}' 을(를) 화면에 표시하려고 상위 스키마·테이블을 펼치는 중…`);
      try {
        await _metaGraphRevealNode(key);
      } catch (_) {
        // 확장 중 예외(rebuild 실패 등) — 상태 고착 방지(리뷰 #6): 안내 후 종료(finally 가 busy 해제).
        _metaGraphStatus(`'${nm}' 표시 실패 — 확대하거나 검색으로 탐색해 보세요.`);
        return;
      } finally {
        _metaGraphFocusSelBusy = false;
      }
      rel = _metaRenderedIdFor(key);
      if (!rel) {
        // 활성화로도 못 띄움(타 데이터소스·표시 상한·줌 LOD 억제·kind 숨김 등 다양) → 조상 승격 폴백.
        //   원인이 여럿이라 특정 원인을 단정하지 않고 '확대·검색' 을 일반 안내한다(리뷰 #3·#4).
        const anc = _metaRenderedAncestorFor(key);
        if (anc) {
          _metaGraphAnimateFocus(anc, _metaGraph._opSeq);
          // graph-catcluster-focus: 어느 상위 객체로 갔는지 명시 — 접힌 컨텐츠/제품 카테고리면 그 클러스터를 펼치면 된다는 다음 행동이 드러난다.
          _metaGraphStatus(`→ '${nm}' 의 ${_metaAncestorKindKo(anc)}로 카메라 이동 (그 클러스터를 펼치거나 확대·검색으로 하위 노드를 직접 탐색할 수 있습니다).`);
        } else {
          _metaGraphStatus(`'${nm}' 은(는) 현재 화면에 표시할 수 없습니다 — 확대하거나 검색으로 직접 탐색해 보세요.`);
        }
        return;
      }
      _metaGraphSetSelected(key);   // 펼쳐 노출된 노드를 선택 강조(사용자 시선 앵커)
    }
    _metaGraphAnimateFocus(key, _metaGraph._opSeq);   // key→렌더 요소 내부 해소 후 카메라 팬(+판독 줌 클램프)
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
      // detail-db-groups(review MAJOR-4): 컬럼 관계 본문은 lazy — 첫 펼침 때만 DOM 을 만들고 바인딩한다.
      //   종전엔 hidden 이어도 전 컬럼의 관계 행이 즉시 DOM 이라, 컬럼 상한(80) 제거와 맞물려 넓은 테이블의
      //   초기 렌더 비용이 커졌다. 지금은 펼친 컬럼만 비용을 낸다(종전 80 캡보다도 낮음).
      if (body && !open) _metaColBodyReveal(body, self.key);
      if (body) body.hidden = open;
    });
  });
  // detail-hover-fx: 하위 항목 hover 강조 — 컬럼=노드 링, 참조·사용 행=연결선(엣지). 클릭/토글 바인딩과 병존.
  _metaGraphBindDetailHover(el, self.key);
  // detail-db-groups: DB 그룹 헤딩 접기/펼치기(+lazy 주입) 바인딩. 위 일괄 바인딩은 이미 렌더된 행에만
  //   적용되므로, 나중에 펼쳐지는 그룹은 각 payload 의 bind 콜백이 그 컨테이너에 한정해 처리한다.
  _metaBindDbGroups(el);
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
  _metaGraphRenderRelations(key, mNodes, mEdges, { truncated: !!data.truncated });
}

function _metaGraphRenderRelations(key, nodes, edges, meta) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  _metaGraphHoverPanCancel(); _metaGraphClearHoverHighlight();   // detail-hover-fx: 패널 재렌더 시 직전 hover 잔여 정리.
  _metaDbGrpLazy.clear();   // detail-db-groups: 직전 패널의 미펼침 payload 폐기(gid 무효화 — 누수 방지).
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const byKey = {};
  (nodes || []).forEach((n) => { if (n && n.key) byKey[n.key] = n; });
  const self = byKey[key] || _metaGraph.nodes.get(key) || { key, name: key, label: "" };
  // detail-db-groups: 선택 노드가 속한 DB — 관계 목록의 DB 그룹 정렬·기본 펼침 기준.
  const selfDbKey = _metaDbGroupKeyOf(key, self.fqn || (_metaGraph.nodes.get(key) || {}).fqn);
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
    return `<li class="amgr-row" data-key="${esc(otherKey)}" data-edge-self="${esc(selfEndKey || key)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
      `<div class="amgr-main"><span class="amgr-arrow">${arrow}</span>${main}` +
      `${e.cardinality ? ` <span class="admin-meta-graph-muted">[${esc(e.cardinality)}]</span>` : ""}${_metaEdgeTrustBadge(e)}${curateBtns(e)}</div>` +
      `<div class="amgr-sub admin-meta-graph-muted">${esc(typeKo)}${srcKo ? " · 근거: " + esc(srcKo) : ""}${on.description ? " — " + esc(on.description) : ""}</div></li>`;
  };
  // detail-db-groups(사용자 요구 2026-07-27): 종전 60/30/20건 상한 + "… 외 N건" 으로 목록이 숨겨지던 이슈를
  //   제거하고, 방향 그룹 안의 상대 노드를 **소속 DB 단위**로 묶어 접기/펼치기 한다(안전 가드 초과분만 표기).
  const moreRow = (n) => `<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${n}건 (표시 상한 — 그래프에 펼치기로 확인)</div></li>`;
  // 관계 행 바인딩(초기 렌더 + DB 그룹 lazy 주입 공용) — 행 클릭/hover 강조 + 큐레이션 버튼.
  const bindRelRows = (c) => {
    if (!c) return;
    c.querySelectorAll(".amgr-row[data-key]").forEach((r) => {
      // graphux7(#2): 단일=카메라 이동만(상세 유지), 더블=상세 전환(+대상 테이블·컬럼 강조).
      _metaGraphBindRelRow(r, r.getAttribute("data-key"));
      // detail-hover-fx: hover 시 연결선(엣지) 강조 — self 끝점(data-edge-self)↔상대(data-key).
      _metaBindHoverHighlight(r, { edgeKeyPairs: [[r.getAttribute("data-edge-self") || key, r.getAttribute("data-key")]] });
    });
    // graph-category(§55 B): 큐레이션 버튼 — 행 클릭(카메라 이동)과 분리(stopPropagation).
    c.querySelectorAll("button.amgr-cur").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation(); ev.preventDefault();
        _metaGraphCurateRelation(b.getAttribute("data-cur"), b.getAttribute("data-src"), b.getAttribute("data-tgt"), key);
      });
    });
  };
  // 방향 그룹 본문 — 상대 노드를 DB 단위로 묶어 전량 방출(단일 DB 면 평면).
  //   dir "out": 상대 = e.target(self 끝점 e.source) · dir "in": 상대 = e.source(self 끝점 e.target).
  const dirRowsHTML = (list, dir) => _metaDbGroupedRowsHTML(
    list.map((e) => {
      const otherKey = (dir === "out") ? e.target : e.source;
      const selfEndKey = (dir === "out") ? e.source : e.target;
      return {
        key: otherKey,
        fqn: (byKey[otherKey] || _metaGraph.nodes.get(otherKey) || {}).fqn,
        html: row(e, otherKey, selfEndKey, dir === "out" ? "→" : "←"),
      };
    }),
    { selfDbKey, esc, bind: bindRelRows }
  );
  // review: REFERENCES 외 타입이 섞이면 "참조" 대신 중립 라벨.
  const dirLabel = (list, refLabel, neutral) => (list.every((e) => e.type === "REFERENCES") ? refLabel : neutral);
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR[self.label] || "#5c6773"}">${esc(self.label || "")}</span><strong>${esc(self.name || self.fqn || key)}</strong> <span class="admin-meta-graph-relbadge">관계 상세</span></div>`);
  if (self.fqn) parts.push(`<div class="admin-meta-graph-fqn">${esc(self.fqn)}</div>`);
  // graph-noise-reduce: 설명 문장은 걷어내고 카운트(데이터)만 남김 — 조작 설명은 hover 툴팁으로.
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">참조함 ${out.length} · 참조받음 ${inn.length} · 연관 용어 ${terms.length}${around.length ? ` · 주변 관계 ${around.length}` : ""}${_metaSecHelp("이 노드가 맺은 관계를 방향별로 봅니다. 목록을 잘라내지 않으며, 상대가 여러 DB 에 걸치면 DB 머리글로 묶입니다(머리글 클릭 = 그 DB 접기/펼치기, '모두 펼치기' 로 일괄). 행 클릭 = 상대 노드 상세로 이동.")}</p>`);
  parts.push(_metaDbGrpTruncNotice(meta));
  if (out.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>→ ${dirLabel(out, "참조함", "나가는 관계")} (${out.length})</h4><ul class="amgr-list">`);
    parts.push(dirRowsHTML(out, "out"));
    parts.push(`</ul></div>`);
  }
  if (inn.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>← ${dirLabel(inn, "참조받음", "들어오는 관계")} (${inn.length})</h4><ul class="amgr-list">`);
    parts.push(dirRowsHTML(inn, "in"));
    parts.push(`</ul></div>`);
  }
  if (terms.length) {
    parts.push(`<div class="admin-meta-graph-sec"><h4>연관 용어 (${terms.length})</h4><ul class="amgr-list">`);
    // detail-db-groups: 종전 30건 절단 제거 — 용어는 DB 소속이 아니라 그룹 축 없이 전량(안전 가드만).
    terms.slice(0, _META_DBGRP_ROW_CAP).forEach(({ e, node }) => {
      parts.push(`<li class="amgr-row" data-key="${esc(node.key)}" data-edge-self="${esc(key)}" role="button" tabindex="0" title="클릭 = 카메라 이동 · 더블클릭 = 상세 전환">` +
        `<div class="amgr-main"><span class="amgr-arrow">◈</span><strong>${esc(node.name || node.key)}</strong></div>` +
        `<div class="amgr-sub admin-meta-graph-muted">${esc(_META_EDGE_TYPE_KO[e.type] || e.type)}${node.description ? " — " + esc(node.description) : ""}</div></li>`);
    });
    if (terms.length > _META_DBGRP_ROW_CAP) parts.push(moreRow(terms.length - _META_DBGRP_ROW_CAP));
    parts.push(`</ul></div>`);
  }
  if (around.length) {
    // 앵커에 직접 닿지 않는 이웃-이웃 관계 — 맥락 참고용으로만 접어서 나열(비클릭).
    //   detail-db-groups: 종전 20건 절단 제거 — 전량(비클릭 텍스트 행이라 그룹 축 없이 나열, 안전 가드만).
    parts.push(`<div class="admin-meta-graph-sec"><h4>주변 관계 (${around.length})</h4><ul class="amgr-list">`);
    around.slice(0, _META_DBGRP_ROW_CAP).forEach((e) => parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted"><code>${esc(nm(e.source))}</code> → <code>${esc(nm(e.target))}</code>${_metaEdgeTrustBadge(e)}</div></li>`));
    if (around.length > _META_DBGRP_ROW_CAP) parts.push(`<li class="amgr-row amgr-plain"><div class="amgr-sub admin-meta-graph-muted">… 외 ${around.length - _META_DBGRP_ROW_CAP}건 (표시 상한 — 관계 확장으로 그래프에서 확인)</div></li>`);
    parts.push(`</ul></div>`);
  }
  if (!out.length && !inn.length && !terms.length) {
    parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">기록된 관계가 없습니다 — FK 미선언 스키마일 수 있습니다. AI 능동 분석·대화 사용이 쌓이면 추정(점선) 관계가 나타납니다.</p>`);
  }
  parts.push(`<div class="amgr-actions"><button type="button" class="btn-secondary" id="amgrExpandBtn" title="이 노드의 이웃을 그래프 화면에 펼칩니다">🕸 그래프에 펼치기</button><button type="button" class="btn-secondary" id="amgrDetailBtn">📋 상세 보기</button></div>`);
  parts.push(`</div>`);
  el.innerHTML = parts.join("");
  // 초기 렌더분 행 바인딩(행 클릭·hover 강조·큐레이션). 접힌 DB 그룹은 펼칠 때 같은 bindRelRows 로 처리된다.
  bindRelRows(el);
  // detail-db-groups: DB 그룹 헤딩 접기/펼치기(+lazy 주입).
  _metaBindDbGroups(el);
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
  _metaGraphHoverPanCancel(); _metaGraphClearHoverHighlight();   // detail-hover-fx: 패널 재렌더 시 직전 hover 잔여 정리.
  _metaDbGrpLazy.clear();   // detail-db-groups: 다른 상세 뷰로 전환 — 직전 패널의 미펼침 payload 폐기(누수 방지).
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const label = _metaGraph.catLabelOf.get(catKey) || (catKey === "PC:__none__" ? "미분류" : catKey);
  const members = _metaGraph.catMembers.get(catKey) || [];
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:#8a5a1f">카테고리</span><strong>🗂 ${esc(label)}</strong> <span class="admin-meta-graph-relbadge">제품 카테고리</span></div>`);
  // graph-noise-reduce: 일반 카테고리 설명("이 제품의 접근 DB 묶음" + 밴드 조작 안내)은 카드 헤더 배지·
  //   범례 탭과 중복이라 제거. '미분류' 는 원인·해소 경로를 알려주는 상태 안내라 1줄로 유지(상세는 툴팁).
  if (catKey === "PC:__none__") {
    parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">어느 제품의 접근 DB 로도 등록되지 않은 스키마(DB) 묶음${_metaSecHelp("관리 콘솔 > 제품 > 접근 DB 에 등록하면 해당 제품 카테고리로 배치됩니다.")}</p>`);
  }
  parts.push(`<div class="admin-meta-graph-sec"><h4>스키마(DB) ${members.length}개${_metaSecHelp("행 클릭 = 그 스키마 클러스터 상세. 캔버스에서는 🗂 헤더 칩 드래그로 밴드 전체 이동, − / + 로 접기/펼치기.")}</h4><ul class="amgr-list">`);
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
    const cid = r.getAttribute("data-cid");
    r.addEventListener("click", () => _metaGraphShowClusterDetailById(cid));
    _metaBindHoverPan(r, cid);   // detail-hover-fx: hover 시 해당 스키마 클러스터로 부드러운 카메라 이동
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
    let forceAll = false;
    if (!dry || !dry.planned) {
      const totalAll = dry ? ((dry.total_tables || 0) + (dry.total_routines || 0)) : 0;
      if (!totalAll) {
        _metaGraphStatus(`${nm}: 분석 대상 없음 — 이 DB(스키마)에 테이블·함수/프로시저가 없습니다.`);
        return;
      }
      // analysis-freshness(2026-07-23, 사용자 리포트): 전부 분석 완료 상태여도 재시도를 차단하지
      //   않는다 — §55 refine-not-override(기존 분석문과 비교·융합) 전체 재분석을 confirm 후
      //   only_missing:false 로 시작. 스키마 변화·컬럼 인벤토리 보강분도 이 경로로 재탐색된다.
      //   §18.8 m3: confirm 수치는 재분석 기준 2차 dry_run(only_missing:false)의 planned/capped 로
      //   정확히 — 총계만 보여주고 백엔드 SCHEMA_CAP 절단(예: 500 승인→200 실행)을 숨기지 않는다.
      let dryAll = null;
      try {
        dryAll = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
          method: "POST", body: JSON.stringify({ schema_key: schemaKey, dry_run: true, only_missing: false }),
        });
      } catch (_) { dryAll = null; }
      const planAll = (dryAll && dryAll.planned) ? dryAll.planned : totalAll;
      const capTxtAll = (dryAll && dryAll.capped)
        ? `\n※ 상한 적용: 전체 ${dryAll.missing}개 중 이번 실행 ${dryAll.planned}개 — 완료 후 재실행하면 이어서 분석합니다.` : "";
      if (!window.confirm(`'${nm}' 의 테이블 ${dry.total_tables || 0}개 · 함수/프로시저 ${dry.total_routines || 0}개는 모두 분석 완료 상태입니다.\n\n전체 재분석을 시작할까요?\n· 기존 분석문은 삭제되지 않으며, 이전 분석과 비교·융합(refine)해 갱신됩니다.\n· 최신 스키마·관계·컬럼 기준으로 다시 탐색하며, 이번 실행 ${planAll}개 항목마다 LLM 분석이 수행됩니다(백그라운드).${capTxtAll}`)) return;
      forceAll = true;
    } else {
      const cappedTxt = dry.capped ? `\n※ 상한 적용: 미분석 ${dry.missing}개 중 이번 실행 ${dry.planned}개 — 완료 후 재실행하면 이어서 분석합니다.` : "";
      if (!window.confirm(`'${nm}' DB 전체 AI 능동 분석을 시작합니다.\n\n테이블 ${dry.total_tables}개 · 함수/프로시저 ${dry.total_routines || 0}개 · 미분석 ${dry.missing}개 · 이번 실행 ${dry.planned}개${cappedTxt}\n\n이번 실행 대상 ${dry.planned}개 항목(테이블·함수·프로시저)마다 LLM 분석이 수행됩니다(백그라운드). 진행할까요?`)) return;
    }
    let res;
    try {
      res = await apiFetch(`/api/admin/metadata/graph/analyze-schema`, {
        method: "POST",
        body: JSON.stringify(forceAll ? { schema_key: schemaKey, only_missing: false }
                                      : { schema_key: schemaKey }),
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

// graph-catcluster-scroll(사용자 요청 2026-07-28): 캔버스에서 **컨텐츠 카테고리(sim-group) 클러스터**를 선택하면
//   그 선택이 여는 '스키마 클러스터' 상세 목록에서 같은 카테고리 헤딩 위치로 패널을 스크롤한다. 캡 해제 이후
//   (cluster-detail-fulllist) 목록이 수백~수천 행이라, 캔버스에서 고른 카테고리를 패널에서 사용자가 직접
//   스크롤해 찾아야 했다(요청 마찰).
//   ⚠ 키 대조는 **fam(구분자 뒤)** 로만 한다 — 그룹 키는 `_metaSimGroups(schemaId, …)` 의 schemaId 로
//   네임스페이스되는데 캔버스는 comboId("<scope>:<schema>"), 패널은 "panel:<schemaName>" 을 쓴다.
//   구분자 뒤 fam(= "nm:"/"be:"/"role:" 토큰 또는 "misc")은 멤버 집합에서 파생돼 양쪽이 공유한다.
const _META_GKEY_SEP = "\u0001";
function _metaGroupFam(groupKey) {
  const s = String(groupKey == null ? "" : groupKey);
  const i = s.indexOf(_META_GKEY_SEP);
  return i >= 0 ? s.slice(i + 1) : "";
}
// graph-catcluster-scroll(polish, 사용자 요청 2026-07-28 ②): 패널 스크롤을 브라우저 native smooth
//   (가변·임의 duration, 장거리에서 수 초)에서 **대화 뷰 point-rail 과 동일한 280ms EaseOutExpo**
//   (app.js `POINT_SCROLL_DURATION_MS`/`_easeOutExpo`, share.js `SHARE_POINT_SCROLL_DURATION_MS`)로
//   교체한다 — "빠르게 도달 + 깔끔한 정착". 거리와 무관하게 항상 280ms 라 장거리 목록에서도 즉답감.
const _META_PANEL_SCROLL_MS = 280;
function _metaEaseOutExpo(t) { return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t); }   // f(1)=1 정확(부동소수 분기)
// 패널 aside 의 scrollTop 을 from→to 로 EaseOutExpo 구동. seqOf() 가 현재 세대와 달라지면 즉시 중단
//   (연타 시 이전 애니메이션이 새 목표를 덮어쓰지 않게 — 세대 토큰은 _metaGraph._panelFocusSeq).
function _metaAnimatePanelScroll(box, from, to, seqOf, reduce) {
  const delta = to - from;
  if (delta === 0) return;
  if (reduce) { box.scrollTop = to; return; }
  const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : null;
  if (t0 == null) { box.scrollTop = to; return; }   // performance.now 부재 폴백
  const step = (now) => {
    if (!seqOf()) return;
    const p = Math.min(1, (now - t0) / _META_PANEL_SCROLL_MS);
    box.scrollTop = from + delta * _metaEaseOutExpo(p);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// graph-catcluster-scroll(polish, 사용자 요청 2026-07-28 ②): 도착 연출 = **카테고리 헤딩 점멸 +
//   하위 멤버 행이 파도(wave)처럼 순차 점멸**, 뒤로 갈수록 점멸 알파가 **선형 감쇠**.
//   구현은 CSS 애니메이션(`.is-focus` / `.is-wave` + `--amgr-wave-a` 알파 변수 + `animation-delay`)이고
//   JS 는 대상 선정·변수 주입·정리만 한다(합성 프로퍼티만 애니메이트 — 레이아웃 무비용).
const _META_WAVE_MAX = 24;        // 파도 대상 상한 — 패널 뷰포트가 담는 행 수 정도(그 아래는 어차피 비가시)
const _META_WAVE_STEP_MS = 26;    // 행 간 지연(파도 진행 속도)
const _META_WAVE_LEAD_MS = 90;    // 헤딩 점멸이 시작된 뒤 파도가 따라붙는 offset
const _META_WAVE_DUR_MS = 420;    // 행 1개의 점멸 길이(CSS keyframes 와 동일)
let _metaWaveNodes = [];          // 현재 연출 중인 노드 — 새 연출 진입 시 즉시 원복(중첩 방지)
function _metaClearPanelWave() {
  _metaWaveNodes.forEach((el) => {
    try {
      el.classList.remove("is-focus", "is-wave");
      el.style.removeProperty("animation-delay");
      el.style.removeProperty("--amgr-wave-a");
    } catch (_) { /* detached 노드 — 무해 */ }
  });
  _metaWaveNodes = [];
}
// target 헤딩 다음부터 다음 헤딩 전까지의 **보이는** 멤버 행(접힌 그룹은 display:none 이라 제외)에
//   지연·알파를 주입한다. 알파는 A0 에서 0 까지 선형(요청: "점점 선형적으로 연하게").
function _metaRunPanelWave(target, reduce) {
  _metaClearPanelWave();
  try { target.classList.add("is-focus"); } catch (_) { return; }
  _metaWaveNodes.push(target);
  // 모션 최소화 선호: 헤딩 정적 강조만(파도는 순차 모션 그 자체라 생략 — CSS 가 .is-focus 를 무애니로 분기).
  if (reduce) return _META_WAVE_DUR_MS * 3;
  const rows = [];
  let n = target.nextElementSibling;
  while (n && !n.classList.contains("amgr-ct-group") && rows.length < _META_WAVE_MAX) {
    if (n.classList.contains("amgr-ct-row-li") && !n.classList.contains("amgr-ct-collapsed")) rows.push(n);
    n = n.nextElementSibling;
  }
  const N = rows.length;
  rows.forEach((li, i) => {
    // 선형 감쇠: 첫 행 A0, 마지막 행 ~0. N=1 이면 A0 그대로(0으로 나누지 않음).
    const a = (0.5 * (N > 1 ? (1 - i / (N - 1)) : 1)).toFixed(3);
    try {
      li.style.setProperty("--amgr-wave-a", a);
      li.style.setProperty("animation-delay", (_META_WAVE_LEAD_MS + i * _META_WAVE_STEP_MS) + "ms");
      li.classList.add("is-wave");
      _metaWaveNodes.push(li);
    } catch (_) { /* graceful */ }
  });
  return _META_WAVE_LEAD_MS + Math.max(0, N - 1) * _META_WAVE_STEP_MS + _META_WAVE_DUR_MS;
}

// 패널의 해당 컨텐츠 카테고리 헤딩으로 스크롤 + 도착 연출. 반환: 매칭 헤딩 라벨(미매칭이면 null — 상태줄 보강용).
//   스크롤 컨테이너는 aside(#metadataGraphDetail, _metaGraphDetailScrollEl) 이므로 scrollIntoView(조상까지
//   스크롤 — 관리콘솔 본문이 함께 움직임) 대신 aside.scrollTop 을 직접 계산해 국소 스크롤한다.
function _metaGraphFocusPanelGroup(fam) {
  if (!fam) return null;
  const box = _metaGraphDetailScrollEl();
  if (!box) return null;
  // 스코프를 클러스터 상세 목록으로 한정 — 검색 결과(.amgr-srch-subhead)·관련 노드 DB 그룹(.amgr-dbgrp)도
  //   같은 .amgr-ct-group 시각을 재사용하므로 ul.amgr-cluster-tables 안에서만 찾는다.
  const ul = box.querySelector("ul.amgr-cluster-tables");
  if (!ul) return null;
  const heads = ul.querySelectorAll("li.amgr-ct-group[data-group-key]");
  let target = null;
  for (let i = 0; i < heads.length; i++) {
    if (_metaGroupFam(heads[i].getAttribute("data-group-key")) === fam) { target = heads[i]; break; }
  }
  if (!target) return null;   // 캔버스/패널 그룹 분할이 어긋난 경우(멤버 집합 차이) — graceful no-op
  const seq = ++_metaGraph._panelFocusSeq;
  const fresh = () => seq === _metaGraph._panelFocusSeq;   // 더 최근 선택이 선점하면 stale
  // sticky 이력 바(.admin-meta-graph-detailnav, 표시 중일 때만)가 헤딩을 덮지 않도록 그 높이만큼 위 여백 확보.
  const nav = document.getElementById("metadataGraphDetailNav");
  const navH = (nav && !nav.hidden) ? Math.round(nav.getBoundingClientRect().height) : 0;
  let reduce = false;
  try { reduce = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (_) { reduce = false; }
  // rAF: 방금 교체된 innerHTML 의 레이아웃이 반영된 뒤 위치를 재야 clamp 되지 않는다(이력 스크롤 복원과 동형).
  requestAnimationFrame(() => {
    if (!fresh()) return;   // 더 최근 선택이 선점 — stale 스크롤 금지
    try {
      const top = box.scrollTop + (target.getBoundingClientRect().top - box.getBoundingClientRect().top) - navH - 6;
      const y = Math.max(0, Math.round(top));
      const maxTop = Math.max(0, box.scrollHeight - box.clientHeight);
      _metaAnimatePanelScroll(box, box.scrollTop, Math.min(maxTop, y), fresh, reduce);
    } catch (_) { /* graceful — 스크롤 실패해도 연출은 남긴다 */ }
    // 도착 연출(헤딩 점멸 + 멤버 파도). 재렌더로 노드가 교체돼도 stale 노드의 class 제거는 무해.
    const total = _metaRunPanelWave(target, reduce) || _META_WAVE_DUR_MS;
    setTimeout(() => { if (fresh()) _metaClearPanelWave(); }, total + 120);
  });
  const lab = target.querySelector(".amgr-ct-group-label");
  return (lab && lab.textContent) || fam;
}

// 스키마 클러스터(combo) 상세 — 스키마명·포함 테이블 목록·개수. combo:click 진입.
// focusFam(선택): 캔버스에서 고른 컨텐츠 카테고리의 fam — 렌더 후 그 헤딩으로 패널을 스크롤(graph-catcluster-scroll).
async function _metaGraphShowClusterDetailById(comboId, focusFam) {
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
  // graph-funcproc(cluster-detail-routines): 함수·프로시저(Routine)는 API 응답 형태와 무관하게 **모델에서**
  //   수집한다 — 패널은 화면 내 스키마 대상이라 모델(_metaGraph.nodes)에 이 클러스터 Routine 이 이미 로드돼 있고,
  //   build 가 Table+Routine 을 함께 sim-group 화하는 것과 정합(Routine-only 컨텐츠 카테고리 누락 해소).
  //   kind 필터(hiddenKinds, §54②) 를 build(graph-core L74-75)와 동형으로 적용 — 숨긴 kind 는 캔버스처럼 패널에서도 제외.
  let childTables = 0, childCols = 0;
  const routines = [];
  _metaGraph.nodes.forEach((n) => {
    if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) childTables += 1;
    else if (n.label === "Routine" && _metaCatParent(n.key, n.fqn) === comboId && !_metaGraph.hiddenKinds.has((n.routine_type === "function") ? "function" : "procedure")) routines.push(n);
    else if (n.label === "Column" && _metaCatParent(n.key, n.fqn) === comboId) childCols += 1;
  });
  if (!tables.length) _metaGraph.nodes.forEach((n) => { if (n.label === "Table" && _metaCatParent(n.key, n.fqn) === comboId) tables.push(n); });
  routines.sort((a, b) => _metaNatSort(a.name || a.key, b.name || b.key));
  const _focused = _metaGraphRenderClusterDetail(schemaName, schemaName, tables, childTables, childCols, null, false, comboId, routines, focusFam);
  const _rnote = routines.length ? ` · 함수·프로시저 ${routines.length}개` : "";
  // graph-catcluster-scroll: 캔버스 카테고리 선택으로 진입한 경우, 패널이 어디로 이동했는지 상태줄에 명시
  //   (스크롤이 조용히 일어나면 사용자가 위치 변화를 놓친다). 미매칭이면 기존 문구 그대로.
  const _fnote = _focused ? ` · 목록을 '${_focused}' 위치로 이동` : "";
  _metaGraphStatus(`클러스터: ${schemaName} · 테이블 ${tables.length || childTables}개${_rnote}${_fnote}`);
}

// 항목2: 클러스터 상세 카드 렌더(우측 상세 패널 body). 노드 상세(_metaGraphRenderDetail)와 동일 컨테이너를 교체.
// graph-catcluster-scroll: focusFam(선택) 이 주어지면 렌더 직후 그 컨텐츠 카테고리 헤딩으로 패널을 스크롤하고
//   매칭 라벨을 반환한다(호출자가 상태줄에 표기). 미지정/미매칭이면 null — 기존 동작 그대로.
function _metaGraphRenderClusterDetail(name, fqn, tables, childTables, childCols, totalOverride, truncated, comboId, routines, focusFam) {
  const el = document.getElementById("metadataGraphDetailBody") || document.getElementById("metadataGraphDetail");
  if (!el) return;
  _metaGraphHoverPanCancel(); _metaGraphClearHoverHighlight();   // detail-hover-fx: 패널 재렌더 시 직전 hover 잔여 정리.
  _metaDbGrpLazy.clear();   // detail-db-groups: 다른 상세 뷰로 전환 — 직전 패널의 미펼침 payload 폐기(누수 방지).
  // graph-funcproc(cluster-detail-collapse): `"` 도 이스케이프(파일 내 강한 esc 와 정합) — data-group-key/aria-label/title 등
  //   속성값이 상태-키 라운드트립까지 실어 나르므로 속성 breakout 방지(§18.8 적대 리뷰 MINOR #2 반영). 텍스트 노드엔 무해.
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  // graph-funcproc(cluster-detail-routines): 목록 집계 대상 = 테이블 + 함수·프로시저(Routine). build 가
  //   Table+Routine 을 함께 sim-group 화하므로 패널도 병합집합으로 구획해야 캔버스와 컨텐츠 카테고리가 일치하고,
  //   함수·프로시저만 있는 컨텐츠 카테고리도 목록에 나타난다. 테이블 개수/절단 표기는 기존대로 테이블 기준 유지.
  const tblList = tables || [];
  const rtnList = routines || [];
  const members = tblList.concat(rtnList);
  const nRoutines = rtnList.length;
  // graph-initview(V-G): cap 절단 시 실 총계(table_count) 우선 — 카드 배지와 패널 수치 모순 방지.
  const nTables = (totalOverride != null) ? totalOverride : (tblList.length || childTables || 0);
  const truncNote = (truncated || (totalOverride != null && totalOverride > tblList.length))
    ? ` (그래프에는 ${tblList.length}개만 표시 — 상한)` : "";
  const parts = [];
  parts.push(`<div class="admin-meta-graph-card">`);
  // graphux7(#7): 펼쳐진 스키마면 상세 패널(항상 화면 내 aside)에 전용 '접기' 버튼 — 캔버스 combo 우상단
  //   "−" 컨트롤은 큰 스키마에서 뷰포트 밖으로 벗어나 접근 불가하던 문제 해소. 패널 body 클릭으로 접히지 않게
  //   접기는 이 버튼(및 기존 "−"/우클릭 메뉴)로만 트리거.
  const _canCollapse = comboId && _metaGraph.schemaExpanded && _metaGraph.schemaExpanded.has(comboId);
  // graph-analyze-perm(Critical §12.3, 2026-07-14): 클러스터 상세 카드의 'DB 전체 AI 능동 분석' 버튼도
  //   metadata.graph.analyze 게이트 — 미보유 시 미렌더(요청: 권한 없으면 버튼 UI 미표시). 바인딩(하단
  //   getElementById)은 null-safe 라 렌더 조건만 가드하면 충분. 실 거부는 백엔드 403 이 최종 경계.
  const _canAnalyzeCluster = (typeof can === "function") && can("metadata.graph.analyze");
  parts.push(`<div class="admin-meta-graph-card-head"><span class="admin-meta-graph-badge" style="background:${_META_GRAPH_COLOR.Schema}">스키마 클러스터</span><strong>${esc(name)}</strong>${_canCollapse ? ` <button type="button" class="amgr-link" id="metaGraphClusterCollapseBtn" title="이 스키마를 카드로 접습니다(그래프에서 축소)">▦ 접기</button>` : ""}${(comboId && comboId !== _META_TERMS_COMBO && _canAnalyzeCluster) ? ` <button type="button" class="amgr-link" id="metaGraphClusterAnalyzeBtn" title="이 DB(스키마)의 미분석 항목(테이블·함수·프로시저) 전체를 AI 능동 분석합니다 — 실행 전 대상 수를 확인합니다">✨ DB 전체 AI 능동 분석</button>` : ""}</div>`);
  if (fqn && fqn !== name) parts.push(`<div class="admin-meta-graph-fqn">${esc(fqn)}</div>`);
  const _rtnDesc = nRoutines ? ` · 함수·프로시저 ${nRoutines}개` : "";
  const _clickHint = nRoutines ? "컬럼·파라미터·관계·용어" : "컬럼·관계·용어";
  // graph-noise-reduce: 카운트(데이터)만 남기고 "항목을 클릭하면 …" 조작 설명은 hover 툴팁으로.
  parts.push(`<p class="admin-meta-graph-desc admin-meta-graph-muted">테이블 ${nTables}개${_rtnDesc}${truncNote}${childCols ? ` · 표시된 컬럼 ${childCols}개` : ""}${_metaSecHelp(`이 스키마 클러스터에 속한 항목입니다. 항목을 클릭하면 ${_clickHint} 상세를 봅니다.`)}</p>`);
  if (members.length) {
    // graph-funcproc(cluster-detail-routines): 섹션 제목은 함수·프로시저가 있으면 병합집합을 반영.
    const secTitle = nRoutines ? `테이블·함수·프로시저 (${members.length})` : `테이블 (${tblList.length})`;
    // role-cluster-prefix: AI 능동 분석 완료 테이블은 역할 칩을 접두사로, 미분석은 동일 폭 빈 슬롯(라벨 좌측 정렬 유지 — 뒤틀림 방지).
    //   graph-funcproc: Routine 행은 역할 칩 대신 ƒ/⚙ 보라 칩(캔버스 칩 색과 동일)을 접두사로 — 테이블/루틴을 시각 구분.
    //   graph-funcproc(cluster-detail-collapse): 행 <li> 에 amgr-ct-row-li 클래스 부여(그룹 접힘 시 amgr-ct-collapsed 로 display:none 토글 대상).
    const rowHTML = (t, collapsed) => {
      let prefix, title;
      if (t.label === "Routine") {
        prefix = `<span class="amgr-role-chip amgr-role-chip-sm" style="background:${_META_GRAPH_COLOR.Routine};color:#fff" title="${esc(_metaRoutineKo(t.routine_type))}">${_metaRoutineIcon(t.routine_type)}</span>`;
        title = "클릭하면 이 함수·프로시저 노드를 선택합니다";
      } else {
        const role = _metaRoleOf(t.key);
        prefix = role ? _metaRoleChipHTML(role, esc, true) : `<span class="amgr-role-chip amgr-role-chip-sm amgr-role-none" aria-hidden="true"></span>`;
        title = "클릭하면 이 테이블 노드를 선택합니다";
      }
      return `<li class="amgr-ct-row-li${collapsed ? " amgr-ct-collapsed" : ""}"><button type="button" class="amgr-ct-row" data-node-key="${esc(t.key)}" title="${title}">${prefix}<code>${esc(t.name || t.fqn || "")}</code>${t.description ? `<span class="amgr-ct-desc"> — ${esc(t.description)}</span>` : ""}</button></li>`;
    };
    // graph-simgroups: 캔버스와 동일한 유사 속성 그룹으로 목록도 구획(헤딩 행) — 2그룹 이상일 때만. 실패 시 평면 폴백.
    //   graph-funcproc: 구획 입력을 members(테이블+루틴)로 확장 — Routine-only 컨텐츠 카테고리도 그룹 헤딩으로 나타난다.
    //   (collapse 컨트롤 조건 판정을 위해 h4 방출 전에 계산.)
    let sgs = null;
    try {
      const tbk = new Map(members.map((t) => [t.key, t]));
      sgs = _metaSimGroups("panel:" + String(name), members, _metaRelAdjacency(tbk));
    } catch (_) { sgs = null; }
    const _grouped = !!(sgs && sgs.length >= 2);
    // graph-funcproc(cluster-detail-collapse): 컨텐츠 카테고리별 접기/펼치기(사용자 요청). 그룹 헤딩을 클릭/키보드 토글(캐럿 ▾/▸)로
    //   멤버 행을 display 토글하고, 접힘 상태는 _metaGraph.panelGroupCollapsed(sg.key)에 유지(같은 클러스터 재렌더 간). 섹션 헤더엔
    //   '모두 접기/펼치기' 편의 컨트롤(긴 목록 탐색용). 그룹이 있을 때(_grouped)만 노출.
    const _allCollapsed = _grouped && sgs.every((sg) => _metaGraph.panelGroupCollapsed.has(sg.key));
    const _collapseAllBtn = _grouped
      ? ` <button type="button" class="amgr-link amgr-ct-collapse-all" id="metaGraphCtCollapseAll" title="모든 컨텐츠 카테고리 접기/펼치기">${_allCollapsed ? "▸ 모두 펼치기" : "▾ 모두 접기"}</button>`
      : "";
    parts.push(`<div class="admin-meta-graph-sec"><h4>${secTitle}${_collapseAllBtn}</h4><ul class="amgr-cluster-tables">`);
    // graph-funcproc(cluster-detail-fulllist): 캡 규약 재개정(사용자 요청 "전체 출력") — 직전 전역 500행 + 그룹당 25
    //   캡은 컨텐츠 카테고리 멤버 총합이 500 초과인 스키마에서 뒤쪽 그룹을 (0/n)·경계 그룹을 (3/5)로 잘랐다.
    //   이제 **모든 컨텐츠 카테고리의 전체 멤버를 렌더**한다(그룹당 캡 제거, 전역 상한은 비현실 극단 스키마의
    //   브라우저 행 방지용 안전 가드 ROW_CAP 만 유지 — 구획/평면 폴백 공통 상수). 수천 행 렌더에도 행 상호작용은
    //   아래 컨테이너(ul) 이벤트 위임으로 처리해 리스너가 O(1)(누적/바인딩 비용 안전). 헤딩 항상 방출·절단표식은 가드 경계에서만.
    const ROW_CAP = 5000;
    if (_grouped) {
      // §18.8 패널: 그룹 헤딩은 목록의 실제 구획 의미(장식 아님) → 접기/펼치기 disclosure(role="button"+aria-expanded).
      let emitted = 0;
      sgs.forEach((sg) => {
        const collapsed = _metaGraph.panelGroupCollapsed.has(sg.key);
        const shown = Math.min(sg.tables.length, Math.max(0, ROW_CAP - emitted));
        const trunc = shown < sg.tables.length ? ` <span class="amgr-ct-group-trunc">(${shown}/${sg.n})</span>` : "";
        // graph-funcproc(cluster-detail-group-hoverpan): 헤딩 hover → 해당 컨텐츠 카테고리 위치로 카메라 부드럽게 팬.
        //   타깃 = 그룹의 **첫 멤버 노드 key**(행 hover-pan 과 동일하게 노드로 팬 — 사용자 "다른 객체와 동일하게"). 첫 멤버는
        //   항상 실 노드라 진입경로(카드클릭 Local / 콤보·히스토리 ById-API)·fam 정합에 무관하게 견고하고, sim-group 은 캔버스에서
        //   조밀 박스로 팩되므로 첫 멤버로 팬하면 그 카테고리 영역이 화면에 들어온다. `_metaGraphHoverPan` 이 200ms intent 후
        //   `_metaRenderedIdFor` 로 해석 → 미렌더(접힘 스키마/컬링) 시 graceful no-op(행 동형).
        const _panKey = sg.tables[0] ? sg.tables[0].key : "";
        parts.push(`<li class="amgr-ct-group${collapsed ? " is-collapsed" : ""}" role="button" tabindex="0" aria-expanded="${!collapsed}" data-group-key="${esc(sg.key)}"${_panKey ? ` data-pan-key="${esc(_panKey)}"` : ""} title="클릭하면 이 컨텐츠 카테고리를 접거나 펼칩니다" aria-label="${esc(sg.label)} 컨텐츠 카테고리 · 항목 ${sg.n}개"><span class="amgr-ct-group-caret" aria-hidden="true">${collapsed ? "▸" : "▾"}</span><span class="amgr-ct-group-label">${esc(sg.label)}</span><span class="amgr-ct-group-n">${sg.n}</span>${trunc}</li>`);
        sg.tables.slice(0, shown).forEach((t) => { parts.push(rowHTML(t, collapsed)); emitted++; });
      });
    } else {
      members.slice(0, ROW_CAP).forEach((t) => parts.push(rowHTML(t, false)));
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
  // role-cluster-prefix + cluster-detail-fulllist: 행 클릭 → 노드 선택(_metaGraphShowDetail) + focus; hover → 카메라 pan.
  //   전체 출력(캡 해제)로 행이 수천 개가 될 수 있어 **행마다 바인딩하지 않고 컨테이너(ul)에 이벤트 위임**한다.
  //   ul 은 매 렌더 innerHTML 로 재생성되므로 위임 리스너가 누적되지 않는다(직전 ul 은 리스너와 함께 GC). mouseover/out·
  //   focusin/out 은 버블링되므로 위임 가능(mouseenter/leave·focus/blur 는 버블 안 됨). _hoverKey 로 같은 행 재-pan/중복 취소 방지.
  const _ctUl = el.querySelector("ul.amgr-cluster-tables");
  // graph-funcproc(cluster-detail-collapse): '모두 접기/펼치기' 라벨을 현재 그룹 상태로 재동기화(§18.8 적대 리뷰 MINOR #1 —
  //   개별 토글 후 라벨-동작 불일치 방지). 전부 접힘이면 '펼치기', 아니면 '접기'.
  const _syncCollapseAllLabel = () => {
    const btn = document.getElementById("metaGraphCtCollapseAll");
    if (!btn || !_ctUl) return;
    const groups = _ctUl.querySelectorAll(".amgr-ct-group[data-group-key]");
    if (!groups.length) return;
    const allCol = [...groups].every((g) => g.classList.contains("is-collapsed"));
    btn.textContent = allCol ? "▸ 모두 펼치기" : "▾ 모두 접기";
  };
  // graph-funcproc(cluster-detail-collapse): 컨텐츠 카테고리 그룹 접기/펼치기 — 헤딩 다음부터 다음 그룹 헤딩 전까지의
  //   멤버 행(amgr-ct-row-li)에 amgr-ct-collapsed(display:none) 를 토글. 접힘 상태는 _metaGraph.panelGroupCollapsed 에 유지.
  const _toggleCtGroup = (grp) => {
    if (!grp) return;
    const gk = grp.getAttribute("data-group-key");
    const collapse = !grp.classList.contains("is-collapsed");
    grp.classList.toggle("is-collapsed", collapse);
    grp.setAttribute("aria-expanded", String(!collapse));
    const caret = grp.querySelector(".amgr-ct-group-caret"); if (caret) caret.textContent = collapse ? "▸" : "▾";
    let n = grp.nextElementSibling;
    while (n && !n.classList.contains("amgr-ct-group")) { n.classList.toggle("amgr-ct-collapsed", collapse); n = n.nextElementSibling; }
    if (gk) { if (collapse) _metaGraph.panelGroupCollapsed.add(gk); else _metaGraph.panelGroupCollapsed.delete(gk); }
    _syncCollapseAllLabel();
  };
  if (_ctUl) {
    const _rowKeyOf = (e) => { const b = e.target.closest(".amgr-ct-row[data-node-key]"); return (b && _ctUl.contains(b)) ? b.getAttribute("data-node-key") : null; };
    let _hoverKey = null;
    _ctUl.addEventListener("click", (e) => {
      // 그룹 헤딩 클릭 = 접기/펼치기 토글(행 클릭보다 먼저 판정).
      const grp = e.target.closest(".amgr-ct-group[data-group-key]");
      if (grp && _ctUl.contains(grp)) { _toggleCtGroup(grp); return; }
      const k = _rowKeyOf(e);
      if (!k) return;
      _metaGraphShowDetail(k);
      const g = _metaGraph.graph, rel = _metaRenderedIdFor(k);
      if (g && rel && typeof g.focusElement === "function") { try { Promise.resolve(g.focusElement(rel, false)).catch(() => {}); } catch (_) {} }
    });
    // 키보드 접근성: 포커스된 그룹 헤딩에서 Enter/Space = 토글(Space 는 페이지 스크롤 방지).
    _ctUl.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
      const grp = e.target.closest(".amgr-ct-group[data-group-key]");
      if (grp && _ctUl.contains(grp)) { e.preventDefault(); _toggleCtGroup(grp); }
    });
    // graph-funcproc(cluster-detail-group-hoverpan): hover-pan 대상 = 행(data-node-key, 노드) **또는** 그룹 헤딩(data-pan-key,
    //   컨텐츠 카테고리 GB 박스). 둘 다 _metaGraphHoverPan 으로 동일하게 처리(200ms intent·미렌더 graceful no-op).
    const _panTargetOf = (e) => {
      const row = e.target.closest(".amgr-ct-row[data-node-key]");
      if (row && _ctUl.contains(row)) return row.getAttribute("data-node-key");
      const grp = e.target.closest(".amgr-ct-group[data-pan-key]");
      if (grp && _ctUl.contains(grp)) return grp.getAttribute("data-pan-key");
      return null;
    };
    const _hoverOn = (e) => { const k = _panTargetOf(e); if (k && k !== _hoverKey) { _hoverKey = k; _metaGraphHoverPan(k); } };
    _ctUl.addEventListener("mouseover", _hoverOn);
    _ctUl.addEventListener("focusin", _hoverOn);
    _ctUl.addEventListener("mouseout", (e) => {
      const b = e.target.closest(".amgr-ct-row[data-node-key], .amgr-ct-group[data-pan-key]");
      // 같은 행/헤딩 내부(칩↔코드·캐럿↔라벨 등) 이동은 취소하지 않음 — relatedTarget 이 그 밖으로 나갈 때만.
      if (b && (!e.relatedTarget || !b.contains(e.relatedTarget))) { _hoverKey = null; _metaGraphHoverPanCancel(); }
    });
    _ctUl.addEventListener("focusout", (e) => { if (e.target.closest(".amgr-ct-row[data-node-key], .amgr-ct-group[data-pan-key]")) { _hoverKey = null; _metaGraphHoverPanCancel(); } });
  }
  // graph-funcproc(cluster-detail-collapse): '모두 접기/펼치기' — 하나라도 펼쳐져 있으면 전부 접고, 전부 접혀 있으면 전부 펼친다.
  const _collapseAllBtnEl = document.getElementById("metaGraphCtCollapseAll");
  if (_collapseAllBtnEl && _ctUl) {
    _collapseAllBtnEl.addEventListener("click", () => {
      const groups = [..._ctUl.querySelectorAll(".amgr-ct-group[data-group-key]")];
      if (!groups.length) return;
      const anyExpanded = groups.some((g) => !g.classList.contains("is-collapsed"));
      // 하나라도 펼침 → 전부 접기, 전부 접힘 → 전부 펼치기. 라벨은 _toggleCtGroup 이 _syncCollapseAllLabel 로 갱신.
      groups.forEach((g) => { const isCol = g.classList.contains("is-collapsed"); if (anyExpanded ? !isCol : isCol) _toggleCtGroup(g); });
    });
  }
  // graph-catcluster-scroll: 모든 DOM 조립·바인딩이 끝난 뒤 스크롤(헤딩 위치가 최종 레이아웃 기준이어야 함).
  return _metaGraphFocusPanelGroup(focusFam);
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
  // graph-detail-scroll(m3): AI 박스가 로드돼 패널 높이가 바뀐 직후, 뒤로/앞으로 복원 목표를 1회 재적용
  //   (첫 rAF 복원이 짧은 콘텐츠로 clamp 됐던 하단부 스크롤을 되살림). key 불일치·미보류 시 no-op.
  _metaGraphReapplyPendingScroll(key);
}

// 폼 값 수집 — 체크박스는 boolean, 그 외는 trim 된 문자열. (number 변환은 _metaSubmitForm 에서.)


export { _metaColParent, _metaCtx, _metaCtxPoint, _metaGraphColCmp, _metaGraphCollapse, _metaGraphCollapseSchema, _metaGraphCtxForCanvas, _metaGraphCtxForCategory, _metaGraphCtxForCombo, _metaGraphCtxForContentCategory, _metaGraphCtxForEdge, _metaGraphCtxForNode, _metaGraphCtxForSchema, _metaGraphCtxHide, _metaGraphExpand, _metaGraphExpandSchema, _metaGraphFocusChip, _metaGraphHistoryGo, _metaGraphHistoryReset, _metaGraphIngest, _metaGraphInitResizer, _metaGraphRenderDetailEmpty, _metaGraphSearch, _metaGraphSetSelected, _metaGraphShowCategoryDetail, _metaGraphShowClusterDetailById, _metaGraphShowClusterDetailLocal, _metaGraphShowDetail, _metaGraphSyncAnalysisMarkers, _metaGraphToggleColumns, _metaTableHasCols };
