// ITEM-09 batch3 — graph.js L169~L569 pure move: node-role-viz: 역할 분류 시각 표식(칩·아이콘·범례).
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { _META_TERMS_COMBO, _METLAY, _METZ, _metaGraph, _metaSchemaComboOf } from "./graph-state.js?v=dev";
import { _META_GRAPH_COLOR, _metaCatParent } from "./graph-core.js?v=dev";
import { _metaColParent } from "./graph-ctxmenu.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)

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
// ── graph-edge-flow(§83): 관계선 렌더 어휘 ────────────────────────────────────
// 사용자 요구 3축을 하나의 스타일 어휘로 통합한다.
//   ① 방향성 곡선 — 곡률은 진행방향 왼쪽 고정이라 A→B 와 B→A 가 반대편 호로 갈라진다. 같은 두
//      객체 사이의 읽기·쓰기가 각각 자기 호를 가져 "관계선 2개"가 자연히 성립(Cytoscape.js 평행엣지
//      자동 bezier / Gephi 수직 컨트롤포인트 관례).
//   ② 가늘고 반투명 — 개별 선은 옅지만 **겹칠수록 alpha 가 누적**돼 허브 노드 주변이 스스로 진해진다
//      (edge density 를 투명도로 인코딩하는 정보시각화 표준 기법).
//   ③ 다발 볼륨 — 상위 부모(스키마 카드)나 집계 관계선이 품은 관계 수를 가닥 수로 표현.
// 곡률은 낮게(0.13~0.16)만 준다 — 강한 edge bundling 은 경로 추적 정확도·속도를 떨어뜨린다는 사용자
// 연구 결과가 있어, 군집 효과만 취하고 추적성은 보존하는 지점을 택했다.
// (§84 라이브 실측 반영) 곡률 상한을 카드 치수에 결속한다 — 종전 44px 는 접힌 스키마 카드 높이
// (_METLAY.CARDH=44) 와 같아, 이웃 행(GAPY=52) 카드 위로 호가 부풀어 라벨 영역을 스치는 것이 관측됐다.
// ── graph-edge-flow(§83) → graph-edge-encoding(§86): 관계선 렌더 어휘 ──────────
// 채널을 직교화한다 — 하나의 시각 속성이 하나의 의미만 담는다(사용자 지정 인코딩).
//   **굵기 = 관계의 개수**(많을수록 굵게) · **진하기(alpha) = 연결의 신뢰성**(높을수록 진하게)
//   색 = 관계 종류(FK / 루틴 / 교차DB / 스키마 집계) · 화살촉 = 방향 · 곡률 = 왕복 분리
// 기본값은 **가늘게**(단선 0.6px) 잡고 개수가 늘 때만 굵어진다. 종전(§83~§85)에는 굵기가 신뢰도를,
// 개수는 '다발 가닥' 을 담당했는데 — 두 축이 섞여 읽기 어려웠고, 다발은 줌아웃에서 화면을 더 가렸다.
// 굵기는 화면 픽셀 기준값이며 줌 정책(§86: 줌인 고정·줌아웃 비례)은 렌더러가 태운다.
// 곡률 상한은 카드 치수 결속(§84) — 접힌 카드 높이 44·행 간격 52 안에 머물러 이웃 카드를 침범하지 않는다.
const _META_EDGE_CURVE = 0.13;       // 곡률 계수(직선 길이 대비 중점 편차 비율)
const _META_EDGE_CURVE_MAX = 26;     // 편차 상한(model px)
const _META_EDGE_CURVE_MIN = 5;      // 편차 하한 — 근접 노드 왕복선도 반드시 갈라지게
// §87: 기본 굵기를 1.0px 로 올린다 — 0.6px 는 dpr 1 에서 **전 줌 구간이 서브픽셀**이라 항상 hairline
//   경로(폭 1물리픽셀 + alpha 감쇠)를 타서, 개수 축이 굵기 대신 alpha 로만 표현되고 신뢰도 채널과
//   상시 섞였다. 1.0px 부터는 dpr 1 에서도 정상 렌더 구간이라 두 축이 설계대로 분리된다.
//   "가느다랗게" 는 유지된다 — 1px 실선은 hairline 과 같은 두께이고, 끊김만 사라진다.
const _META_EDGE_W_BASE = 1.0;       // 단일 관계선의 화면 굵기(px) — "기본은 가느다랗게"(=1물리픽셀)
const _META_EDGE_W_GAIN = 0.27;      // 개수 2배당 굵기 증가분(로그 스케일)
const _META_EDGE_W_CAP = 1.6;        // 개수發 증가분 상한(최대 2.6px) — 대량 집계가 화면을 덮지 않게
// 관계 개수 → 화면 굵기(px). 1건 1.00 · 4건 1.54 · 16건 2.08 · 64건 2.60 · 그 이상 2.60 포화.
function _metaEdgeWidthFor(count) {
  const n = Math.max(1, Number(count) || 1);
  return _META_EDGE_W_BASE + Math.min(_META_EDGE_W_CAP, Math.log2(n) * _META_EDGE_W_GAIN);
}
// 곡선 키 주입(공통 축 1곳). 개수→굵기는 각 스타일 함수가 _metaEdgeWidthFor 로 직접 정한다.
function _metaEdgeFlow(s) {
  s.curve = _META_EDGE_CURVE; s.curveMax = _META_EDGE_CURVE_MAX; s.curveMin = _META_EDGE_CURVE_MIN;
  return s;
}
function _metaEdgeStyleFor(status, crossDs, count) {
  // 신뢰성 = 진하기: FK 선언·검증(trusted 0.85) > 추론 후보(candidate 0.5) > 무상태 추정(inferred 0.38).
  //   교차DB(ADR-019)는 프로브 검증이 불가해 항상 추정성 — candidate 대역 진하기 + 마젠타로 구분한다.
  // graph-zorder(§52): 신뢰 강도가 강한 선이 교차점에서 위에 오도록 소수 오프셋 유지(층 상한 COLUMN=3 미만).
  const w = _metaEdgeWidthFor(count);
  if (crossDs) return _metaEdgeFlow({ stroke: "#a855c7", lineWidth: w, strokeOpacity: 0.5, endArrow: true, zIndex: _METZ.EDGE + 0.1 });
  return _metaEdgeFlow({
    stroke: status === "trusted" ? "#6b4410" : (status === "candidate" ? "#c9a24a" : "#7c8b9e"),
    lineWidth: w,
    strokeOpacity: status === "trusted" ? 0.85 : (status === "candidate" ? 0.5 : 0.38),
    endArrow: true,
    zIndex: _METZ.EDGE + (status === "trusted" ? 0.2 : (status === "candidate" ? 0.1 : 0)) });
}
// graph-funcproc(ADR-016): 함수·프로시저 → 테이블 사용 엣지(ROUTINE_USES).
//   graph-dataflow: AGE 모델은 항상 Routine(source)→Table(target) 이지만 화살표는 **데이터 흐름**을 따른다 —
//   쓰기=루틴→테이블(endArrow), 읽기=테이블→루틴(startArrow). read·미상은 startArrow(상세 패널 kindKo 기본 '읽기'와 정합).
//   §85: 잔점선 폐지(실선). 본문 파싱으로 얻은 **확정 참조**라 AGE 에 신뢰도 등급 자체가 없다
//   (속성은 relation_type·cross_ds 뿐) — 추정성을 뜻하던 점선은 의미와 어긋났고 줌아웃에서 흩어졌다.
function _metaRoutineEdgeStyle(relationType, crossDs, count) {
  const s = { stroke: crossDs ? "#a855c7" : _META_GRAPH_COLOR.Routine,
    lineWidth: _metaEdgeWidthFor(count),
    strokeOpacity: crossDs ? 0.5 : 0.72,   // 확정 참조 → trusted 바로 아래 진하기
    zIndex: _METZ.EDGE };
  if (relationType === "write") s.endArrow = true;
  else s.startArrow = true;
  return _metaEdgeFlow(s);
}
// §57: 접힌 스키마 카드 간 집계 연결선(SCHEMA_REF) — 관계 의미와 구분되는 중립 슬레이트.
//   개수 축은 공통이고, 신뢰도는 혼합 집계라 중립 대역(0.55). 무향 집계라 화살표 없음(양 키 생략 —
//   false 금지, BLUEPRINT §3). count 라벨로 규모 병기.
function _metaSchemaRefEdgeStyle(count) {
  const n = Math.max(1, Number(count) || 1);
  return _metaEdgeFlow({ stroke: "#8fa3bf", lineWidth: _metaEdgeWidthFor(n), strokeOpacity: 0.55, zIndex: _METZ.EDGE,
    labelText: n > 1 ? String(n) : "", labelFontSize: 9, labelFill: "#64748b",
    labelBackground: true, labelBackgroundFill: "#f6f8fb", labelBackgroundOpacity: 0.85,
    labelPlacement: "center" });
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


export { _META_ROLE, _metaColStyle, _metaComboEdgesRestore, _metaComboMemberIds, _metaComboStyleFor, _metaCtlStyle, _metaDragZBoost, _metaDragZRestore, _metaEdgeFlow, _metaEdgeWidthFor, _metaEdgeStyleFor, _metaFocusAdjacency, _metaFocusKeyFor, _metaGraphBindLegendTabs, _metaGraphZAssert, _metaNodeStates, _metaRoleChipHTML, _metaRoleLegendTips, _metaRoleOf, _metaRoutineEdgeStyle, _metaRoutineStyle, _metaSchemaCardStyle, _metaSchemaCtlStyle, _metaSchemaRefEdgeStyle, _metaTableStyle, _metaTermStyle };
