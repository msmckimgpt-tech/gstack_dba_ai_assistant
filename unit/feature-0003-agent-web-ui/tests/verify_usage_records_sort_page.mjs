// verify_usage_records_sort_page.mjs
// REQ-20260814-usage-records-sort-page — 관리 콘솔 > AI 운영 현황 > LLM 사용량 > **사용 기록**
// 표의 열 정렬 + 페이지네이션.
//
// 사용자 요청(2026-08-14): "[관리 콘솔 > AI 운영 현황 > LLM 사용량 > 사용 기록 표]를 출력할 때,
// 집계된 결과셋의 column 에 따라 정렬할 수 있도록 구성해주세요. 페이지네이션 또한 구성해주세요."
//
// 종전 동작: `showUsageConvModal` 이 대화·시스템 행을 합친 뒤 **토큰 내림차순으로 고정** 정렬해
// 전 행(최대 400)을 한 번에 렌더했다 — 다른 축으로 볼 방법도, 나눠 볼 방법도 없었다.
//
// 검증 축:
//   (A) 기본 상태 보존 — 첫 화면은 종전과 같은 토큰 내림차순, 페이지 1, 50행.
//   (B) 정렬 — 수치/일시 열은 첫 클릭 내림차순, 텍스트 열은 오름차순. 재클릭은 방향 토글.
//       aria-sort 가 실제 상태를 따라간다(스크린리더에 거짓말하지 않는다).
//   (C) 표시-정렬 정합 — '주체' 열은 raw sentinel(`__insight_worker__`)이 아니라 **화면에 보이는
//       라벨**("인사이트 워커") 기준으로 정렬된다. 이 축이 깨지면 사용자는 자기가 본 것과 다른
//       순서를 받는다.
//   (D) 페이지네이션 — 슬라이스 정확성, 경계 버튼 disabled, 페이지당 행 수 변경(전체 포함),
//       정렬 변경 시 1페이지 복귀.
//   (E) nav 정체성(핵심 회귀 축) — 시스템 행의 이동 대상은 정렬·페이지가 바뀌어도 **그 행의 것**
//       이어야 한다. 종전 구현의 `navByIdx.push` 는 재렌더마다 누적돼 페이지네이션과 함께 쓰면
//       엉뚱한 화면으로 이동한다.
//   (F) 이스케이프 — 제목·대상의 마크업이 실행되지 않는다.
//
// 실행: node verify_usage_records_sort_page.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   레이아웃·대비·실제 클릭감은 PB-0008 실 Windows 브라우저(§15.4.1)가 본다 — jsdom 은 픽셀을
//   보지 못하므로 두 층이 서로를 대체하지 않는다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const usageJs = read("admin", "usage.js");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : `  — ${detail}`}`); }
}

// 정본 모듈을 jsdom 위에서 그대로 실행한다(로직 재구현 0 — 다른 verify_*.mjs 와 동일 방식).
const MODULE_BODY = usageJs
  .replace(/^import\s[\s\S]*?from\s+"[^"]*";/gm, "")
  .replace(/^export\s+\{[^}]*\};\s*$/gm, "");
if (/^import\s/m.test(MODULE_BODY) || /^export\s/m.test(MODULE_BODY)) {
  console.error("import/export 잔존 — 스텁 치환 실패");
  process.exit(2);
}

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
const navCalls = [];
const _stubs = {
  document: window.document,
  window,
  adminState: { datasources: [], metadata: {} },
  apiFetch: async () => ({}),
  _metaPopulateScopeSelect: () => {},
  activateAiConsoleSubtab: () => {},
  switchTab: (s) => { navCalls.push(s); },
  bindBackdropDismiss: () => {},
  matchesAnyVariant: () => true,
  searchVariants: (s) => [s],
  requestAnimationFrame: (fn) => fn(),
  // applyUsageNav 이 `new Event("input")` 을 쓴다 — 브라우저 전역이라 jsdom 것을 넘긴다.
  Event: window.Event,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
};
const EXPORTS = ["showUsageConvModal", "applyUsageNav", "_usageActorLabel"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`로드됨 ${n}`, typeof M[n] === "function");

// ── 표본 데이터 ────────────────────────────────────────────────────────────────
// 대화 60 + 시스템 60 = 120행 (기본 페이지 50 → 3페이지). 값은 결정적으로 만든다.
const CONV = Array.from({ length: 60 }, (_, i) => ({
  conversation_id: `c${i}`,
  topic: `대화 ${String(i).padStart(2, "0")}`,
  owner_username: `user${String(i % 7)}`,
  owner_role: "Admin",
  calls: 100 + i,
  total_tokens: 1000 + i * 10,
  cost_usd: (i % 5) * 1.5,
  last_used_at: `2026-08-${String((i % 28) + 1).padStart(2, "0")}T03:00:00Z`,
}));
const SYS = Array.from({ length: 60 }, (_, i) => ({
  actor: i % 2 === 0 ? "__insight_worker__" : "__ask_worker__",
  task: "node_analysis",
  task_label: `분석문 사실성 검증 ${String(i).padStart(2, "0")}`,
  target: `db.table_${i}`,
  calls: 50 + i,
  total_tokens: 2000 + i * 7,
  cost_usd: (i % 3) * 2.25,
  last_used_at: `2026-07-${String((i % 28) + 1).padStart(2, "0")}T09:30:00Z`,
  nav: { screen: "metadata", subtab: "objects", search: `table_${i}`, path_label: `메타데이터 ${i}` },
}));
const DATA = { items: CONV, system_items: SYS, truncated: false, system_truncated: false };

const openModal = () => {
  M.showUsageConvModal({ data: DATA, title: "테스트", scope: "admin" });
  return window.document.getElementById("usageConvModalOverlay");
};
const $ = (root, sel) => root.querySelector(sel);
const $$ = (root, sel) => Array.from(root.querySelectorAll(sel));
const bodyRows = (ov) => $$(ov, ".usage-rec-body tr");
const cellText = (tr, i) => (tr.children[i] ? tr.children[i].textContent.trim() : "");
const click = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const headBtn = (ov, key) => $(ov, `[data-usage-sort="${key}"]`);
// 열 인덱스(admin scope): 0 구분 · 1 대화/작업 · 2 주체 · 3 호출 · 4 토큰 · 5 비용 · 6 최근 사용
const COL = { kind: 0, what: 1, who: 2, calls: 3, tokens: 4, cost: 5, when: 6 };
const numOf = (s) => Number(String(s).replace(/[^0-9.]/g, "")) || 0;

// ── (A) 기본 상태 — 종전 첫 화면 보존 ─────────────────────────────────────────
console.log("\n[A] 기본 상태");
{
  const ov = openModal();
  ok("A1 모달이 열린다", !!ov);
  const rows = bodyRows(ov);
  ok("A2 첫 페이지는 50행", rows.length === 50, `rows=${rows.length}`);
  const tokens = rows.map((tr) => numOf(cellText(tr, COL.tokens)));
  ok("A3 기본 정렬 = 토큰 내림차순(종전 동작 보존)",
    tokens.every((v, i) => i === 0 || tokens[i - 1] >= v), `head=${tokens.slice(0, 3)}`);
  const all = CONV.concat(SYS).map((r) => r.total_tokens).sort((a, b) => b - a);
  ok("A4 1행은 전체 최대 토큰", tokens[0] === all[0], `${tokens[0]} vs ${all[0]}`);
  const info = $(ov, ".usage-rec-pager-info");
  ok("A5 페이저가 총건수·표시구간을 밝힌다",
    !!info && /120/.test(info.textContent) && /1/.test(info.textContent) && /50/.test(info.textContent),
    info && info.textContent);
  const th = $$(ov, ".usage-rec-head th");
  ok("A6 열 머리 7개가 모두 정렬 버튼", th.length === 7 && th.every((h) => !!$(h, "[data-usage-sort]")),
    `th=${th.length}`);
  ok("A7 활성 열의 aria-sort=descending",
    th[COL.tokens].getAttribute("aria-sort") === "descending", th[COL.tokens].getAttribute("aria-sort"));
  ok("A8 비활성 열의 aria-sort=none", th[COL.calls].getAttribute("aria-sort") === "none");
}

// ── (B) 정렬 ─────────────────────────────────────────────────────────────────
console.log("\n[B] 정렬");
{
  const ov = openModal();
  click(headBtn(ov, "calls"));
  let vals = bodyRows(ov).map((tr) => numOf(cellText(tr, COL.calls)));
  ok("B1 수치 열 첫 클릭 = 내림차순",
    vals.every((v, i) => i === 0 || vals[i - 1] >= v), `head=${vals.slice(0, 3)}`);
  ok("B2 aria-sort 가 따라간다",
    $$(ov, ".usage-rec-head th")[COL.calls].getAttribute("aria-sort") === "descending");

  click(headBtn(ov, "calls"));
  vals = bodyRows(ov).map((tr) => numOf(cellText(tr, COL.calls)));
  ok("B3 재클릭 = 오름차순 토글",
    vals.every((v, i) => i === 0 || vals[i - 1] <= v), `head=${vals.slice(0, 3)}`);
  ok("B4 오름차순 1행 = 전체 최소 호출", vals[0] === 50, `${vals[0]}`);

  click(headBtn(ov, "what"));
  const texts = bodyRows(ov).map((tr) => cellText(tr, COL.what));
  ok("B5 텍스트 열 첫 클릭 = 오름차순",
    texts.every((v, i) => i === 0 || texts[i - 1].localeCompare(v, "ko") <= 0), `head=${texts.slice(0, 2)}`);

  click(headBtn(ov, "last_used"));
  const when = bodyRows(ov).map((tr) => Date.parse(cellText(tr, COL.when)) || 0);
  ok("B6 일시 열 첫 클릭 = 최신순(내림차순)",
    when.every((v, i) => i === 0 || when[i - 1] >= v), `head=${when.slice(0, 2)}`);

  click(headBtn(ov, "cost_usd"));
  const cost = bodyRows(ov).map((tr) => numOf(cellText(tr, COL.cost)));
  ok("B7 비용 열 정렬(— 은 0 으로 취급되어 뒤로)",
    cost.every((v, i) => i === 0 || cost[i - 1] >= v), `head=${cost.slice(0, 3)}`);
}

// ── (C) 표시-정렬 정합: '주체' 는 화면 라벨 기준 ────────────────────────────────
console.log("\n[C] 표시-정렬 정합");
{
  const ov = openModal();
  click(headBtn(ov, "who"));
  const who = bodyRows(ov).map((tr) => cellText(tr, COL.who));
  ok("C1 주체 열 오름차순(표시 라벨 기준)",
    who.every((v, i) => i === 0 || who[i - 1].localeCompare(v, "ko") <= 0), `head=${who.slice(0, 3)}`);
  ok("C2 raw sentinel 이 화면에 새지 않는다", who.every((v) => v.indexOf("__") < 0), who.find((v) => v.indexOf("__") >= 0));
  ok("C3 워커 라벨이 번역돼 있다", who.some((v) => v.indexOf("인사이트 워커") >= 0 || v.indexOf("요청 처리 워커") >= 0));
  // sentinel 로 정렬했다면 '__ask_worker__' < '__insight_worker__' 라 요청 처리 워커가 먼저 온다.
  // 라벨로 정렬하면 "요청 처리 워커" > "인사이트 워커" (ko) 이므로 순서가 뒤집힌다 — 그 차이를 본다.
  const firstWorker = who.find((v) => v.indexOf("워커") >= 0);
  ok("C4 라벨 기준 정렬 결과(요청 처리 워커가 인사이트 워커보다 앞)",
    firstWorker === "요청 처리 워커", firstWorker);
}

// ── (D) 페이지네이션 ──────────────────────────────────────────────────────────
console.log("\n[D] 페이지네이션");
{
  const ov = openModal();
  const pos = () => $(ov, ".usage-rec-pager-pos").textContent.replace(/\s/g, "");
  const btn = (act) => $(ov, `[data-usage-page="${act}"]`);
  ok("D1 첫 페이지에서 이전/처음 비활성", btn("prev").disabled && btn("first").disabled);
  ok("D2 페이지 표시 1 / 3", pos() === "1/3", pos());

  const page1First = cellText(bodyRows(ov)[0], COL.what);
  click(btn("next"));
  ok("D3 다음 페이지로 이동", pos() === "2/3", pos());
  ok("D4 2페이지 첫 행이 1페이지와 다르다", cellText(bodyRows(ov)[0], COL.what) !== page1First);
  ok("D5 2페이지도 50행", bodyRows(ov).length === 50);

  click(btn("last"));
  ok("D6 마지막 페이지", pos() === "3/3", pos());
  ok("D7 마지막 페이지는 나머지 20행", bodyRows(ov).length === 20, `rows=${bodyRows(ov).length}`);
  ok("D8 마지막에서 다음/끝 비활성", btn("next").disabled && btn("last").disabled);
  const info = $(ov, ".usage-rec-pager-info").textContent;
  ok("D9 표시 구간이 101–120", /101/.test(info) && /120/.test(info), info);

  click(btn("prev"));
  ok("D10 이전 페이지", pos() === "2/3", pos());

  // 정렬을 바꾸면 1페이지로 — 3페이지에 머물면 정렬이 바뀐 게 보이지 않는다.
  click(btn("last"));
  click(headBtn(ov, "calls"));
  ok("D11 정렬 변경 시 1페이지 복귀", pos() === "1/3", pos());

  // 페이지당 행 수 — 25 / 전체. 페이저는 매 렌더에 새로 그려지므로 select 를 **그때마다 다시
  // 조회**한다(이전 노드는 문서에서 떨어져 이벤트가 위임 지점까지 올라가지 않는다).
  const setSize = (v) => {
    const sel = $(ov, ".usage-rec-page-size");
    sel.value = v;
    sel.dispatchEvent(new window.Event("change", { bubbles: true }));
  };
  ok("D12 페이지당 행 수 선택기 존재", !!$(ov, ".usage-rec-page-size"));
  setSize("25");
  ok("D13 25행 적용", bodyRows(ov).length === 25 && pos() === "1/5", `${bodyRows(ov).length} ${pos()}`);
  setSize("0");
  ok("D14 '전체' 는 한 페이지에 전 행", bodyRows(ov).length === 120 && pos() === "1/1",
    `${bodyRows(ov).length} ${pos()}`);
  ok("D15 전체 모드에선 페이지 이동 비활성", btn("next").disabled && btn("prev").disabled);
}

// ── (E) nav 정체성 — 정렬·페이지 이동 후에도 그 행의 목적지 ────────────────────
console.log("\n[E] nav 정체성");
{
  const ov = openModal();
  const navBtnOf = (tr) => $(tr, "[data-usage-nav]");
  // 시스템 행만 골라 '작업 · 대상' 텍스트 ↔ data-usage-nav 인덱스의 대응을 수집.
  const mapOf = () => {
    const m = new Map();
    bodyRows(ov).forEach((tr) => {
      const b = navBtnOf(tr);
      if (b) m.set(cellText(tr, COL.what), b.getAttribute("data-usage-nav"));
    });
    return m;
  };
  const before = mapOf();
  ok("E1 시스템 행에 nav 트리거가 있다", before.size > 0, `n=${before.size}`);
  click(headBtn(ov, "what"));            // 정렬 변경
  click($(ov, '[data-usage-page="next"]'));  // 페이지 이동
  click($(ov, '[data-usage-page="prev"]'));
  click(headBtn(ov, "calls"));
  const after = mapOf();
  let stable = true, sample = null;
  after.forEach((idx, label) => {
    if (before.has(label) && before.get(label) !== idx) { stable = false; sample = label; }
  });
  ok("E2 같은 행은 정렬·페이지 이동 뒤에도 같은 nav 인덱스", stable, sample);

  // 실제 이동 — 인덱스로 되짚은 nav 가 그 행이 표시한 대상과 맞는지.
  // 현재 정렬(호출 내림차순)에서는 1페이지가 대화 행으로만 채워질 수 있으므로, 시스템 행이
  // 나오는 페이지까지 넘겨서 고른다(고정 페이지를 가정하지 않는다).
  let tr = bodyRows(ov).find((r) => navBtnOf(r));
  for (let guard = 0; !tr && guard < 10; guard++) {
    const next = $(ov, '[data-usage-page="next"]');
    if (!next || next.disabled) break;
    click(next);
    tr = bodyRows(ov).find((r) => navBtnOf(r));
  }
  ok("E2b 시스템 행을 찾았다", !!tr);
  const label = cellText(tr, COL.what);
  const target = (label.match(/table_(\d+)/) || [])[1];
  navCalls.length = 0;
  // 모달 안에 탭 버튼이 없으면 applyUsageNav 가 조기 반환하므로, 이동 대상 탭을 문서에 심는다.
  const tab = window.document.createElement("button");
  tab.className = "admin-tab";
  tab.setAttribute("data-admin-tab", "metadata");
  window.document.body.appendChild(tab);
  const search = window.document.createElement("input");
  search.id = "metadataSearch";
  window.document.body.appendChild(search);
  click(navBtnOf(tr));
  ok("E3 클릭이 그 행의 화면으로 이동시킨다", navCalls[0] === "metadata", navCalls.join(","));
  ok("E4 이동 시 그 행의 대상이 검색어로 주입된다", search.value === `table_${target}`,
    `${search.value} vs table_${target}`);
  ok("E5 이동 성공 시 모달이 닫힌다", !window.document.getElementById("usageConvModalOverlay"));
  tab.remove(); search.remove();
}

// ── (F) 이스케이프 ────────────────────────────────────────────────────────────
console.log("\n[F] 이스케이프");
{
  const evil = '<img src=x onerror="window.__pwned=1">';
  M.showUsageConvModal({
    scope: "admin",
    title: "x",
    data: {
      items: [{ conversation_id: "c1", topic: evil, owner_username: evil, calls: 1, total_tokens: 1, cost_usd: 0 }],
      system_items: [{ actor: "__insight_worker__", task_label: evil, target: evil, calls: 1, total_tokens: 2, cost_usd: 0 }],
    },
  });
  const ov = window.document.getElementById("usageConvModalOverlay");
  ok("F1 주입된 이미지 태그가 만들어지지 않는다", $$(ov, "img").length === 0);
  ok("F2 원문이 텍스트로 보인다", ov.textContent.indexOf("onerror") >= 0);
  ok("F3 전역 오염 없음", window.__pwned === undefined);
}

// ── (G) 키보드 연속 조작 — 재렌더가 포커스를 삼키지 않는다 ─────────────────────
// 적대 리뷰 [P2]: thead/tbody/페이저를 innerHTML 로 교체하면 방금 누른 컨트롤이 사라져
// 포커스가 body 로 빠진다 → 정렬 방향 토글도, 연속 페이지 이동도 키보드로 못 한다.
console.log("\n[G] 키보드 연속 조작");
{
  const ov = openModal();
  const sortBtn = headBtn(ov, "calls");
  sortBtn.focus();
  click(sortBtn);
  const afterSort = window.document.activeElement;
  ok("G1 정렬 후에도 그 열 머리에 포커스가 남는다",
    afterSort && afterSort.getAttribute && afterSort.getAttribute("data-usage-sort") === "calls",
    afterSort && afterSort.tagName);
  // 남은 포커스로 곧바로 방향 토글이 되는지(연속 조작의 실제 목적).
  click(window.document.activeElement);
  const vals = bodyRows(ov).map((tr) => numOf(cellText(tr, COL.calls)));
  ok("G2 이어서 누르면 방향이 토글된다", vals.every((v, i) => i === 0 || vals[i - 1] <= v),
    `head=${vals.slice(0, 3)}`);

  const next = $(ov, '[data-usage-page="next"]');
  next.focus();
  click(next);
  const afterPage = window.document.activeElement;
  ok("G3 페이지 이동 후에도 '다음' 버튼에 포커스가 남는다",
    afterPage && afterPage.getAttribute && afterPage.getAttribute("data-usage-page") === "next",
    afterPage && afterPage.tagName);

  // 마지막 페이지로 가면 '다음' 이 비활성 — 포커스를 body 로 떨구지 않고 활성 컨트롤로 옮긴다.
  const last = $(ov, '[data-usage-page="last"]');
  last.focus();
  click(last);
  const afterLast = window.document.activeElement;
  ok("G4 경계에서 비활성이 되면 페이저의 활성 컨트롤로 옮긴다",
    !!afterLast && afterLast !== window.document.body && !afterLast.disabled
      && ov.contains(afterLast),
    afterLast && (afterLast.getAttribute("data-usage-page") || afterLast.tagName));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
