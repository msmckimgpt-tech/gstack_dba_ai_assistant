// verify_attach_version_action_align.mjs
// REQ-20260811T-attach-version-action-align — 첨부 버전 이력 행의 **액션 열 정렬**.
//
// 사용자 보고(2026-08-11, 스크린샷 동반): "버전비교 버튼의 유무에 따라, 문서 원문을 조회하는
// 버튼의 위치가 뒤틀리는 것을 확인했습니다."
//
// 기전: `.attach-list-version-actions` 는 `margin-left: auto` 로 **오른쪽 정렬**된 flex 다.
// 그래서 행마다 버튼 **개수**가 다르면 있는 버튼들이 통째로 밀려, 같은 기능의 아이콘이 행마다
// 다른 x 좌표에 선다. 체인 안에서 실제로 갈리는 슬롯은 둘:
//   - `⇄`(비교) — 최신 행에만 없다(자기 자신과의 비교는 무의미. 그 계약 자체는 유지한다).
//   - `🗑`(삭제) — 서버 `can_manage` 가 **행별 술어**(`is_owner || row.AccountId == 나`)라
//     그룹 대화에서 업로더가 섞이면 행마다 갈린다.
//
// 검증 4축:
//   (A) 슬롯 수 불변 — 같은 체인의 모든 행이 **같은 개수**의 액션 슬롯을 갖는다(실 DOM).
//   (B) 슬롯 순서 불변 — 각 행의 슬롯 종류 배열이 같다(👁 자리는 항상 첫째 …).
//   (C) 예약은 필요한 만큼만 — 아무도 못 쓰는 슬롯(예: 전원 can_manage=false 인 `🗑`)은
//       예약하지 않는다. 쓰이지도 않는 빈 여백을 상시로 남기지 않는다.
//   (D) 접근성·CSS — 빈 슬롯은 보조기술에 노출되지 않고 포커스도 받지 않으며, 슬롯 폭이
//       글리프가 아니라 **규칙**으로 고정된다(아이콘 advance 폭이 제각각이라 폰트가 바뀌면
//       같은 열도 폭이 달라진다).
//
// 실행: node verify_attach_version_action_align.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 픽셀 정렬 확인은 PB-0008 실 Windows 브라우저 — jsdom 은 레이아웃을 계산하지 않는다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const composerJs = read("app", "composer.js");
const chatCss = read("css", "chat.css");

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

// composer.js 는 모듈 전체를 태울 수 없다(app.js 전역 의존 다수) — 대상 함수 한 블록만
// 중괄호 밸런스로 떼어 **실제로 실행**한다. 정적 문자열 검사는 "코드에 그런 줄이 있다" 까지만
// 알 수 있고, 행마다 슬롯이 몇 개 붙는지는 실행해야 드러난다.
function extractFn(src, name) {
  const start = src.search(new RegExp(`(?:export\\s+)?function ${name}\\(`));
  if (start < 0) return null;
  let p = src.indexOf("(", start), paren = 0, sigEnd = -1;
  for (let j = p; j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let i = src.indexOf("{", sigEnd), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return end < 0 ? null : src.slice(start, end);
}

const fnSrc = extractFn(composerJs, "_renderAttachmentVersionsBox");
// 빈 슬롯 primitive 는 **모듈 레벨 단일 정의**다(세 목록이 공유) — 함께 태운다.
const slotSrc = extractFn(composerJs, "_attachActionSlot");
ok("함수 추출됨", !!fnSrc && !!slotSrc);

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
const noop = () => {};
const render = new Function(
  "document", "openAttachmentSourceModal", "openAttachmentDiffModal",
  "_downloadAttachmentById", "_openAttachDeleteModal", "_fmtAttachWhen", "_attachWhenTitle",
  `${slotSrc}\n${fnSrc.replace(/^export\s+/, "")}\nreturn _renderAttachmentVersionsBox;`
)(window.document, noop, noop, noop, noop, () => "8/6", () => "2026-08-06");

const mkVersions = (specs) => specs.map((sp, i) => ({
  id: 100 + i,
  version_number: i + 1,
  original_filename: "P_gunzgame_Game_BuyCurrencyItem.sql",
  created_at: "2026-08-06T00:00:00",
  superseded: i !== specs.length - 1,        // 마지막이 최신
  can_manage: Boolean(sp.can_manage),
  is_assistant_generated: false,
}));

// 각 행의 액션 슬롯을 "종류 배열" 로 읽는다 — 빈 슬롯도 한 자리로 센다.
const slotsOf = (box) =>
  Array.from(box.querySelectorAll(".attach-list-version-actions")).map((acts) =>
    Array.from(acts.children).map((el) => {
      const c = el.className || "";
      return c.replace("attach-list-version-", "").replace("attach-list-item-", "").replace("attach-list-action-", "");
    }));

const renderChain = (specs) => {
  const box = window.document.createElement("div");
  render(box, mkVersions(specs), 100);
  return box;
};

// ── (A)(B) 슬롯 수·순서 불변 ────────────────────────────────────────────────
console.log("\n[A/B] 액션 슬롯 수·순서 불변");
{
  // 사용자 보고 재현 조건: 버전 여럿 + 전원 관리 가능(⇄ 만 최신 행에서 빠진다).
  const box = renderChain([{ can_manage: true }, { can_manage: true }, { can_manage: true }]);
  const slots = slotsOf(box);
  ok("A1 행이 3개", slots.length === 3, JSON.stringify(slots));
  const counts = slots.map((r) => r.length);
  ok("A2 모든 행의 슬롯 수가 같다", new Set(counts).size === 1, JSON.stringify(counts));
  // 열 정렬의 계약은 "클래스가 같다" 가 아니다 — 예약 슬롯과 실제 버튼은 **같은 자리**를
  // 차지해야 한다(그래야 x 좌표가 고정된다). 열마다 실제 기능은 하나이고 나머지는 `slot` 이다.
  const columnKinds = (rows) => {
    const w = Math.max(...rows.map((r) => r.length));
    return Array.from({ length: w }, (_, i) => {
      const kinds = new Set(rows.map((r) => r[i]).filter(Boolean));
      kinds.delete("slot");
      return { i, kinds: [...kinds] };
    });
  };
  const cols = columnKinds(slots);
  ok("B1 각 열은 한 기능만 갖는다(나머지는 예약 슬롯)",
    cols.every((c) => c.kinds.length === 1), JSON.stringify(cols));
  ok("B1b 열 순서는 원문·비교·다운로드·삭제",
    cols.map((c) => c.kinds[0]).join(",") === "src,cmp,dl,del",
    JSON.stringify(cols.map((c) => c.kinds[0])));
  ok("B2 첫 슬롯은 항상 원문 보기(👁)", slots.every((r) => r[0] === "src"), JSON.stringify(slots));
  // 최신 행은 실제 `⇄` 대신 **빈 슬롯**을 갖는다(비교 버튼 자체는 두지 않는다는 계약 유지).
  const latest = slots[0];   // ordered 는 최신이 위
  ok("B3 최신 행의 비교 자리는 빈 슬롯", latest[1] === "slot", JSON.stringify(latest));
  ok("B3b 최신 행에 실제 비교 버튼은 없다",
    !box.querySelector(".attach-list-version-row:first-child .attach-list-version-cmp") ||
    Array.from(box.querySelectorAll(".attach-list-version-actions"))[0]
      .querySelector(".attach-list-version-cmp") === null);
  ok("B4 구버전 행에는 실제 비교 버튼", slots[1][1] === "cmp" && slots[2][1] === "cmp",
    JSON.stringify(slots));
}

// 삭제 권한이 행마다 갈리는 그룹 대화 — `can_manage` 는 서버에서 행별 술어다.
{
  const box = renderChain([{ can_manage: true }, { can_manage: false }, { can_manage: true }]);
  const slots = slotsOf(box);
  const counts = slots.map((r) => r.length);
  ok("A3 can_manage 가 행마다 갈려도 슬롯 수 동일", new Set(counts).size === 1,
    JSON.stringify(slots));
  ok("B5 삭제 못 하는 행은 마지막 자리가 빈 슬롯",
    slots.some((r) => r[r.length - 1] === "slot"), JSON.stringify(slots));
  ok("B5b 삭제 가능한 행은 마지막 자리가 실제 버튼",
    slots.some((r) => r[r.length - 1] === "del"), JSON.stringify(slots));
}

// ── (C) 예약은 필요한 만큼만 ────────────────────────────────────────────────
console.log("\n[C] 불필요한 예약 금지");
{
  const box = renderChain([{ can_manage: false }, { can_manage: false }]);
  const slots = slotsOf(box);
  // 비교 슬롯은 예약되지만(체인에 비교가 존재) 삭제 슬롯은 아무도 못 쓰므로 예약하지 않는다 —
  // 쓰이지도 않는 빈 여백을 상시로 남기지 않는다는 것이 이 축의 계약이다.
  ok("C1 아무도 삭제 못 하면 삭제 슬롯을 예약하지 않는다",
    slots.every((r) => !r.includes("del")) && slots.every((r) => r.length === 3),
    JSON.stringify(slots));
  ok("C1c 비교 슬롯은 여전히 예약된다(체인에 비교가 있다)",
    slots.some((r) => r.includes("slot")) && slots.some((r) => r.includes("cmp")),
    JSON.stringify(slots));
  ok("C1b 그래도 행 간 슬롯 수는 같다", new Set(slots.map((r) => r.length)).size === 1);

  // 버전이 하나뿐이면 비교 자체가 성립하지 않으므로 그 슬롯도 예약하지 않는다.
  const single = renderChain([{ can_manage: true }]);
  const s1 = slotsOf(single);
  ok("C2 단일 버전은 비교 슬롯 미예약", s1.length === 1 && !s1[0].includes("slot"),
    JSON.stringify(s1));
}

// ── (D) 접근성 · CSS 폭 규칙 ────────────────────────────────────────────────
console.log("\n[D] 빈 슬롯의 접근성 · 폭 규칙");
{
  const box = renderChain([{ can_manage: true }, { can_manage: true }]);
  const spacers = Array.from(box.querySelectorAll(".attach-list-action-slot"));
  ok("D1 빈 슬롯이 실제로 생성된다", spacers.length > 0);
  ok("D2 빈 슬롯은 보조기술에 노출되지 않는다",
    spacers.every((s) => s.getAttribute("aria-hidden") === "true"));
  ok("D3 빈 슬롯은 포커스를 받지 않는다(버튼이 아니다)",
    spacers.every((s) => s.tagName === "SPAN" && !s.hasAttribute("tabindex")));
  ok("D4 빈 슬롯에 라벨·텍스트가 없다",
    spacers.every((s) => (s.textContent || "") === "" && !s.getAttribute("title")));
  // 폭을 글리프에 맡기면 폰트·플랫폼이 바뀔 때 같은 열도 폭이 달라진다(👁·⇄·⬇·🗑 advance 상이).
  // ⚠️ `min-width` 는 **바닥**이라 글리프가 그 값을 넘으면 열이 다시 갈린다(§18.8 ux 실증:
  // 16px 확대 시 버튼 22→24px, 그 행의 `👁` 만 1135→1133). `flex-basis` 로 못을 박고
  // `min-width: 0` 으로 flex 자동 최소 크기가 되밀지 못하게 해야 폭이 **고정**된다.
  ok("D5 슬롯 폭이 flex-basis 로 고정된다(바닥 아님)",
    /\.attach-list-version-actions\s*>\s*\*,[\s\S]{0,80}flex:\s*0 0 22px;[\s\S]{0,40}min-width:\s*0/.test(chatCss));
  ok("D5d min-width 를 바닥으로 쓰지 않는다", !/min-width:\s*22px/.test(chatCss));
  ok("D5b 슬롯이 flex 로 늘어나지 않는다", /flex:\s*0 0 22px/.test(chatCss));
  // 같은 결함 클래스를 한쪽만 고치지 않는다 — 활성 목록·휴지통도 같은 오른쪽 정렬 flex 다.
  ok("D5c 폭 규칙이 활성/휴지통 목록 컨테이너에도 걸린다",
    /\.attach-list-item-actions\s*>\s*\*/.test(chatCss));
  ok("D6 빈 슬롯 CSS 정의 존재", /\.attach-list-action-slot\s*\{/.test(chatCss));
}

// ── (E) 같은 결함 클래스의 형제 목록 ────────────────────────────────────────
// 이 결함은 "버전 이력" 만의 것이 아니다 — 첨부 목록 3종이 모두 `margin-left: auto` 오른쪽
// 정렬 flex 이고 셋 다 조건부 버튼을 갖는다. 한쪽만 고치면 같은 증상이 다른 화면에 남는다.
//
// 휴지통은 버전 박스와 같은 관용구로 **실행**해서 슬롯 배열을 대조한다 — 소스 정규식은
// "코드에 그런 줄이 있다" 까지만 알 뿐, 슬롯을 엉뚱한 컨테이너에 붙이거나 순서를 뒤집어도
// 통과한다(§18.8 ux 지적 — 이 파일의 헤더가 스스로 금지한 방식이었다).
console.log("\n[E] 형제 목록(활성 · 휴지통)에도 같은 예약");
{
  ok("E1 빈 슬롯 primitive 는 단일 정의(복제 금지)",
    (composerJs.match(/function _attachActionSlot\(/g) || []).length === 1 &&
    (composerJs.match(/_attachActionSlot\(\)/g) || []).length >= 3);

  // ── 휴지통: 실행 테스트 ──
  const trashSrc = extractFn(composerJs, "_renderTrashAttachmentList");
  ok("E2 휴지통 렌더러 추출됨", !!trashSrc);
  const renderTrash = new Function(
    "document", "escapeHtml", "fmtSize", "remainText", "_performAttachRestore", "_attachActionSlot",
    `${trashSrc.replace(/^export\s+/, "")}\nreturn _renderTrashAttachmentList;`
  )(window.document, (v = "") => String(v), (b) => `${b}B`, () => "3일 남음", () => {},
    new Function("document", `${slotSrc}\nreturn _attachActionSlot;`)(window.document));

  const trashRows = (arr) => {
    const host = window.document.createElement("div");
    renderTrash(host, arr);
    return Array.from(host.querySelectorAll(".attach-list-item-actions")).map((a) =>
      Array.from(a.children).map((el) => (el.className || "")
        .replace("attach-list-item-", "").replace("attach-list-action-", "")));
  };
  // 체인(root 9, 2개) + 단독(root 7) — 체인 머리에만 `⇤` 가 붙는다.
  const rows = trashRows([
    { id: 91, root_attachment_id: 9, version_number: 2, can_manage: true, size: 1 },
    { id: 92, root_attachment_id: 9, version_number: 1, can_manage: true, size: 1 },
    { id: 70, root_attachment_id: 7, version_number: 1, can_manage: true, size: 1 },
  ]);
  ok("E3 휴지통 3행 렌더", rows.length === 3, JSON.stringify(rows));
  ok("E4 모든 행의 슬롯 수가 같다", new Set(rows.map((r) => r.length)).size === 1,
    JSON.stringify(rows));
  ok("E5 체인 머리만 실제 전체복구(⇤), 나머지는 빈 슬롯",
    rows.filter((r) => r.includes("restore is-chain")).length === 1 &&
    rows.filter((r) => r.includes("slot")).length === 2, JSON.stringify(rows));
  ok("E6 빈 슬롯은 항상 **마지막 자리**(열 순서 보존)",
    rows.every((r) => r[r.length - 1] === "slot" || r[r.length - 1] === "restore is-chain"),
    JSON.stringify(rows));
  // 체인 머리가 없으면(단독 항목뿐) 슬롯을 예약하지 않는다.
  const solo = trashRows([{ id: 70, root_attachment_id: 7, version_number: 1, can_manage: true, size: 1 }]);
  ok("E7 체인 머리가 없으면 예약하지 않는다", !solo[0].includes("slot"), JSON.stringify(solo));

  // ── 활성 목록: 실행 불가(async + apiFetch) → **구조 단언으로 defer 하고 그 사실을 남긴다** ──
  // 픽셀 근거는 PB-0008 에서 DOM-level control 로 확보했다(test-runs fragment 좌표 표).
  ok("E8 활성 목록이 삭제 슬롯을 예약한다(구조 — 실행 테스트는 async 라 defer)",
    /const anyItemManage = arr\.some\(/.test(composerJs) &&
    /if \(anyItemManage && !a\.can_manage\) \{\s*\n\s*item\.querySelector\("\.attach-list-item-actions"\)\.appendChild\(_attachActionSlot\(\)\);/
      .test(composerJs));
  ok("E9 세 목록 모두 '쓰이는 슬롯만' 예약한다(불필요 여백 금지)",
    /anyItemManage &&/.test(composerJs) && /anyChainHead &&/.test(composerJs) &&
    /anyManage &&/.test(composerJs));
}

// ⚠️ 이 하네스가 보장하지 **못하는** 것 (정직 표기): jsdom 은 레이아웃을 계산하지 않으므로
// "슬롯 수가 같다" 는 픽셀 정렬의 **필요조건**일 뿐이다. 실제 x 좌표 일치는 PB-0008 실 브라우저
// `getBoundingClientRect` 실측이 정본이고, 그 결과는 test-runs.d fragment 에 좌표로 기록한다.

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
