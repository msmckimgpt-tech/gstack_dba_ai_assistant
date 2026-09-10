// verify_sidebar_reorder_anim.mjs
// sidebar-reorder-anim: 좌측 대화목록의 명칭(대화 제목 · 폴더 이름)을 바꾸면 정렬 키가 함께
//   바뀌어(대화 = last_activity_at(=updated_at) desc / 폴더 = sort_order → name) 항목이 다른
//   자리로 순간이동했다. renderConversationList 는 innerHTML 을 비우고 전량 재구성하므로 CSS
//   transition 이 걸리지 않아, 방금 이름을 바꾼 항목이 사용자 시야에서 사라진 것처럼 보였다.
//   해소 = FLIP(전/후 좌표 비교 후 역이동→트윈) + 시야 유지(스크롤 복원·보정, 접힌 조상 펼침).
//
//   여기서 검증하는 것은 그 **좌표/상태 계산 계약**이다 — DOM·CSS 스텁으로 실제 함수 본문을
//   그대로 실행하며(문자열 존재 검사가 아니라 동작 검사), 실제 화면 정본은 PB-0008
//   Windows-browser Run 이 담당한다(§15.4.1).
//
// 실행: node verify_sidebar_reorder_anim.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const SIDEBAR = readFileSync(join(STATIC, "app/sidebar.js"), "utf8");
const APPJS = readFileSync(join(STATIC, "app.js"), "utf8");
const SHELLCSS = readFileSync(join(STATIC, "css/shell.css"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : ` — ${detail}`}`); }
}

// signature 의 destructuring `{}` 를 body `{` 로 오인하지 않도록 paren-matching 후 brace-matching.
function extractFn(src, name) {
  let start = src.indexOf(`async function ${name}(`);
  if (start < 0) start = src.indexOf(`function ${name}(`);
  if (start < 0) start = src.indexOf(`export function ${name}(`);
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end).replace(/^export\s+/, "");
}

// ── 상수는 소스에서 그대로 실어온다(하드코딩하면 임계값 변경을 하네스가 놓친다) ──
const CONST_BLOCK = (SIDEBAR.match(/const REORDER_ANIM_MIN_MS[\s\S]*?const REORDER_ROW_SELECTOR = [^\n]+\n/) || [""])[0];
ok("[추출] REORDER_* 상수 블록", CONST_BLOCK.includes("REORDER_ROW_SELECTOR"));

const FN_NAMES = [
  "requestSidebarReorderAnimation", "bumpSidebarDataVersion", "_reorderRowKey", "_reorderRowByKey",
  "_beginSidebarReorder", "_expandAncestorsForReorderFocus",
  "_scrollReorderFocusIntoView", "_markReorderArrival", "_reorderDurationFor",
  "_attachReorderAnchor", "_detachReorderAnchor", "_decorateReorderAnchor", "_applyReorderAnchor",
  "_armReorderCleanup", "_playReorderMove", "_commitSidebarReorder",
];
const FN_SRC = {};
FN_NAMES.forEach((n) => {
  FN_SRC[n] = extractFn(SIDEBAR, n);
  ok(`[추출] ${n}`, Boolean(FN_SRC[n]));
});

// 행 선택자가 3개 행 종류(대화 · 폴더 헤더 · 날짜 그룹 헤더)를 모두 덮는다 —
// 하나라도 빠지면 그 종류는 FLIP 대상에서 조용히 제외된다.
[".conv-item", ".conv-folder-header", ".conv-date-group-header"].forEach((sel) => {
  ok(`[계약] REORDER_ROW_SELECTOR 가 ${sel} 포함`, CONST_BLOCK.includes(sel));
});

// ── DOM/window 스텁 — 실제 함수 본문을 그대로 실행할 최소 환경 ────────────────
function makeEnv({ rows = [], scrollTop = 0, viewTop = 0, viewH = 400, reduced = false,
                   scrollHeight = null, state: stateOverride = {}, folders = [] } = {}) {
  const timers = [];
  const rafs = [];
  // 스크롤 컨테이너 스텁 — clamp 경계를 실제 브라우저와 같게 재현한다
  // (콘텐츠 높이 = 마지막 행 bottom, 명시 지정 가능).
  const contentH = scrollHeight != null
    ? scrollHeight
    : rows.reduce((m, r) => Math.max(m, r.docTop + r._h), 0);
  const listEl = {
    scrollTop,
    offsetWidth: 260,
    clientHeight: viewH,
    scrollHeight: contentH,
    innerHTML: "",
    querySelectorAll: () => rows,
    getBoundingClientRect: () => ({ top: viewTop, bottom: viewTop + viewH, height: viewH }),
  };
  rows.forEach((r, i) => {
    r._list = listEl;
    r.previousElementSibling = i > 0 ? rows[i - 1] : null;
  });
  const state = {
    sidebarReorderFocus: null,
    sidebarDataVersion: 0,   // app.js state 슬롯과 동일 초기값
    sidebarReorderAnchor: null,
    collapsedDateGroups: new Set(),
    conversations: [],
    folders,
    ...stateOverride,
  };
  let saveCollapsedCalls = 0;
  const env = {
    state,
    listEl,
    rows,
    timers,
    rafs,
    saveCollapsedCalls: () => saveCollapsedCalls,
    timerDelays: () => timers.map(([, ms]) => ms),
    flushRaf: () => { const q = rafs.splice(0); q.forEach((fn) => fn()); },
    flushTimers: () => { const q = timers.splice(0); q.forEach(([fn]) => fn()); },
  };
  const windowStub = {
    setTimeout: (fn, ms) => { timers.push([fn, ms]); return timers.length; },
    clearTimeout: () => {},
  };
  // 배지는 실제 요소다 — 생성·부착·제거가 도는지 보려면 최소 document 가 필요하다.
  const documentStub = {
    createElement: () => ({
      className: "", textContent: "", _attrs: {},
      setAttribute(k, v) { this._attrs[k] = v; },
      getAttribute(k) { return this._attrs[k]; },
      parentNode: null,
    }),
  };
  const factory = new Function(
    "state", "conversationListEl", "_prefersReducedMotion", "_folderById",
    "_saveCollapsedGroups", "window", "requestAnimationFrame", "document",
    `${CONST_BLOCK}\n${FN_NAMES.map((n) => FN_SRC[n]).join("\n")}\n` +
    `return { ${FN_NAMES.join(", ")} };`
  );
  const api = factory(
    state,
    listEl,
    () => reduced,
    (id) => state.folders.find((f) => Number(f.folder_id) === Number(id)) || null,
    () => { saveCollapsedCalls += 1; },
    windowStub,
    (fn) => { rafs.push(fn); return rafs.length; },
    documentStub,
  );
  return { ...env, api };
}

// docTop = 문서 기준 좌표. 화면 좌표는 스크롤을 뺀 값 → 스크롤 보정 효과가 rect 에 반영된다.
function makeRow(dataset, docTop, h = 30) {
  // 실제 DOM 과 같은 클래스를 부여한다 — `_markReorderArrival` 이 형제를 거슬러 올라가며 도착
  // 묶음 헤더를 찾을 때 클래스로 판별하므로, 없으면 그 경로가 통째로 죽은 채 통과한다.
  const kindClass = dataset.dateKey ? "conv-date-group-header"
    : dataset.folderId ? "conv-folder-header" : "conv-item";
  return {
    dataset,
    kindClass,
    docTop,
    _h: h,
    _list: null,
    style: {},
    offsetWidth: 220,
    _events: [],
    addEventListener(type, fn) { this._events.push([type, fn]); },
    removeEventListener(type, fn) { this._events = this._events.filter(([t, f]) => !(t === type && f === fn)); },
    // 실제 DOM 처럼 event 객체를 넘긴다 — target/propertyName 필터를 우회하지 않기 위함.
    fire(type, ev) {
      const evt = ev === undefined ? { target: this, propertyName: "transform" } : ev;
      this._events.filter(([t]) => t === type).forEach(([, fn]) => fn(evt));
    },
    // 실제 DOM 처럼 다중 클래스 인자를 받는다(단일 인자만 처리하면 두 번째 클래스가 조용히 누락).
    classList: {
      _s: new Set([kindClass]),
      add(...cs) { cs.forEach((c) => this._s.add(c)); },
      remove(...cs) { cs.forEach((c) => this._s.delete(c)); },
      contains(c) { return this._s.has(c); },
    },
    previousElementSibling: null,  // makeEnv 가 rows 순서대로 연결(그룹 헤더 탐색이 실제로 돌게)
    _children: [],
    querySelector(sel) {
      const cls = String(sel).replace(/^\./, "");
      return this._children.find((c) => String(c.className).split(/\s+/).includes(cls)) || null;
    },
    appendChild(node) { node.parentNode = this; this._children.push(node); return node; },
    removeChild(node) { this._children = this._children.filter((c) => c !== node); node.parentNode = null; return node; },
    getBoundingClientRect() {
      const top = this.docTop - (this._list ? this._list.scrollTop : 0);
      return { top, bottom: top + this._h, height: this._h };
    },
  };
}

console.log("\n[1] 행 키 규약 (재구성 전/후를 잇는 유일 식별자)");
{
  const { api } = makeEnv();
  ok("대화 행 → conv:<id>", api._reorderRowKey(makeRow({ conversationId: "c-1" }, 0)) === "conv:c-1");
  ok("폴더 헤더 → folder:<id>", api._reorderRowKey(makeRow({ folderId: "7" }, 0)) === "folder:7");
  ok("날짜 그룹 헤더 → date:<key>", api._reorderRowKey(makeRow({ dateKey: "__today__" }, 0)) === "date:__today__");
  ok("키 없는 행 → 빈 문자열(FLIP 대상 제외)", api._reorderRowKey(makeRow({}, 0)) === "");
  // 대화 행에도 dateKey 가 붙는 경우가 생기면 conv 키가 이겨야 한다(항목 추적이 그룹으로 흡수되지 않게).
  ok("우선순위 conv > folder > date",
    api._reorderRowKey(makeRow({ conversationId: "c-9", folderId: "3", dateKey: "d" }, 0)) === "conv:c-9");
}

console.log("\n[2] 예약(First) 게이트 — 예약이 없으면 측정도 하지 않는다");
{
  const rows = [makeRow({ conversationId: "a" }, 0), makeRow({ conversationId: "b" }, 40)];
  const env = makeEnv({ rows });
  ok("예약 없음 → null (기존 렌더 경로)", env.api._beginSidebarReorder() === null);

  env.api.requestSidebarReorderAnimation("conv:b");
  ok("requestSidebarReorderAnimation 이 state 에 예약 기록",
    env.state.sidebarReorderFocus && env.state.sidebarReorderFocus.key === "conv:b");
  env.api.bumpSidebarDataVersion();  // 목록 데이터 도착 — 이 렌더가 재배치를 담는다
  const snap = env.api._beginSidebarReorder();
  ok("예약 있음 → 스냅샷 반환", Boolean(snap) && snap.key === "conv:b");
  ok("스냅샷에 모든 행의 이전 top 기록", snap.before.get("conv:a") === 0 && snap.before.get("conv:b") === 40);
  ok("예약은 1회 소비 (뒤따르는 무관한 렌더로 새지 않음)", env.state.sidebarReorderFocus === null);
  ok("소비 후 재호출 → null", env.api._beginSidebarReorder() === null);
}
{
  // 응답이 크게 늦어 다른 화면 상태가 된 뒤 도착한 렌더는 애니메이션 대상이 아니다.
  const env = makeEnv({ rows: [makeRow({ conversationId: "a" }, 0)] });
  env.state.sidebarReorderFocus = { key: "conv:a", at: Date.now() - 60000, dataVersion: -1 };
  ok("TTL 초과 예약 → null + 소비", env.api._beginSidebarReorder() === null && env.state.sidebarReorderFocus === null);
}
{
  // §18.8 codex [P1]: PATCH 왕복 중 끼어든 데이터-무관 렌더(그룹 토글 등)가 예약을 삼키면,
  // 정작 재배치가 드러나는 렌더는 전환 없이 순간이동한다. 데이터 버전으로 귀속시킨다.
  const rows = [makeRow({ conversationId: "a" }, 0), makeRow({ conversationId: "b" }, 40)];
  const env = makeEnv({ rows });
  env.api.requestSidebarReorderAnimation("conv:b");
  const v0 = env.state.sidebarDataVersion;
  ok("예약이 현재 데이터 버전을 기록", env.state.sidebarReorderFocus.dataVersion === v0);

  const midRender = env.api._beginSidebarReorder();   // 데이터 갱신 없이 일어난 렌더
  ok("데이터 미갱신 렌더 → 애니메이션 대상 아님", midRender === null);
  ok("데이터 미갱신 렌더는 예약을 소비하지 않는다(핵심)",
    env.state.sidebarReorderFocus !== null && env.state.sidebarReorderFocus.key === "conv:b");

  env.api.bumpSidebarDataVersion();                   // 목록 데이터 도착
  const realRender = env.api._beginSidebarReorder();
  ok("데이터 갱신 렌더 → 애니메이션 대상", Boolean(realRender) && realRender.key === "conv:b");
  ok("이때 비로소 예약 소비", env.state.sidebarReorderFocus === null);
}
{
  const env = makeEnv({ rows: [makeRow({ conversationId: "a" }, 0)], reduced: true });
  env.api.requestSidebarReorderAnimation("conv:a");
  env.api.bumpSidebarDataVersion();
  const snap = env.api._beginSidebarReorder();
  ok("reduced-motion → before 미측정(트윈 생략)", Boolean(snap) && snap.before === null);
  ok("reduced-motion 이어도 스크롤 위치는 기억(시야 유지용)", snap.scrollTop === 0);
}

console.log("\n[3] FLIP(Invert→Play) — 이동한 행만 이전 자리에서 미끄러진다");
{
  // 이름 변경으로 b(문서 40px) 가 맨 위(0px)로, a 는 40px 로 밀린 상황.
  const before = new Map([["conv:a", 0], ["conv:b", 40]]);
  const rows = [makeRow({ conversationId: "b" }, 0), makeRow({ conversationId: "a" }, 40)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "conv:b", scrollTop: 0, before });

  const rb = rows[0], ra = rows[1];
  ok("b: 이전 자리(+40px)에서 출발 (invert)", rb.style.transform === "translateY(40.0px)");
  ok("a: 이전 자리(-40px)에서 출발 (invert)", ra.style.transform === "translateY(-40.0px)");
  ok("invert 단계는 transition 없음", rb.style.transition === "none" && ra.style.transition === "none");
  ok("focus 행 도착 표식 부여", rb.classList.contains("is-reorder-flash") && rb.classList.contains("is-reorder-anchor"));

  env.flushRaf();
  ok("play: transform 해제", rb.style.transform === "" && ra.style.transform === "");
  ok("play: transform transition 부여", /transform \d+ms/.test(rb.style.transition), rb.style.transition);
  // ★ 기대값은 **소스에서 뽑지 않고 여기 고정**한다 (§18.8 codex [P2]) — 소스에서 추출해 다시
  //   소스와 비교하면 값이 무엇으로 바뀌어도 통과하는 토톨로지가 된다. 사용자가 요청한 곡선
  //   (easeInOutBack)과 그것을 담기 위해 정한 재생 시간이 계약이므로, 바뀌면 여기가 red 여야 한다.
  const EXPECT = {
    durationMinMs: 160,                         // 거리 적응형 하한(짧은 이동)
    durationMaxMs: 280,                         // 상한(먼 이동) — 오버슈트 420ms 에서 되돌림
    easing: "cubic-bezier(.22,.61,.36,1)",      // ease-out (감속) — 오버슈트 곡선 금지
    watchdogMs: 680,                            // = durationMax + 400
    flashMs: 900,
    anchorMs: 3500,
    badgeText: "이동됨",
    requestTtlMs: 4000,
  };
  {
    const d = Number((/transform (\d+)ms/.exec(rb.style.transition) || [])[1]);
    ok("[계약] play duration 이 거리 적응형 대역(160~280ms)",
      d >= EXPECT.durationMinMs && d <= EXPECT.durationMaxMs, `${d}ms`);
  }
  ok("[계약] play easing = ease-out (독립 기대값, 네 제어점 정확 일치)",
    rb.style.transition.includes(EXPECT.easing), rb.style.transition);
  // 소스 상수도 같은 값이어야 한다(코드가 리터럴을 인라인해 상수와 갈라지는 것 차단).
  ok("[계약] 소스 REORDER_EASING == 기대 곡선",
    (/const REORDER_EASING = "([^"]+)"/.exec(CONST_BLOCK) || [])[1] === EXPECT.easing);
  ok("[계약] 소스 REORDER_ANIM_MIN_MS == 160",
    Number((/const REORDER_ANIM_MIN_MS = (\d+)/.exec(CONST_BLOCK) || [])[1]) === EXPECT.durationMinMs);
  ok("[계약] 소스 REORDER_ANIM_MAX_MS == 280",
    Number((/const REORDER_ANIM_MAX_MS = (\d+)/.exec(CONST_BLOCK) || [])[1]) === EXPECT.durationMaxMs);
  ok("[계약] 소스 REORDER_FLASH_MS == 900",
    Number((/const REORDER_FLASH_MS = (\d+)/.exec(CONST_BLOCK) || [])[1]) === EXPECT.flashMs);
  ok("[계약] 소스 REORDER_ANCHOR_MS == 3500",
    Number((/const REORDER_ANCHOR_MS = (\d+)/.exec(CONST_BLOCK) || [])[1]) === EXPECT.anchorMs);
  ok("[계약] 소스 REORDER_REQUEST_TTL_MS == 4000",
    Number((/const REORDER_REQUEST_TTL_MS = (\d+)/.exec(CONST_BLOCK) || [])[1]) === EXPECT.requestTtlMs);
  // ★ 기능적 재정렬에 오버슈트 곡선을 다시 넣는 회귀 차단 — 제어점 y 는 [0,1] 안이어야 한다.
  {
    const src = (/const REORDER_EASING = "([^"]+)"/.exec(CONST_BLOCK) || [])[1] || "";
    const m = /^cubic-bezier\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)$/.exec(src);
    ok("[계약] 곡선에 오버슈트 없음(y1 ≥ 0 ∧ y2 ≤ 1)",
      Boolean(m) && parseFloat(m[2]) >= 0 && parseFloat(m[4]) <= 1, src);
  }
  ok("[계약] duration 상한이 기능 UI 대역(≤ 300ms)", EXPECT.durationMaxMs <= 300);
  // 타이머는 "실행됐다" 가 아니라 **언제 발화하도록 걸렸는지**를 본다.
  ok("[계약] 정리 watchdog 지연 = 680ms", env.timerDelays().includes(EXPECT.watchdogMs), JSON.stringify(env.timerDelays()));
  ok("[계약] 도착 펄스 타이머 = 900ms", env.timerDelays().includes(EXPECT.flashMs), JSON.stringify(env.timerDelays()));
  ok("[계약] 도착 앵커 타이머 = 3500ms", env.timerDelays().includes(EXPECT.anchorMs), JSON.stringify(env.timerDelays()));
  globalThis.__REORDER_EXPECT = EXPECT;

  // transitionend 로 인라인 스타일이 정리되어 다음 렌더에 잔류하지 않는다.
  rb.fire("transitionend");
  ok("transitionend → 인라인 스타일 정리", rb.style.transform === "" && rb.style.transition === "");
  // 탭 숨김 등으로 transitionend 가 안 와도 보강 타이머가 정리한다.
  env.flushTimers();
  ok("보강 타이머 → 잔류 스타일 정리", ra.style.transition === "");
}
{
  // §18.8 codex [P2]: transitionend 는 자식에서 버블링한다. 이동 중 포인터가 지나가며 메뉴
  // 트리거의 opacity transition 이 끝나면, 그 이벤트로 FLIP 이 조기 종료돼 행이 최종 위치로 튄다.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map([["conv:a", 60]]) });
  const el = rows[0];
  const child = { nodeName: "SPAN" };
  el.fire("transitionend", { target: child, propertyName: "opacity" });
  ok("자식의 transitionend 는 FLIP 을 끊지 않는다", el.style.transform === "translateY(60.0px)");
  el.fire("transitionend", { target: el, propertyName: "opacity" });
  ok("같은 행이라도 transform 아닌 property 는 무시", el.style.transform === "translateY(60.0px)");
  el.fire("transitionend", { target: el, propertyName: "transform" });
  ok("자기 transform 전환 종료만 인정", el.style.transform === "" && el.style.transition === "");
}
{
  // §18.8 codex [P2]: invert 직후 탭이 백그라운드로 가면 rAF(play)가 오지 않는다.
  // 정리자가 play 안에서만 설치되면 `transition:none` + translateY 가 영구 잔류한다.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map([["conv:a", 50]]) });
  ok("invert 적용됨", rows[0].style.transform === "translateY(50.0px)");
  env.flushTimers();                 // rAF 는 끝내 오지 않고 watchdog 만 발화
  ok("rAF 미도래(탭 백그라운드)여도 잔류 스타일 정리",
    rows[0].style.transform === "" && rows[0].style.transition === "");
}
{
  // 이동하지 않은(또는 노이즈 수준) 행은 건드리지 않는다.
  const rows = [makeRow({ conversationId: "a" }, 0), makeRow({ conversationId: "b" }, 41)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map([["conv:a", 0], ["conv:b", 40]]) });
  ok("delta 0 → transform 미적용", rows[0].style.transform === undefined);
  ok("delta 1px(임계 미만) → transform 미적용", rows[1].style.transform === undefined);
}
{
  // 상한을 넘는 이동은 "화면 밖에서 날아오는" 과장 연출이 되므로 그 행만 트윈을 생략한다.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map([["conv:a", 99999]]) });
  ok("delta 상한 초과 → transform 미적용", rows[0].style.transform === undefined);
}
{
  // 새로 나타난 행(이전 스냅샷에 없음)은 이동이 아니다 — 0 에서 날아오지 않게.
  const rows = [makeRow({ conversationId: "new" }, 0)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map() });
  ok("신규 행 → transform 미적용", rows[0].style.transform === undefined);
}

console.log("\n[3b] 도착 표식 — 모션이 끝난 뒤에도 남는 신호 (디자인 재검토 2026-08-24)");
{
  const E = globalThis.__REORDER_EXPECT;
  const rows = [makeRow({ dateKey: "__today__" }, 0), makeRow({ conversationId: "a" }, 30)];
  const env = makeEnv({ rows });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 0, before: new Map([["conv:a", 90], ["date:__today__", 60]]) });

  const row = rows[1];
  ok("도착 순간 펄스 부여", row.classList.contains("is-reorder-flash"));
  ok("도착 앵커(rail) 부여", row.classList.contains("is-reorder-anchor"));
  // 배지는 **실제로 붙어야** 한다(스타일 존재만 검사하면 부착 코드를 지워도 통과한다).
  {
    const badge = row.querySelector(".conv-reorder-badge");
    ok("'이동됨' 배지가 행에 부착됨", Boolean(badge));
    ok("배지 문구 = 이동됨", badge && badge.textContent === E.badgeText);
    ok("배지에 스크린리더 라벨", badge && String(badge.getAttribute("aria-label") || "").length > 0);
    env.api._attachReorderAnchor(row);
    ok("배지 중복 부착 안 함(매 렌더 부여되므로)",
      row._children.filter((c) => c.className === "conv-reorder-badge").length === 1);
    env.api._detachReorderAnchor(row);
    ok("표식 해제 시 rail·배지 함께 제거",
      !row.querySelector(".conv-reorder-badge") && !row.classList.contains("is-reorder-anchor"));
    env.api._attachReorderAnchor(row);
  }
  ok("앵커가 state 에 기록(재렌더 부여의 근거)",
    env.state.sidebarReorderAnchor && env.state.sidebarReorderAnchor.key === "conv:a");
  ok("앵커 만료 시각이 미래(≈3.5초)", env.state.sidebarReorderAnchor.until - Date.now() > E.anchorMs - 500);
  ok("도착 그룹 헤더 동반 펄스", rows[0].classList.contains("is-reorder-flash"));

  // 펄스와 앵커는 **수명이 다르다** — 이것이 이 설계의 핵심.
  env.timers.find(([, ms]) => ms === E.flashMs)[0]();
  ok("펄스는 짧게 걷힌다", !row.classList.contains("is-reorder-flash"));
  ok("앵커는 그 뒤에도 남는다", row.classList.contains("is-reorder-anchor"));
}
{
  // ★ 지속성의 실체: 행 요소는 매 렌더 교체되므로 **행을 만들 때** 부여해야 살아남는다.
  //   (렌더 후 되붙이는 후처리는 렌더 횟수·순서에 취약 — 라이브에서 두 번째 렌더에 사라졌다.)
  const fresh = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows: fresh, state: { sidebarReorderAnchor: { key: "conv:a", until: Date.now() + 3000 } } });
  ok("갓 만든 행엔 표식이 없다(전제)", !fresh[0].classList.contains("is-reorder-anchor"));
  env.api._decorateReorderAnchor(fresh[0]);
  ok("행 생성 시 부여 → 앵커 지속", fresh[0].classList.contains("is-reorder-anchor"));
  ok("행 생성 시 배지도 함께", Boolean(fresh[0].querySelector(".conv-reorder-badge")));

  const other = makeRow({ conversationId: "zzz" }, 0);
  env.api._decorateReorderAnchor(other);
  ok("다른 행에는 부여하지 않는다", !other.classList.contains("is-reorder-anchor"));
}
{
  // ★ 연속 이동: 오래된 만료 타이머가 **최신 표식을 지우면 안 된다**(세대 검사).
  //   라이브에서 폴더를 잇달아 만들고 이름을 바꿨을 때 표식이 수명보다 일찍 사라진 결함.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows });
  env.api._markReorderArrival(rows[0], "conv:a");        // 1세대
  const firstTimer = env.timers.find(([, ms]) => ms === globalThis.__REORDER_EXPECT.anchorMs);
  env.api._markReorderArrival(rows[0], "conv:a");        // 2세대(같은 키)
  const secondToken = env.state.sidebarReorderAnchor;
  firstTimer[0]();                                        // 1세대 타이머 발화
  ok("오래된 타이머가 최신 앵커 상태를 지우지 않는다", env.state.sidebarReorderAnchor === secondToken);
  ok("오래된 타이머가 최신 표식을 걷어내지 않는다", rows[0].classList.contains("is-reorder-anchor"));
  ok("최신 표식의 배지도 유지", Boolean(rows[0].querySelector(".conv-reorder-badge")));
  // 자기 세대 타이머는 정상적으로 거둔다.
  const ownTimer = env.timers.filter(([, ms]) => ms === globalThis.__REORDER_EXPECT.anchorMs).pop();
  ownTimer[0]();
  ok("자기 세대 타이머는 표식을 거둔다",
    !rows[0].classList.contains("is-reorder-anchor") && env.state.sidebarReorderAnchor === null);
}
{
  // 만료된 앵커는 부여하지 않는다(표식이 영원히 남는 것 방지).
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows, state: { sidebarReorderAnchor: { key: "conv:a", until: Date.now() - 1 } } });
  env.api._decorateReorderAnchor(rows[0]);
  ok("만료 앵커는 부여 안 함", !rows[0].classList.contains("is-reorder-anchor"));
  env.api._applyReorderAnchor();
  ok("만료 앵커는 상태에서 제거", env.state.sidebarReorderAnchor === null);
}
{
  // reduced-motion: 트윈은 없어도 **표식은 유지**한다 — 모션을 줄일수록 정적 신호가 중요하다.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows, reduced: true });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 0, before: null });
  ok("reduced: transform 미적용", rows[0].style.transform === undefined);
  ok("reduced: 도착 표식(rail) 유지", rows[0].classList.contains("is-reorder-anchor"));
  ok("reduced: 배지 유지", Boolean(rows[0].querySelector(".conv-reorder-badge")));
  ok("reduced: 앵커 state 기록", Boolean(env.state.sidebarReorderAnchor));
}
{
  // 트윈 중 포인터 차단은 유지(이동 중 오클릭 방지).
  const pr = [makeRow({ conversationId: "p" }, 0)];
  const envP = makeEnv({ rows: pr });
  envP.api._commitSidebarReorder({ key: "", scrollTop: 0, before: new Map([["conv:p", 60]]) });
  ok("트윈 중 pointer-events 차단", pr[0].style.pointerEvents === "none");
  pr[0].fire("transitionend");
  ok("정착 후 pointer-events 복원", pr[0].style.pointerEvents === "");
}

console.log("\n[4] 시야 유지 — 스크롤 복원 + 대상 추종");
{
  // 재구성으로 스크롤이 0 으로 clamp 된 상태에서 복원되어야 한다.
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows, scrollTop: 0 });
  env.api._commitSidebarReorder({ key: "", scrollTop: 150, before: new Map() });
  ok("렌더로 리셋된 scrollTop 복원", env.listEl.scrollTop === 150);
}
{
  // focus 행이 뷰 아래로 밀려났으면(문서 900px, 뷰 0~400) 시야 안으로 끌어온다.
  const rows = [makeRow({ conversationId: "a" }, 900)];
  const env = makeEnv({ rows, scrollTop: 0, viewH: 400 });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 0, before: new Map([["conv:a", 900]]) });
  const r = rows[0].getBoundingClientRect();
  ok("뷰 아래 대상 → 스크롤 보정으로 시야 진입", r.top >= 0 && r.bottom <= 400, `top=${r.top} bottom=${r.bottom}`);
  ok("보정분이 FLIP delta 에 흡수(별도 점프 없음)", rows[0].style.transform !== undefined && rows[0].style.transform !== "");
}
{
  // 뷰 위로 올라간 경우도 동일(스크롤 가능한 긴 목록).
  const rows = [makeRow({ conversationId: "a" }, 0)];
  const env = makeEnv({ rows, scrollTop: 300, viewH: 400, scrollHeight: 1200 });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 300, before: new Map([["conv:a", 0]]) });
  const r = rows[0].getBoundingClientRect();
  ok("뷰 위 대상 → 스크롤 보정으로 시야 진입", r.top >= 0 && r.bottom <= 400, `top=${r.top}`);
}
{
  // 이미 시야 안이면 스크롤을 건드리지 않는다(사용자 위치 보존).
  const rows = [makeRow({ conversationId: "a" }, 200)];
  const env = makeEnv({ rows, scrollTop: 100, viewH: 400 });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 100, before: new Map([["conv:a", 200]]) });
  ok("시야 안 대상 → 스크롤 불변", env.listEl.scrollTop === 100);
}
{
  // reduced-motion: 트윈·강조는 없어도 시야 유지는 수행한다(접근성 신호는 '모션 줄이기').
  const rows = [makeRow({ conversationId: "a" }, 900)];
  const env = makeEnv({ rows, scrollTop: 0, viewH: 400, reduced: true });
  env.api._commitSidebarReorder({ key: "conv:a", scrollTop: 0, before: null });
  const r = rows[0].getBoundingClientRect();
  ok("reduced: 시야 유지 수행", r.top >= 0 && r.bottom <= 400);
  ok("reduced: transform 미적용", rows[0].style.transform === undefined);
  ok("reduced: 펄스 애니메이션은 CSS 에서 정지(표식 자체는 [3b] 에서 확인)", true);
}

console.log("\n[5] 접힌 조상 펼침 — 대상이 DOM 에 없으면 전환도 불가");
{
  // 미분류 대화가 '지난 해 > 월' 로 옮겨간 경우: leaf + 조상 branch 를 모두 펼친다.
  const env = makeEnv({
    state: {
      collapsedDateGroups: new Set(["year:2025", "month:2025-11", "__today__"]),
      conversations: [{ id: "c-1", folder_id: null }],
    },
  });
  const dateTree = {
    nodes: [{
      kind: "branch", key: "year:2025", children: [
        { kind: "leaf", key: "month:2025-11", items: [{ id: "c-1" }] },
      ],
    }],
  };
  env.api._expandAncestorsForReorderFocus("conv:c-1", dateTree);
  ok("leaf(월) 접힘 해제", !env.state.collapsedDateGroups.has("month:2025-11"));
  ok("조상 branch(연) 접힘 해제", !env.state.collapsedDateGroups.has("year:2025"));
  ok("무관한 그룹은 그대로", env.state.collapsedDateGroups.has("__today__"));
  // §18.8 codex [P2]: 이 펼침은 "지금 이 항목을 보이게" 하는 세션 조치이지 사용자의 접힘
  // 선호가 아니다. 영속하면, 의도적으로 접어둔 그룹이 이름 한 번 바꿨다고 이후 접속에서도 펼쳐진다.
  ok("자동 펼침은 영속하지 않는다(사용자 선호 보존)", env.saveCollapsedCalls() === 0);
}
{
  // 폴더 배정 대화: 자기 폴더 + 조상 체인을 펼쳐야 대화 행이 그려진다.
  const env = makeEnv({
    state: {
      collapsedDateGroups: new Set(["folder:5", "folder:2"]),
      conversations: [{ id: "c-2", folder_id: 5 }],
      folders: [{ folder_id: 5, parent_folder_id: 2 }, { folder_id: 2, parent_folder_id: null }],
    },
  });
  env.api._expandAncestorsForReorderFocus("conv:c-2", { nodes: [] });
  ok("자기 폴더 접힘 해제", !env.state.collapsedDateGroups.has("folder:5"));
  ok("조상 폴더 접힘 해제", !env.state.collapsedDateGroups.has("folder:2"));
}
{
  // 폴더 헤더 자신이 대상일 때: 부모만 펼치고 자기 접힘은 존중(헤더는 접혀도 보인다).
  const env = makeEnv({
    state: {
      collapsedDateGroups: new Set(["folder:5", "folder:2"]),
      folders: [{ folder_id: 5, parent_folder_id: 2 }, { folder_id: 2, parent_folder_id: null }],
    },
  });
  env.api._expandAncestorsForReorderFocus("folder:5", { nodes: [] });
  ok("부모 폴더 접힘 해제", !env.state.collapsedDateGroups.has("folder:2"));
  ok("자기 접힘은 유지(사용자 선호 보존)", env.state.collapsedDateGroups.has("folder:5"));
}
{
  // 어느 경로에서도 localStorage 를 건드리지 않는다(영속은 사용자 토글 전용).
  const env = makeEnv({
    state: {
      collapsedDateGroups: new Set(["__today__", "folder:9"]),
      conversations: [{ id: "c-3", folder_id: 9 }],
      folders: [{ folder_id: 9, parent_folder_id: null }],
    },
  });
  env.api._expandAncestorsForReorderFocus("conv:c-3", { nodes: [{ kind: "leaf", key: "__today__", items: [{ id: "c-3" }] }] });
  ok("해제가 일어나도 영속 저장 안 함", env.saveCollapsedCalls() === 0);
  ok("세션 상태에서는 실제로 펼쳐짐(날짜)", !env.state.collapsedDateGroups.has("__today__"));
  ok("세션 상태에서는 실제로 펼쳐짐(폴더)", !env.state.collapsedDateGroups.has("folder:9"));
  env.api._expandAncestorsForReorderFocus("", { nodes: [] });
  ok("키 없음 → no-op", env.saveCollapsedCalls() === 0);
}
{
  // 폴더 체인에 순환(데이터 이상)이 있어도 무한 루프에 빠지지 않는다.
  const env = makeEnv({
    state: {
      collapsedDateGroups: new Set(["folder:1", "folder:2"]),
      folders: [{ folder_id: 1, parent_folder_id: 2 }, { folder_id: 2, parent_folder_id: 1 }],
      conversations: [{ id: "c-4", folder_id: 1 }],
    },
  });
  env.api._expandAncestorsForReorderFocus("conv:c-4", { nodes: [] });
  ok("순환 폴더 체인 종료(무한 루프 없음)", !env.state.collapsedDateGroups.has("folder:1"));
}

console.log("\n[6] 호출 배선 — 두 명칭 변경 경로가 실제로 예약한다");
{
  const commitRename = extractFn(SIDEBAR, "_commitFolderRename") || "";
  ok("폴더 이름 변경이 재배치 예약", /requestSidebarReorderAnimation\(`folder:\$\{folderId\}`\)/.test(commitRename));
  // 실패 경로(자리 변화 없음)에서는 예약하지 않는다 — PATCH 성공 뒤에만 있어야 한다.
  //   sidebar-inline-rename 이후 커밋은 "PATCH try/catch → (실패면 return) → 예약 → 재조회"
  //   구조다(저장 성공 뒤의 재조회 실패를 '변경 실패' 로 보고하지 않기 위한 분리). 따라서
  //   "첫 catch 이전" 이 아니라 **실패 return 이후에 예약이 있고, 그 return 이 예약보다 앞선다**
  //   를 본다(실패 경로에서는 예약에 도달할 수 없다).
  const failReturnIdx = commitRename.search(/showToast\([^)]*이름 변경에 실패[\s\S]*?return;/);
  const reserveIdx = commitRename.indexOf("requestSidebarReorderAnimation");
  ok("예약은 PATCH 실패 경로에서 도달 불가", failReturnIdx >= 0 && reserveIdx > failReturnIdx,
    `failReturn=${failReturnIdx} reserve=${reserveIdx}`);
  // ★ 순서 계약 (라이브 실측으로 잡은 회귀): 예약이 기록하는 데이터 버전이 "이 예약이 기다리는
  //   갱신" 의 기준이다. 데이터 재적재(loadFolders) **뒤에** 예약하면 자기 갱신을 이미 지나쳐
  //   어떤 렌더에서도 소비되지 않는다 — 애니메이션이 조용히 사라진다.
  ok("폴더: 예약이 loadFolders() 보다 먼저",
    commitRename.indexOf("requestSidebarReorderAnimation") < commitRename.indexOf("await loadFolders()"),
    `req@${commitRename.indexOf("requestSidebarReorderAnimation")} load@${commitRename.indexOf("await loadFolders()")}`);

  // ★ 드래그&드롭 이동 — **문자열이 아니라 실행**으로 잠근다 (§18.8 codex [P2]).
  //   인덱스 비교만 하면 예약을 PATCH 앞으로 옮겨도 통과하고, 실패 경로도 못 본다.
  {
    const moveConvSrc = extractFn(SIDEBAR, "moveConversationToFolder");
    const moveFolderSrc = extractFn(SIDEBAR, "moveFolderTo");
    const sameRefSrc = extractFn(SIDEBAR, "_sameFolderRef");
    const reqSrc = extractFn(SIDEBAR, "requestSidebarReorderAnimation");
    const bumpSrc = extractFn(SIDEBAR, "bumpSidebarDataVersion");
    ok("[DnD] 이동 함수 추출", Boolean(moveConvSrc) && Boolean(moveFolderSrc) && Boolean(sameRefSrc));

    // 실 함수를 구동한다 — apiFetch/loadConversations/loadFolders 는 호출 **순서를 기록**하는 스텁.
    const buildMove = ({ patchRejects = false } = {}) => {
      const calls = [];
      const st = { conversations: [{ id: "c1", folder_id: null }], folders: [{ folder_id: 7, parent_folder_id: null }],
                   sidebarReorderFocus: null, sidebarDataVersion: 0 };
      const factory = new Function(
        "state", "apiFetch", "showToast", "loadConversations", "loadHistory", "loadFolders",
        "renderConversationList", "calls",
        `${sameRefSrc}\n${reqSrc}\n${bumpSrc}\n` +
        `function _folderById(id) { return state.folders.find((f) => Number(f.folder_id) === Number(id)) || null; }\n` +
        `${moveConvSrc}\n${moveFolderSrc}\n` +
        `return { moveConversationToFolder, moveFolderTo };`
      );
      const api = factory(
        st,
        async (...a) => { calls.push(`patch:${a[0]}`); if (patchRejects) throw new Error("boom"); return {}; },
        (m) => calls.push(`toast:${String(m).slice(0, 10)}`),
        async () => { calls.push("loadConversations"); st.sidebarDataVersion += 1; calls.push("render"); },
        async () => { calls.push("loadHistory"); },
        async () => { calls.push("loadFolders"); st.sidebarDataVersion += 1; },
        () => calls.push("render"),
        calls,
      );
      // 예약 호출을 순서 기록에 남기려면 wrapper 로 감싼다(원 함수는 위 클로저 안에서 그대로 쓰인다).
      return { api, st, calls };
    };

    // (1) 대화 이동: 예약이 서고, 그것을 소비할 렌더가 **데이터 버전이 오른 뒤** 온다.
    {
      const { api, st, calls } = buildMove();
      await api.moveConversationToFolder("c1", 7);
      ok("[DnD] 대화 이동이 재배치를 예약", st.sidebarReorderFocus !== null || calls.includes("render"));
      const iPatch = calls.findIndex((c) => c.startsWith("patch:"));
      const iLoad = calls.indexOf("loadConversations");
      ok("[DnD] 대화 이동: PATCH → 서버 반영 순서", iPatch >= 0 && iLoad > iPatch, calls.join(" > "));
      // ★ 트윈을 끊던 "즉시 렌더" 가 없어야 한다 — 서버 반영 전 렌더가 있으면 그 렌더가 트윈을
      //   시작하고 곧바로 두 번째 렌더가 DOM 을 갈아엎는다.
      const rendersBeforeLoad = calls.slice(0, iLoad).filter((c) => c === "render").length;
      ok("[DnD] 대화 이동: 서버 반영 전 선-렌더 없음(트윈 절단 방지)", rendersBeforeLoad === 0, calls.join(" > "));
    }
    // (2) PATCH 실패 시 예약이 남지 않는다(무관한 렌더를 강조하지 않게).
    {
      const { api, st } = buildMove({ patchRejects: true });
      await api.moveConversationToFolder("c1", 7);
      ok("[DnD] 대화 이동 실패 → 예약 없음", st.sidebarReorderFocus === null);
    }
    {
      const { api, st } = buildMove({ patchRejects: true });
      await api.moveFolderTo(7, 3);
      ok("[DnD] 폴더 이동 실패 → 예약 없음", st.sidebarReorderFocus === null);
    }
    // (3) 폴더 이동: 예약이 loadFolders(=데이터 버전 상승) **앞**에 선다.
    {
      const { api, st, calls } = buildMove();
      await api.moveFolderTo(7, 3);
      ok("[DnD] 폴더 이동이 재배치를 예약", st.sidebarReorderFocus !== null);
      ok("[DnD] 폴더 이동: 예약 시점의 데이터 버전이 loadFolders 이전 값",
        st.sidebarReorderFocus && st.sidebarReorderFocus.dataVersion === 0 && st.sidebarDataVersion === 1,
        `focus=${JSON.stringify(st.sidebarReorderFocus)} ver=${st.sidebarDataVersion}`);
      ok("[DnD] 폴더 이동: PATCH → loadFolders → render", calls.join(" > ").includes("loadFolders > render"), calls.join(" > "));
    }
    // (4) 제자리 드롭은 이동이 아니다 — 서버 왕복도 예약도 없다.
    {
      const { api, st, calls } = buildMove();
      await api.moveConversationToFolder("c1", null);   // 이미 folder_id === null
      ok("[DnD] 대화 제자리 드롭 → PATCH 없음", !calls.some((c) => c.startsWith("patch:")), calls.join(" > "));
      ok("[DnD] 대화 제자리 드롭 → 예약 없음(거짓 '이동됨' 표식 차단)", st.sidebarReorderFocus === null);
    }
    {
      const { api, st, calls } = buildMove();
      await api.moveFolderTo(7, null);                  // 이미 parent_folder_id === null
      ok("[DnD] 폴더 제자리 드롭 → PATCH 없음", !calls.some((c) => c.startsWith("patch:")), calls.join(" > "));
      ok("[DnD] 폴더 제자리 드롭 → 예약 없음", st.sidebarReorderFocus === null);
    }
  }
  // 주기 unread 동기화가 대기 중 예약을 가로채거나 드래그를 깨지 않는다 (§18.8 codex [P1]).
  {
    const syncSrc = extractFn(SIDEBAR, "_maybeSyncConversationListUnread") || "";
    const guardHead = syncSrc.slice(0, syncSrc.indexOf("_lastSidebarUnreadSyncAt = now"));
    ok("[DnD] 주기 동기화: 드래그 중이면 skip", /if \(state\.dqaDrag\) return;/.test(guardHead));
    ok("[DnD] 주기 동기화: 대기 중 재배치 예약이 있으면 skip", /if \(state\.sidebarReorderFocus\) return;/.test(guardHead));
  }

  const settings = extractFn(APPJS, "openConversationSettings") || "";
  ok("대화 제목 변경이 재배치 예약", /requestSidebarReorderAnimation\(`conv:\$\{conversation\.id\}`\)/.test(settings));
  ok("대화: 예약이 refreshWorkspace() 보다 먼저",
    settings.indexOf("requestSidebarReorderAnimation") < settings.indexOf("refreshWorkspace(conversation.id)"));
  ok("app.js 가 sidebar 의 예약 API 를 import", /import \{[^}]*requestSidebarReorderAnimation[^}]*\} from "\.\/app\/sidebar\.js/s.test(APPJS));
  ok("state 에 sidebarReorderFocus 슬롯 존재", /sidebarReorderFocus: null/.test(APPJS));
  ok("state 에 sidebarDataVersion 슬롯 존재", /sidebarDataVersion: 0/.test(APPJS));
  // [P1] 봉인: 데이터가 갱신되는 **모든** 목록 적재 경로가 버전을 올려야 예약이 그 렌더로 간다.
  const loadConvSrc = extractFn(APPJS, "loadConversations") || "";
  ok("loadConversations 가 데이터 버전을 올린다", /state\.conversations = [^\n]*\n(?:[^\n]*\n){0,4}?\s*bumpSidebarDataVersion\(\);/.test(loadConvSrc)
    || (loadConvSrc.includes("state.conversations =") && loadConvSrc.includes("bumpSidebarDataVersion()")));
  const loadFoldersSrc = extractFn(SIDEBAR, "loadFolders") || "";
  ok("loadFolders 가 데이터 버전을 올린다", loadFoldersSrc.includes("bumpSidebarDataVersion()"));
  const unreadSyncSrc = extractFn(SIDEBAR, "_maybeSyncConversationListUnread") || "";
  ok("주기 unread 동기화도 데이터 버전을 올린다", unreadSyncSrc.includes("bumpSidebarDataVersion()"));
  ok("모션 게이트 단일 정의 공유(_prefersReducedMotion export)", /export function _prefersReducedMotion\(\)/.test(APPJS));
  // folder-newconv(2026-09-10): 종전 정규식은 `_prefersReducedMotion,` 이 import 블록의 **마지막
  //   줄**일 것을 요구해, app.js 에서 심볼을 하나 더 가져오기만 해도(기능 무관) 깨졌다. 이 게이트가
  //   지키려는 계약은 «모션 게이트를 자체 정의하지 않고 app.js 정본에서 가져온다» 이므로, 줄 배치가
  //   아니라 그 사실을 본다.
  ok("sidebar 가 모션 게이트를 import",
    /import\s*\{[^}]*\b_prefersReducedMotion\b[^}]*\}\s*from\s*"\.\.\/app\.js/.test(SIDEBAR));

  // 렌더 wrapper 가 실제로 FLIP 을 감싸는지(예약 소비 → 렌더 → commit 순서).
  const wrapper = extractFn(SIDEBAR, "renderConversationList") || "";
  ok("renderConversationList 가 _beginSidebarReorder 로 시작", wrapper.includes("_beginSidebarReorder()"));
  ok("renderConversationList 가 렌더 후 _commitSidebarReorder 호출", wrapper.includes("_commitSidebarReorder(snap)"));
  ok("렌더 본체에 focus 키 전달(접힌 조상 펼침용)", wrapper.includes("_renderConversationListDom(snap ? snap.key : \"\")"));
  // ★ 앵커의 값어치는 "재렌더를 견딘다" 는 데 있다 — 행을 만드는 경로에서 부여해야 한다.
  //   (검사하지 않아 후처리 방식의 결함이 하네스를 통과했던 구멍을 메운다.)
  const buildItem = SIDEBAR.slice(SIDEBAR.indexOf("const buildCompactItem"), SIDEBAR.indexOf("// --- 내 대화"));
  ok("[배선] 대화 행 생성 시 앵커 부여", buildItem.includes("_decorateReorderAnchor(button)"));
  const folderNode = SIDEBAR.slice(SIDEBAR.indexOf("const renderFolderNode"), SIDEBAR.indexOf("_folderChildren(null).forEach"));
  ok("[배선] 폴더 헤더 생성 시 앵커 부여(일반·이름변경 두 경로)",
    (folderNode.match(/_decorateReorderAnchor\(header\)/g) || []).length === 2);
  ok("렌더 본체가 조상 펼침을 seed 이후에 적용",
    SIDEBAR.indexOf("_seedAggregateGroupsCollapsedOnce(dateTree.keys)") <
    SIDEBAR.indexOf("_expandAncestorsForReorderFocus(reorderFocusKey, dateTree)"));
}

console.log("\n[7] 강조 스타일 + 접근성");
{
  ok("shell.css 에 도착 펄스 정의", /@keyframes convReorderFlash/.test(SHELLCSS));
  ok("대화 행·폴더 헤더·날짜 그룹 헤더 모두 펄스 대상",
    /\.conv-item\.is-reorder-flash/.test(SHELLCSS) && /\.conv-folder-header\.is-reorder-flash/.test(SHELLCSS)
    && /\.conv-date-group-header\.is-reorder-flash/.test(SHELLCSS));
  ok("앵커 rail 스타일(형태 신호 — hover 배경과 의미 충돌 회피)",
    /\.is-reorder-anchor[\s\S]{0,240}box-shadow: inset 3px 0 0/.test(SHELLCSS));
  ok("'이동됨' 배지 스타일 존재(언어 신호)", /\.conv-reorder-badge\s*\{/.test(SHELLCSS));
  ok("배지가 레이아웃을 흔들지 않는다(absolute)",
    /\.conv-reorder-badge[\s\S]{0,200}position: absolute/.test(SHELLCSS));
  ok("폴더 헤더에 배지 기준(relative)", /\.conv-folder-header \{ position: relative; \}/.test(SHELLCSS));
  const reduceBlocks = SHELLCSS.match(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\n\}/g) || [];
  const rb2 = reduceBlocks.find((b) => b.includes("is-reorder-flash"));
  ok("CSS 차원에서도 reduced-motion 시 펄스 정지", Boolean(rb2) && rb2.includes("animation: none"));
  ok("reduced-motion 에서도 rail 은 유지(정지 표식)",
    Boolean(rb2) && !/is-reorder-anchor[^}]*(display:\s*none|box-shadow:\s*none)/.test(rb2));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
