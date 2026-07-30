// graph-catcluster-scroll 헤드리스 결정론 검증 — 캔버스에서 **컨텐츠 카테고리(sim-group) 클러스터**를
//   선택하면 '스키마 클러스터' 상세 목록이 같은 카테고리 헤딩 위치로 스크롤되는지 확인한다.
//   사용자 요구(2026-07-28): "그래프 뷰에서 카테고리 클러스터를 선택했을 경우 '스키마 클러스터' 항목에서
//   해당 카테고리 클러스터 위치로 스크롤".
//   polish(2026-07-28 ②): ① 스크롤을 대화 뷰 point-rail 과 동일한 **280ms EaseOutExpo** 로 단축,
//   ② 도착 연출을 **헤딩 점멸 + 하위 멤버 행 파도 순차 점멸(알파 선형 감쇠)** 로 개선.
//
// 실제 렌더/스크롤은 PixiJS·DOM 의존이라 라이브 육안은 PB-0008 이 담당한다. 여기서는 graph-ctxmenu.js /
// graph-core.js 소스에서 대상 유닛의 **본문을 그대로 추출**해(사본 아님) 의존을 test double 로 주입하고,
// 키 대조 규칙·스크롤 곡선·파도 지연/알파·세대 토큰·호출부 인자 매핑을 결정론적으로 검증한다.
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
const constSep = grab(src, /const _META_GKEY_SEP = "\\u0001";/, "_META_GKEY_SEP");
const fnFam = grab(src, /\nfunction _metaGroupFam\([\s\S]*?\n\}\n/, "_metaGroupFam");
const constScroll = grab(src, /const _META_PANEL_SCROLL_MS = \d+;/, "_META_PANEL_SCROLL_MS");
const fnEase = grab(src, /\nfunction _metaEaseOutExpo\(.*?\n/, "_metaEaseOutExpo");
const fnAnim = grab(src, /\nfunction _metaAnimatePanelScroll\([\s\S]*?\n\}\n/, "_metaAnimatePanelScroll");
const constWave = grab(src, /const _META_WAVE_MAX = [\s\S]*?let _metaWaveNodes = \[\];/, "wave 상수");
const fnClear = grab(src, /\nfunction _metaClearPanelWave\([\s\S]*?\n\}\n/, "_metaClearPanelWave");
const fnWave = grab(src, /\nfunction _metaRunPanelWave\([\s\S]*?\n\}\n/, "_metaRunPanelWave");
const fnFocus = grab(src, /\nfunction _metaGraphFocusPanelGroup\([\s\S]*?\n\}\n/, "_metaGraphFocusPanelGroup");

const UNITS = [constSep, fnFam, constScroll, fnEase, fnAnim, constWave, fnClear, fnWave, fnFocus].join("\n");

// ── DOM test double ───────────────────────────────────────────────────────────
function mkStyle() {
  const props = {};
  return {
    props,
    setProperty: (k, v) => { props[k] = v; },
    removeProperty: (k) => { delete props[k]; },
  };
}
function mkEl(classes, extra) {
  const cls = new Set(classes || []);
  return Object.assign({
    classes: cls,
    style: mkStyle(),
    classList: {
      add: function () { for (let i = 0; i < arguments.length; i++) cls.add(arguments[i]); },
      remove: function () { for (let i = 0; i < arguments.length; i++) cls.delete(arguments[i]); },
      contains: (c) => cls.has(c),
    },
    nextElementSibling: null,
    getAttribute: () => null,
    getBoundingClientRect: () => ({ top: 0, height: 20 }),
    querySelector: () => null,
  }, extra || {});
}
// 헤딩 li
function mkHead(groupKey, label, top) {
  return mkEl(["amgr-ct-group"], {
    _key: groupKey,
    getAttribute: (a) => (a === "data-group-key" ? groupKey : null),
    getBoundingClientRect: () => ({ top, height: 20 }),
    querySelector: (s) => (s === ".amgr-ct-group-label" ? { textContent: label } : null),
  });
}
// 멤버 행 li (collapsed=true 면 접힌 그룹의 숨은 행)
function mkRow(collapsed) {
  return mkEl(collapsed ? ["amgr-ct-row-li", "amgr-ct-collapsed"] : ["amgr-ct-row-li"]);
}
// nodes 를 형제 체인으로 연결
function chain(nodes) {
  for (let i = 0; i < nodes.length - 1; i++) nodes[i].nextElementSibling = nodes[i + 1];
  if (nodes.length) nodes[nodes.length - 1].nextElementSibling = null;
  return nodes;
}
// scroll aside
function mkBox(heads, opts) {
  const o = opts || {};
  const ul = { querySelectorAll: (s) => (s === "li.amgr-ct-group[data-group-key]" ? heads : []) };
  return {
    scrollTop: o.scrollTop == null ? 0 : o.scrollTop,
    scrollHeight: o.scrollHeight == null ? 100000 : o.scrollHeight,
    clientHeight: o.clientHeight == null ? 600 : o.clientHeight,
    getBoundingClientRect: () => ({ top: o.boxTop == null ? 100 : o.boxTop }),
    querySelector: (s) => (s === "ul.amgr-cluster-tables" ? (o.noUl ? null : ul) : null),
  };
}

// 유닛 실행 컨텍스트 — rAF/setTimeout 은 수집만 하고 테스트가 명시적으로 구동한다(결정론).
function newCtx(opts) {
  const o = opts || {};
  const rafQ = [], timerQ = [];
  let nowMs = 1000;
  const sandbox = {
    console, Math, String, Number,
    _metaGraph: { _panelFocusSeq: 0 },
    _metaGraphDetailScrollEl: () => o.box || null,
    document: { getElementById: (id) => (id === "metadataGraphDetailNav" ? (o.nav || null) : null) },
    window: { matchMedia: o.noMatchMedia ? undefined : ((q) => ({ matches: !!o.reduceMotion && /reduce/.test(q) })) },
    performance: o.noPerfNow ? {} : { now: () => nowMs },
    requestAnimationFrame: (fn) => { rafQ.push(fn); return rafQ.length; },
    setTimeout: (fn, ms) => { timerQ.push({ fn, ms }); return timerQ.length; },
  };
  vm.createContext(sandbox);
  vm.runInContext(UNITS + "\n", sandbox);
  const tick = (dt) => { nowMs += (dt == null ? 16 : dt); const q = rafQ.splice(0); q.forEach((fn) => fn(nowMs)); };
  return {
    sandbox, rafQ, timerQ,
    now: () => nowMs,
    tick,
    // 애니메이션이 자기 자신을 재예약하므로 큐가 빌 때까지(상한) 프레임을 돌린다.
    runAnim: (maxFrames) => { let i = 0; while (rafQ.length && i < (maxFrames || 80)) { i++; tick(16); } return i; },
  };
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

// ── ② EaseOutExpo 곡선 계약(대화 뷰 point-rail 과 동일 식) ────────────────────
{
  const c = newCtx({});
  const e = c.sandbox._metaEaseOutExpo;
  check("② f(0)=0", e(0) === 0);
  check("② f(1)=1 정확", e(1) === 1);
  check("② t>1 클램프", e(1.5) === 1);
  check("② 단조 증가", e(0.1) < e(0.3) && e(0.3) < e(0.6) && e(0.6) < e(0.9));
  // EaseOutExpo 특성 — 초반에 크게 움직인다(절반 시점에 이미 96% 이상 진행).
  check("② 초반 급가속(t=0.5 에서 ≥96%)", e(0.5) >= 0.96, e(0.5));
  check("② duration = 280ms (point-rail 정합)", /const _META_PANEL_SCROLL_MS = 280;/.test(src));
}

// ── ③ 핵심: 네임스페이스가 달라도 fam 으로 매칭 + 280ms 안에 목표 정착 ────────
{
  const heads = [
    mkHead("panel:masangsoftweb" + SEP + "nm:account", "게임 계정 매칭", 300),
    mkHead("panel:masangsoftweb" + SEP + "nm:munpia", "문피아 계정 이전", 900),
    mkHead("panel:masangsoftweb" + SEP + "misc", "기타", 1500),
  ];
  chain(heads);
  const box = mkBox(heads, { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  const canvasKey = "mssql-web-qa:masangsoftweb" + SEP + "nm:munpia";
  const label = c.sandbox._metaGraphFocusPanelGroup(c.sandbox._metaGroupFam(canvasKey));
  check("③ 네임스페이스 달라도 fam 으로 매칭 — 라벨 반환", label === "문피아 계정 이전", label);
  c.tick();                    // focus rAF — 스크롤 애니메이션 시작 + 연출 부여
  check("③ 첫 프레임엔 아직 목표 미도달(애니메이션 구동 중)", box.scrollTop < 794, box.scrollTop);
  const frames = c.runAnim();
  // 목표 y = 0 + (900-100) - navH(0) - 6 = 794
  check("③ 정착 = 헤딩 상대 위치 - 여백", Math.round(box.scrollTop) === 794, box.scrollTop);
  // 280ms / 16ms ≈ 18 프레임 — 20 프레임(≈320ms)을 넘지 않는다(native smooth 대비 단축 계약).
  check("③ 애니메이션이 ~280ms 내 종료(≤20 프레임)", frames <= 20, frames);
  check("③ 도착 강조 클래스 부여", heads[1].classList.contains("is-focus"));
  check("③ 다른 그룹은 강조되지 않음", !heads[0].classList.contains("is-focus") && !heads[2].classList.contains("is-focus"));
}

// ── ④ 파도: 하위 멤버 행 순차 지연 + 알파 선형 감쇠 ──────────────────────────
{
  const head = mkHead("panel:s" + SEP + "a", "A", 500);
  const rows = [mkRow(), mkRow(), mkRow(), mkRow(), mkRow()];
  const nextHead = mkHead("panel:s" + SEP + "b", "B", 900);
  const tail = [mkRow(), mkRow()];
  chain([head].concat(rows, [nextHead], tail));
  const box = mkBox([head, nextHead], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a");
  c.tick();
  const waved = rows.filter((r) => r.classList.contains("is-wave"));
  check("④ 그룹 멤버 전원이 파도 대상", waved.length === 5, waved.length);
  const delays = rows.map((r) => parseInt(r.style.props["animation-delay"], 10));
  check("④ 지연이 26ms 간격 순차(lead 90ms)", JSON.stringify(delays) === JSON.stringify([90, 116, 142, 168, 194]), delays);
  const alphas = rows.map((r) => parseFloat(r.style.props["--amgr-wave-a"]));
  check("④ 알파 선형 감쇠 — 첫 0.5 · 마지막 0", alphas[0] === 0.5 && alphas[4] === 0, alphas);
  const diffs = [1, 2, 3, 4].map((i) => +(alphas[i - 1] - alphas[i]).toFixed(3));
  check("④ 감쇠 간격이 균일(=선형)", diffs.every((d) => Math.abs(d - diffs[0]) < 1e-6), diffs);
  check("④ 단조 감소", alphas.every((a, i) => i === 0 || a < alphas[i - 1]), alphas);
  check("④ 다음 그룹 헤딩에서 파도 종료(경계)", !nextHead.classList.contains("is-wave"));
  check("④ 다음 그룹 멤버는 미포함", tail.every((r) => !r.classList.contains("is-wave")));
  // 정리 타이머: lead 90 + (5-1)*26 + 420 + 120 = 734ms
  check("④ 정리 타이머 = 파도 총 길이 + 여유", c.timerQ.length === 1 && c.timerQ[0].ms === 734, c.timerQ.map((t) => t.ms));
  c.timerQ[0].fn();
  check("④ 정리 후 클래스·인라인 변수 제거", !head.classList.contains("is-focus")
    && rows.every((r) => !r.classList.contains("is-wave") && r.style.props["--amgr-wave-a"] === undefined && r.style.props["animation-delay"] === undefined));
}

// ── ⑤ 파도 상한 + 접힌 행 제외 + 단일 멤버 ────────────────────────────────────
{
  const head = mkHead("panel:s" + SEP + "a", "A", 500);
  const rows = []; for (let i = 0; i < 40; i++) rows.push(mkRow());
  chain([head].concat(rows));
  const box = mkBox([head], {});
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick();
  const waved = rows.filter((r) => r.classList.contains("is-wave"));
  check("⑤ 파도 상한 24행(뷰포트 밖은 비가시라 제외)", waved.length === 24, waved.length);
}
{
  const head = mkHead("panel:s" + SEP + "a", "A", 500);
  const rows = [mkRow(true), mkRow(true), mkRow(true)];   // 접힌 그룹(display:none)
  chain([head].concat(rows));
  const box = mkBox([head], {});
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick();
  check("⑤ 접힌 그룹은 헤딩만 점멸(숨은 행에 파도 미주입)",
    head.classList.contains("is-focus") && rows.every((r) => !r.classList.contains("is-wave")));
}
{
  const head = mkHead("panel:s" + SEP + "a", "A", 500);
  const rows = [mkRow()];
  chain([head].concat(rows));
  const box = mkBox([head], {});
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick();
  check("⑤ 멤버 1개면 0으로 나누지 않고 알파 = 0.5", parseFloat(rows[0].style.props["--amgr-wave-a"]) === 0.5, rows[0].style.props);
}

// ── ⑥ sticky 이력 바 보정 + 클램프 ────────────────────────────────────────────
{
  const head = mkHead("panel:s" + SEP + "misc", "기타", 500);
  chain([head]);
  const box = mkBox([head], { scrollTop: 40, boxTop: 100 });
  const nav = { hidden: false, getBoundingClientRect: () => ({ height: 44 }) };
  const c = newCtx({ box, nav });
  c.sandbox._metaGraphFocusPanelGroup("misc"); c.tick(); c.runAnim();
  // 40 + (500-100) - 44 - 6 = 390
  check("⑥ nav 표시 시 nav 높이만큼 위 여백", Math.round(box.scrollTop) === 390, box.scrollTop);
}
{
  const head = mkHead("panel:s" + SEP + "misc", "기타", 500);
  chain([head]);
  const box = mkBox([head], { scrollTop: 40, boxTop: 100 });
  const nav = { hidden: true, getBoundingClientRect: () => ({ height: 44 }) };
  const c = newCtx({ box, nav });
  c.sandbox._metaGraphFocusPanelGroup("misc"); c.tick(); c.runAnim();
  check("⑥ nav 숨김(이력 ≤1)이면 보정 없음", Math.round(box.scrollTop) === 434, box.scrollTop);
}
{
  const head = mkHead("panel:s" + SEP + "misc", "기타", 100);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("misc"); c.tick(); c.runAnim();
  check("⑥ 음수 목표 클램프 → 0(이동 없음)", box.scrollTop === 0, box.scrollTop);
}
{
  // scrollHeight-clientHeight 상한 클램프 — 목표가 바닥을 넘으면 바닥에 멈춘다.
  const head = mkHead("panel:s" + SEP + "misc", "기타", 5000);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100, scrollHeight: 2000, clientHeight: 600 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("misc"); c.tick(); c.runAnim();
  check("⑥ 하단 초과 목표는 maxTop 클램프", Math.round(box.scrollTop) === 1400, box.scrollTop);
}

// ── ⑦ 세대 토큰: 더 최근 선택이 rAF/애니메이션을 선점 ─────────────────────────
{
  const head = mkHead("panel:s" + SEP + "a", "A", 900);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a");     // 1차 — rAF 대기
  c.sandbox._metaGraph._panelFocusSeq += 1;     // 그 사이 더 최근 선택(연타)
  c.tick(); c.runAnim();
  check("⑦ stale rAF 은 스크롤하지 않음", box.scrollTop === 0, box.scrollTop);
  check("⑦ stale rAF 은 연출도 하지 않음", !head.classList.contains("is-focus"));
}
{
  // 애니메이션 진행 중 새 선택이 들어오면 진행 중 프레임이 즉시 중단된다.
  const head = mkHead("panel:s" + SEP + "a", "A", 5000);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100, scrollHeight: 100000, clientHeight: 600 });
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a");
  c.tick();                                     // 애니메이션 첫 프레임 예약
  c.tick();                                     // 1프레임 진행
  const mid = box.scrollTop;
  c.sandbox._metaGraph._panelFocusSeq += 1;     // 새 선택 선점
  c.runAnim();
  check("⑦ 진행 중 애니메이션이 새 선택에 선점되어 중단", box.scrollTop === mid && mid > 0, { mid, after: box.scrollTop });
}
{
  // 새 연출은 직전 연출의 잔여 클래스를 즉시 원복한다(중첩 방지).
  const h1 = mkHead("panel:s" + SEP + "a", "A", 300);
  const r1 = [mkRow(), mkRow()];
  const h2 = mkHead("panel:s" + SEP + "b", "B", 900);
  const r2 = [mkRow()];
  chain([h1].concat(r1, [h2], r2));
  const box = mkBox([h1, h2], {});
  const c = newCtx({ box });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick();
  check("⑦ 1차 연출 부여", h1.classList.contains("is-focus") && r1[0].classList.contains("is-wave"));
  c.sandbox._metaGraphFocusPanelGroup("b"); c.tick();
  check("⑦ 2차 연출 시 1차 잔여 즉시 원복", !h1.classList.contains("is-focus") && r1.every((r) => !r.classList.contains("is-wave")));
  check("⑦ 2차 연출은 정상 부여", h2.classList.contains("is-focus") && r2[0].classList.contains("is-wave"));
}

// ── ⑧ graceful no-op: fam 없음 / 컨테이너 없음 / 목록 없음 / 미매칭 ───────────
{
  const head = mkHead("panel:s" + SEP + "a", "A", 900);
  chain([head]);
  const box = mkBox([head], {});
  const c = newCtx({ box });
  check("⑧ fam 미지정 → null(기존 동작 보존)", c.sandbox._metaGraphFocusPanelGroup("") === null && c.sandbox._metaGraphFocusPanelGroup(undefined) === null);
  check("⑧ 미매칭 fam → null", c.sandbox._metaGraphFocusPanelGroup("nope") === null);
  c.tick(); c.runAnim();
  check("⑧ 미매칭이면 스크롤 없음", box.scrollTop === 0);

  const c2 = newCtx({ box: null });
  check("⑧ 스크롤 컨테이너 부재 → null", c2.sandbox._metaGraphFocusPanelGroup("a") === null);

  const box3 = mkBox([head], { noUl: true });
  const c3 = newCtx({ box: box3 });
  check("⑧ 클러스터 목록(ul) 부재 → null", c3.sandbox._metaGraphFocusPanelGroup("a") === null);
}

// ── ⑨ 모션 최소화 선호: 즉시 점프 + 파도 없음 ────────────────────────────────
{
  const head = mkHead("panel:s" + SEP + "a", "A", 900);
  const rows = [mkRow(), mkRow(), mkRow()];
  chain([head].concat(rows));
  const box = mkBox([head], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box, reduceMotion: true });
  c.sandbox._metaGraphFocusPanelGroup("a");
  c.tick();
  check("⑨ reduced-motion → 첫 프레임에 즉시 정착(애니메이션 없음)", Math.round(box.scrollTop) === 794, box.scrollTop);
  check("⑨ reduced-motion → 헤딩 강조만, 파도 미주입",
    head.classList.contains("is-focus") && rows.every((r) => !r.classList.contains("is-wave")));
}
{
  const head = mkHead("panel:s" + SEP + "a", "A", 900);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box, noMatchMedia: true });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick(); c.runAnim();
  check("⑨ matchMedia 미지원 환경도 throw 없이 정착", Math.round(box.scrollTop) === 794, box.scrollTop);
}
{
  const head = mkHead("panel:s" + SEP + "a", "A", 900);
  chain([head]);
  const box = mkBox([head], { scrollTop: 0, boxTop: 100 });
  const c = newCtx({ box, noPerfNow: true });
  c.sandbox._metaGraphFocusPanelGroup("a"); c.tick();
  check("⑨ performance.now 부재 → 즉시 점프 폴백", Math.round(box.scrollTop) === 794, box.scrollTop);
}

// ── ⑩ 호출부 인자 매핑 회귀 방지(소스 계약) ───────────────────────────────────
//    유닛만 검증하면 호출부가 fam 을 안 넘겨도 전건 PASS 한다 — test_detail_dbgroups.js 의
//    §18.8 적대 리뷰 지적(호출부 미실행)과 동일한 사각을 여기서 미리 닫는다.
{
  // GB/GH prefix 분기는 core 에 여러 개(드래그 리지드 경로 등) — 좌클릭 라우팅 분기(sep 로 스키마 분리)만 앵커.
  const gbBranch = coreSrc.match(/if \(String\(id\)\.startsWith\("GB:"\) \|\| String\(id\)\.startsWith\("GH:"\)\) \{\n    const gk = String\(id\)\.slice\(3\), sep = [\s\S]*?\n  \}/);
  check("⑩ graph-core GB/GH 좌클릭 분기 존재", !!gbBranch);
  check("⑩ GB/GH 좌클릭이 fam 을 2번째 인자로 전달",
    !!gbBranch && /_metaGraphShowClusterDetailById\(sc, gk\.slice\(sep \+ 1\)\)/.test(gbBranch[0]), gbBranch && gbBranch[0]);

  const ctxItem = src.match(/label: "소속 스키마 상세"[\s\S]*?\}\);/);
  check("⑩ 컨텐츠 카테고리 우클릭 '소속 스키마 상세'가 fam 전달",
    !!ctxItem && /_metaGraphShowClusterDetailById\(schemaKey, key\.slice\(sep \+ 1\)\)/.test(ctxItem[0]), ctxItem && ctxItem[0]);

  check("⑩ ShowClusterDetailById 가 focusFam 파라미터 보유",
    /async function _metaGraphShowClusterDetailById\(comboId, focusFam\)/.test(src));
  check("⑩ ShowClusterDetailById → RenderClusterDetail 로 focusFam 전달",
    /_metaGraphRenderClusterDetail\(schemaName, schemaName, tables, childTables, childCols, null, false, comboId, routines, focusFam\)/.test(src));
  check("⑩ RenderClusterDetail 이 focusFam 파라미터 보유",
    /function _metaGraphRenderClusterDetail\(name, fqn, tables, childTables, childCols, totalOverride, truncated, comboId, routines, focusFam\)/.test(src));
  check("⑩ RenderClusterDetail 이 FocusPanelGroup 결과를 반환(상태줄 보강 소스)",
    /return _metaGraphFocusPanelGroup\(focusFam\);/.test(src));

  // 헤딩 li 가 data-group-key 를, 멤버 행이 amgr-ct-row-li 를 계속 방출하는지(매칭·파도 앵커 소실 방지)
  check("⑩ 패널 헤딩이 data-group-key 방출", /class="amgr-ct-group\$\{collapsed \? " is-collapsed" : ""\}" role="button" tabindex="0" aria-expanded="\$\{!collapsed\}" data-group-key="\$\{esc\(sg\.key\)\}"/.test(src));
  check("⑩ 멤버 행이 amgr-ct-row-li(+접힘 시 amgr-ct-collapsed) 방출", /<li class="amgr-ct-row-li\$\{collapsed \? " amgr-ct-collapsed" : ""\}">/.test(src));
  // content-cluster-cohesion(2026-07-30): 패널 sim-group 은 **캔버스 캐시가 1순위**(SSOT).
  //   종전 `"panel:"+표시명` 전용 네임스페이스는 (a) 키가 캔버스와 달라 순서 안정화 맵이 분리되고
  //   (b) 멤버 집합(API 응답 vs 모델 gated)이 달라 **그룹 구성 자체가 갈리는** 부정합의 근인이었다.
  //   폴백(캐시 부재 = 접힌 스키마 등)에서도 comboId 네임스페이스를 우선해 키 정합을 지킨다.
  check("⑩ 패널 sim-group 1순위 = 캔버스 캐시(_simCache[comboId])",
    /_cached = \(_cache && _cache\.has\(comboId\)\) \? _cache\.get\(comboId\) : null;/.test(src)
    && /if \(_sameSet\) \{\s*sgs = _cached;/.test(src));
  // codex P1-3: 캐시는 **멤버 집합 동일**일 때만 — 다르면 패널 전체 멤버로 재계산(행 누락 금지).
  check("⑩ 캐시 사용은 멤버 집합 동일 조건부",
    /_sameSet = inCache\.size === members\.length && members\.every\(\(t\) => inCache\.has\(t\.key\)\)/.test(src));
  check("⑩ 패널 폴백도 comboId 네임스페이스 우선",
    /_metaSimGroups\(comboId \|\| \("panel:" \+ String\(name\)\), members,/.test(src));
}

// ── ⑪ CSS 연출 규칙 존재(JS 가 붙이는 클래스에 스타일이 없으면 무음 실패) ────
{
  check("⑪ .amgr-ct-group.is-focus 규칙 존재", /\.amgr-ct-group\.is-focus\s*\{/.test(cssSrc));
  check("⑪ 헤딩 점멸 keyframes 존재", /@keyframes amgrCtGroupFocus/.test(cssSrc));
  check("⑪ 헤딩이 2회 점멸(중간 감쇠 stop 보유)", /46%\s*\{ background: rgba\(219, 234, 254, \.28\)/.test(cssSrc));
  check("⑪ .amgr-ct-row-li.is-wave 규칙 존재", /\.amgr-ct-row-li\.is-wave\s*\{/.test(cssSrc));
  check("⑪ 파도 keyframes 가 --amgr-wave-a 알파 변수 소비", /@keyframes amgrCtRowWave[\s\S]*?var\(--amgr-wave-a/.test(cssSrc));
  check("⑪ 파도 duration 이 JS 상수(420ms)와 일치", /\.amgr-ct-row-li\.is-wave \{ animation: amgrCtRowWave 420ms/.test(cssSrc) && /_META_WAVE_DUR_MS = 420;/.test(src));
  check("⑪ prefers-reduced-motion 에서 점멸·파도 모두 정지",
    /prefers-reduced-motion: reduce\)[\s\S]*?\.amgr-ct-group\.is-focus \{ animation: none[\s\S]*?\.amgr-ct-row-li\.is-wave \{ animation: none/.test(cssSrc));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
