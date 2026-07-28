// graph-catcluster-scroll 헤드리스 결정론 검증 — 캔버스에서 **컨텐츠 카테고리(sim-group) 클러스터**를
//   선택하면 '스키마 클러스터' 상세 목록이 같은 카테고리 헤딩 위치로 스크롤되는지 확인한다.
//   사용자 요구(2026-07-28): "그래프 뷰에서 카테고리 클러스터를 선택했을 경우 '스키마 클러스터' 항목에서
//   해당 카테고리 클러스터 위치로 스크롤".
//
// 실제 렌더/스크롤은 PixiJS·DOM 의존이라 라이브 육안은 PB-0008 이 담당한다. 여기서는 graph-ctxmenu.js /
// graph-core.js 소스에서 대상 유닛의 **본문을 그대로 추출**해(사본 아님) 의존을 test double 로 주입하고,
// 키 대조 규칙·스크롤 목표 좌표·세대 토큰·호출부 인자 매핑을 결정론적으로 검증한다.
// (test_detail_dbgroups.js 와 동일한 추출-후-vm 실행 패턴 — ES-module 이라 파일 전체 eval 은 불가.)
//
// 사용: node test_catcluster_panel_scroll.js [<graph-ctxmenu.js path>] [<graph-core.js path>]
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const GRAPH_DIR = path.join(__dirname, "..", "..", "src", "static", "graph");
const CTX = process.argv[2] || path.join(GRAPH_DIR, "graph-ctxmenu.js");
const CORE = process.argv[3] || path.join(GRAPH_DIR, "graph-core.js");
const src = fs.readFileSync(CTX, "utf8");
const coreSrc = fs.readFileSync(CORE, "utf8");
const cssSrc = fs.readFileSync(path.join(GRAPH_DIR, "graph.css"), "utf8");

const SEP = String.fromCharCode(1);   // 그룹 키 네임스페이스 구분자(_META_GKEY_SEP)

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 300)); }
}

// ── 소스에서 검증 대상 유닛 추출 ────────────────────────────────────────────────
function grab(text, re, label) {
  const m = text.match(re);
  if (!m) { console.error(`FAIL: ${label} 추출 실패 — 함수명/형식 변경?`); process.exit(1); }
  return m[0];
}
const constText = grab(src, /const _META_GKEY_SEP = "\\u0001";/, "_META_GKEY_SEP");
const fnFam = grab(src, /\nfunction _metaGroupFam\([\s\S]*?\n\}\n/, "_metaGroupFam");
const fnFocus = grab(src, /\nfunction _metaGraphFocusPanelGroup\([\s\S]*?\n\}\n/, "_metaGraphFocusPanelGroup");

// ── DOM test double ───────────────────────────────────────────────────────────
// 헤딩 li: getAttribute(data-group-key) / getBoundingClientRect / classList / querySelector(label)
function mkHead(groupKey, label, top) {
  const cls = new Set();
  return {
    _key: groupKey,
    classes: cls,
    getAttribute: (a) => (a === "data-group-key" ? groupKey : null),
    getBoundingClientRect: () => ({ top, height: 20 }),
    classList: { add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c) },
    querySelector: (s) => (s === ".amgr-ct-group-label" ? { textContent: label } : null),
  };
}
// scroll aside: scrollTop / getBoundingClientRect / querySelector(ul) / scrollTo
function mkBox(heads, opts) {
  const o = opts || {};
  const ul = {
    querySelectorAll: (s) => (s === "li.amgr-ct-group[data-group-key]" ? heads : []),
  };
  return {
    scrollTop: o.scrollTop == null ? 0 : o.scrollTop,
    scrolled: null,
    getBoundingClientRect: () => ({ top: o.boxTop == null ? 100 : o.boxTop }),
    querySelector: (s) => (s === "ul.amgr-cluster-tables" ? (o.noUl ? null : ul) : null),
    scrollTo: function (arg) { this.scrolled = arg; },
  };
}

// 유닛 실행 컨텍스트 — rAF/setTimeout 은 수집만 하고 테스트가 명시적으로 flush 한다(결정론).
function newCtx(opts) {
  const o = opts || {};
  const rafQ = [], timerQ = [];
  const sandbox = {
    console, Math, String, Number,
    _metaGraph: { _panelFocusSeq: 0 },
    _metaGraphDetailScrollEl: () => o.box || null,
    document: { getElementById: (id) => (id === "metadataGraphDetailNav" ? (o.nav || null) : null) },
    window: {
      matchMedia: o.noMatchMedia ? undefined : ((q) => ({ matches: !!o.reduceMotion && /reduce/.test(q) })),
    },
    requestAnimationFrame: (fn) => { rafQ.push(fn); return rafQ.length; },
    setTimeout: (fn, ms) => { timerQ.push({ fn, ms }); return timerQ.length; },
  };
  vm.createContext(sandbox);
  vm.runInContext(`${constText}\n${fnFam}\n${fnFocus}\n`, sandbox);
  return { sandbox, rafQ, timerQ, flush: () => { while (rafQ.length) rafQ.shift()(); } };
}

// ── ① fam 추출: 구분자 뒤만 취한다(네임스페이스 무시) ─────────────────────────
{
  const c = newCtx({});
  const fam = c.sandbox._metaGroupFam;
  check("① fam = 구분자 뒤 토큰(캔버스 키)", fam("mssql-web-qa:masangsoftweb" + SEP + "nm:munpia") === "nm:munpia");
  check("① fam = 구분자 뒤 토큰(패널 키)", fam("panel:masangsoftweb" + SEP + "nm:munpia") === "nm:munpia");
  check("① 구분자 없으면 빈 문자열", fam("no-separator-here") === "");
  check("① null/undefined graceful", fam(null) === "" && fam(undefined) === "");
  check("① fam 자체에 콜론 포함해도 절단 안 함", fam("x" + SEP + "be:12") === "be:12");
}

// ── ② 핵심: 캔버스 키와 패널 키의 네임스페이스가 달라도 같은 카테고리로 매칭 ──
//    (이 계약이 깨지면 스크롤이 조용히 no-op 이 된다 — 회귀 방지의 본체)
{
  const heads = [
    mkHead("panel:masangsoftweb" + SEP + "nm:account", "게임 계정 매칭", 300),
    mkHead("panel:masangsoftweb" + SEP + "nm:munpia", "문피아 계정 이전", 900),
    mkHead("panel:masangsoftweb" + SEP + "misc", "기타", 1500),
  ];
  const box = mkBox(heads, { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  // 캔버스에서 고른 그룹 키는 "<comboId>\u0001<fam>" — comboId 는 패널의 "panel:<name>" 과 다르다.
  const canvasKey = "mssql-web-qa:masangsoftweb" + SEP + "nm:munpia";
  const label = c.sandbox._metaGraphFocusPanelGroup(c.sandbox._metaGroupFam(canvasKey));
  check("② 네임스페이스 달라도 fam 으로 매칭 — 라벨 반환", label === "문피아 계정 이전", label);
  c.flush();
  // 목표 y = box.scrollTop + (head.top - box.top) - navH(0) - 6 = 0 + (900-100) - 0 - 6 = 794
  check("② 스크롤 목표 = 헤딩 상대 위치 - 여백", box.scrolled && box.scrolled.top === 794, box.scrolled);
  check("② 기본은 smooth 스크롤", box.scrolled && box.scrolled.behavior === "smooth", box.scrolled);
  check("② 도착 강조 클래스 부여", heads[1].classList.contains("is-focus"));
  check("② 강조 해제 타이머 예약(1.8s)", c.timerQ.length === 1 && c.timerQ[0].ms === 1800);
  c.timerQ[0].fn();
  check("② 타이머 발화 시 강조 해제", !heads[1].classList.contains("is-focus"));
  check("② 다른 그룹은 강조되지 않음", !heads[0].classList.contains("is-focus") && !heads[2].classList.contains("is-focus"));
}

// ── ③ sticky 이력 바가 표시 중이면 그 높이만큼 위 여백 확보 ────────────────────
{
  const heads = [mkHead("panel:s" + SEP + "misc", "기타", 500)];
  const box = mkBox(heads, { scrollTop: 40, boxTop: 100 });
  const nav = { hidden: false, getBoundingClientRect: () => ({ height: 44 }) };
  const c = newCtx({ box, nav });
  c.sandbox._metaGraphFocusPanelGroup("misc");
  c.flush();
  // 40 + (500-100) - 44 - 6 = 390
  check("③ nav 표시 시 nav 높이만큼 위 여백", box.scrolled && box.scrolled.top === 390, box.scrolled);
}
{
  const heads = [mkHead("panel:s" + SEP + "misc", "기타", 500)];
  const box = mkBox(heads, { scrollTop: 40, boxTop: 100 });
  const nav = { hidden: true, getBoundingClientRect: () => ({ height: 44 }) };
  const c = newCtx({ box, nav });
  c.sandbox._metaGraphFocusPanelGroup("misc");
  c.flush();
  check("③ nav 숨김(이력 ≤1)이면 보정 없음", box.scrolled && box.scrolled.top === 434, box.scrolled);
}

// ── ④ 음수 목표는 0 으로 클램프(첫 그룹이 이미 최상단) ────────────────────────
{
  const heads = [mkHead("panel:s" + SEP + "misc", "기타", 100)];
  const box = mkBox(heads, { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("misc");
  c.flush();
  check("④ 음수 목표 클램프 → 0", box.scrolled && box.scrolled.top === 0, box.scrolled);
}

// ── ⑤ 세대 토큰: 더 최근 선택이 rAF 이전에 들어오면 stale 스크롤 폐기 ──────────
{
  const headsA = [mkHead("panel:s" + SEP + "a", "A", 900)];
  const boxA = mkBox(headsA, { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box: boxA });
  c.sandbox._metaGraphFocusPanelGroup("a");        // 1차 선택 — rAF 대기
  c.sandbox._metaGraph._panelFocusSeq += 1;         // 그 사이 더 최근 선택 발생(연타)
  c.flush();
  check("⑤ stale rAF 은 스크롤하지 않음", boxA.scrolled === null, boxA.scrolled);
  check("⑤ stale rAF 은 강조도 하지 않음", !headsA[0].classList.contains("is-focus"));
}

// ── ⑥ graceful no-op: fam 없음 / 컨테이너 없음 / 목록 없음 / 미매칭 ───────────
{
  const heads = [mkHead("panel:s" + SEP + "a", "A", 900)];
  const box = mkBox(heads, {});
  const c = newCtx({ box });
  check("⑥ fam 미지정 → null(기존 동작 보존)", c.sandbox._metaGraphFocusPanelGroup("") === null && c.sandbox._metaGraphFocusPanelGroup(undefined) === null);
  check("⑥ 미매칭 fam → null", c.sandbox._metaGraphFocusPanelGroup("nope") === null);
  c.flush();
  check("⑥ 미매칭이면 스크롤 없음", box.scrolled === null);

  const c2 = newCtx({ box: null });
  check("⑥ 스크롤 컨테이너 부재 → null", c2.sandbox._metaGraphFocusPanelGroup("a") === null);

  const box3 = mkBox(heads, { noUl: true });
  const c3 = newCtx({ box: box3 });
  check("⑥ 클러스터 목록(ul) 부재 → null", c3.sandbox._metaGraphFocusPanelGroup("a") === null);
}

// ── ⑦ 모션 최소화 선호 시 즉시 스크롤 ─────────────────────────────────────────
{
  const heads = [mkHead("panel:s" + SEP + "a", "A", 900)];
  const box = mkBox(heads, {});
  const c = newCtx({ box, reduceMotion: true });
  c.sandbox._metaGraphFocusPanelGroup("a");
  c.flush();
  check("⑦ prefers-reduced-motion → behavior:auto", box.scrolled && box.scrolled.behavior === "auto", box.scrolled);
}
{
  const heads = [mkHead("panel:s" + SEP + "a", "A", 900)];
  const box = mkBox(heads, {});
  const c = newCtx({ box, noMatchMedia: true });
  c.sandbox._metaGraphFocusPanelGroup("a");
  c.flush();
  check("⑦ matchMedia 미지원 환경도 throw 없이 스크롤", box.scrolled && box.scrolled.top === 794, box.scrolled);
}

// ── ⑧ 호출부 인자 매핑 회귀 방지(소스 계약) ───────────────────────────────────
//    유닛만 검증하면 호출부가 fam 을 안 넘겨도 전건 PASS 한다 — test_detail_dbgroups.js 의
//    §18.8 적대 리뷰 지적(호출부 미실행)과 동일한 사각을 여기서 미리 닫는다.
{
  // GB/GH prefix 분기는 core 에 여러 개(드래그 리지드 경로 등) — 좌클릭 라우팅 분기(sep 로 스키마 분리)만 앵커.
  const gbBranch = coreSrc.match(/if \(String\(id\)\.startsWith\("GB:"\) \|\| String\(id\)\.startsWith\("GH:"\)\) \{\n    const gk = String\(id\)\.slice\(3\), sep = [\s\S]*?\n  \}/);
  check("⑧ graph-core GB/GH 좌클릭 분기 존재", !!gbBranch);
  check("⑧ GB/GH 좌클릭이 fam 을 2번째 인자로 전달",
    !!gbBranch && /_metaGraphShowClusterDetailById\(sc, gk\.slice\(sep \+ 1\)\)/.test(gbBranch[0]), gbBranch && gbBranch[0]);

  const ctxItem = src.match(/label: "소속 스키마 상세"[\s\S]*?\}\);/);
  check("⑧ 컨텐츠 카테고리 우클릭 '소속 스키마 상세'가 fam 전달",
    !!ctxItem && /_metaGraphShowClusterDetailById\(schemaKey, key\.slice\(sep \+ 1\)\)/.test(ctxItem[0]), ctxItem && ctxItem[0]);

  check("⑧ ShowClusterDetailById 가 focusFam 파라미터 보유",
    /async function _metaGraphShowClusterDetailById\(comboId, focusFam\)/.test(src));
  check("⑧ ShowClusterDetailById → RenderClusterDetail 로 focusFam 전달",
    /_metaGraphRenderClusterDetail\(schemaName, schemaName, tables, childTables, childCols, null, false, comboId, routines, focusFam\)/.test(src));
  check("⑧ RenderClusterDetail 이 focusFam 파라미터 보유",
    /function _metaGraphRenderClusterDetail\(name, fqn, tables, childTables, childCols, totalOverride, truncated, comboId, routines, focusFam\)/.test(src));
  check("⑧ RenderClusterDetail 이 FocusPanelGroup 결과를 반환(상태줄 보강 소스)",
    /return _metaGraphFocusPanelGroup\(focusFam\);/.test(src));

  // 헤딩 li 가 data-group-key 를 계속 방출하는지(매칭 앵커 소실 방지)
  check("⑧ 패널 헤딩이 data-group-key 방출", /class="amgr-ct-group\$\{collapsed \? " is-collapsed" : ""\}" role="button" tabindex="0" aria-expanded="\$\{!collapsed\}" data-group-key="\$\{esc\(sg\.key\)\}"/.test(src));
  // 패널 그룹 키 네임스페이스가 "panel:" 접두라는 전제(fam-only 대조의 근거)
  check("⑧ 패널 sim-group 은 'panel:' 네임스페이스", /_metaSimGroups\("panel:" \+ String\(name\), members,/.test(src));
}

// ── ⑨ CSS 강조 클래스 존재(JS 가 붙이는 클래스에 스타일이 없으면 무음 실패) ──
{
  check("⑨ .amgr-ct-group.is-focus 규칙 존재", /\.amgr-ct-group\.is-focus\s*\{/.test(cssSrc));
  check("⑨ 강조 keyframes 존재", /@keyframes amgrCtGroupFocus/.test(cssSrc));
  check("⑨ prefers-reduced-motion 대응 존재", /prefers-reduced-motion: reduce\)\s*\{\s*\n\s*\.amgr-ct-group\.is-focus/.test(cssSrc));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
