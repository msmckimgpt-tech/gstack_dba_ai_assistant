// verify_attach_source_view.mjs
// REQ-20260807T-attach-source-view — 첨부 **원문 보기**(버전이 하나뿐인 첨부 포함).
//
// 사용자 요청: "별도로 추가된 버전이 없는 첨부파일 또한, 클릭했을 때 문서 원문이 출력되도록
// 구성해주세요." (2026-08-07)
//
// 종전: 첨부 목록의 행은 **클릭 대상이 아니었다**(⬇·🗑·"버전 N개" 버튼만 배선). 내용을 보는
// 유일한 길이 "버전 2개 이상일 때의 비교 모달" 이었으므로, 버전이 하나인 첨부(대다수)는
// 내려받지 않고는 내용을 볼 수 없었다.
//
// 검증 5축:
//   (A) 모달 — 원문 표·줄번호·**원문 무손실**·통계·빈 문서. 정본 모듈을 jsdom 위에서 실제 실행.
//   (B) 강등·절단 — 바이너리(viewable=false)는 메타로, 절단 2종은 배너로. 무음 금지.
//   (C) 하이라이트 — 비교 모달과 **같은 primitive·같은 저장 키**(한쪽에서 끈 설정이 다른 쪽에도).
//   (D) 배선 — `composer.js` 의 목록 행이 클릭·키보드로 원문 모달을 열고, 행 안의 버튼은
//       부모로 이벤트를 올리지 않는다(삭제하려다 원문이 함께 열리면 안 된다).
//   (E) 계약 — ESM specifier `?v=dev` · 단일 primitive 재사용(렌더러 복제 0) · 버전 파라미터 부재.
//
// 실행: node verify_attach_source_view.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인은 PB-0008 실 Windows 브라우저(§15.4.1).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const composerJs = read("app", "composer.js");
const chatCss = read("css", "chat.css");
const attachmentsPy = readFileSync(
  join(__dirname, "..", "src", "routers", "attachments.py"), "utf8");
const storePy = readFileSync(
  join(__dirname, "..", "src", "routers", "_conv_store.py"), "utf8");

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

const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/m, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존"); process.exit(2); }

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
let API_RESPONSE = {};
let API_STATUS = 200;
let API_CALLS = [];
let HL_STORE = {};
const CH = new Function(`${read("code-highlight.js").replace(/^export\s+/gm, "")}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();
const _stubs = {
  document: window.document,
  window,
  localStorage: {
    getItem: (k) => (k in HL_STORE ? HL_STORE[k] : null),
    setItem: (k, v) => { HL_STORE[k] = String(v); },
    removeItem: (k) => { delete HL_STORE[k]; },
  },
  requestAnimationFrame: (fn) => fn(),
  // **실 `apiFetch` 와 같은 계약**: non-2xx 는 throw 하고 메시지는
  // `payload.error || payload.detail || statusText` 로 고른다. 항상 resolve 하는 stub 은
  // 오류 경로를 vacuous pass 시킨다(§18.8 ux 지적 — 503 분기가 도달 불가인 채 통과했다).
  apiFetch: async (url) => {
    API_CALLS.push(url);
    if (API_STATUS >= 400) {
      const err = new Error(API_RESPONSE.error || API_RESPONSE.detail || "Service Unavailable");
      err.status = API_STATUS;
      err.payload = API_RESPONSE;
      throw err;
    }
    return API_RESPONSE;
  },
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage: CH.detectCodeLanguage,
  paintCodeInto: CH.paintCodeInto,
  codeLanguageLabel: CH.codeLanguageLabel,
};
const EXPORTS = ["openAttachmentSourceModal", "openAttachmentDiffModal", "_renderSource"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`로드됨 ${n}`, typeof M[n] === "function");

const SRC_LINES = [
  "-- 단일 버전 첨부",
  "SELECT id, name",
  "  FROM users;",
];
const OK_RESP = {
  viewable: true,
  attachment_id: 42,
  filename: "solo.sql",
  version: { id: 42, version_number: 1, created_by_role: "user", size: 108,
    sha256: "abcd1234", created_at: "2026-08-07", is_latest: true },
  rows: SRC_LINES.map((t, i) => ({ type: "equal", right_no: i + 1, right: t })),
  stats: { lines: SRC_LINES.length },
  truncated: { source: false, rows: false },
  caps: { source_bytes: 1048576, rows: 6000 },
};

const tick = () => new Promise((r) => setTimeout(r, 0));
const openWith = async (resp, opts, status) => {
  API_RESPONSE = resp; API_CALLS = []; API_STATUS = Number(status || 200);
  for (const el of Array.from(window.document.querySelectorAll(".attach-source-backdrop"))) el.remove();
  M.openAttachmentSourceModal(42, opts || { filename: "solo.sql" });
  await tick(); await tick();
  return window.document.querySelector(".attach-source-backdrop");
};

// ── (A) 모달 렌더 ────────────────────────────────────────────────────────────
console.log("\n[A] 원문 모달");
{
  const bd = await openWith(OK_RESP);
  ok("A1 모달이 열린다", !!bd);
  ok("A2 제목이 파일명", /solo\.sql/.test(bd.querySelector(".attach-diff-fname").textContent));
  ok("A3 원문 표 렌더", !!bd.querySelector("table.attach-diff-table.is-source"));
  const cells = Array.from(bd.querySelectorAll("table.is-source tr.attach-diff-row td:nth-child(2)"));
  ok("A4 행 수 = 줄 수", cells.length === SRC_LINES.length, `rows=${cells.length}`);
  // load-bearing — 화면이 "원문" 이라 주장하려면 렌더 텍스트가 원문이어야 한다.
  ok("A5 원문 무손실", cells.map((c) => c.textContent).join("\n") === SRC_LINES.join("\n"));
  const nos = Array.from(bd.querySelectorAll("table.is-source td.attach-diff-lineno"));
  ok("A6 줄번호 1..N", nos.map((n) => n.textContent).join(",") === "1,2,3");
  ok("A7 통계에 줄 수·크기", /3줄/.test(bd.querySelector(".attach-diff-stats").textContent));
  ok("A8 요청 URL 은 /source", API_CALLS.length === 1 && /\/api\/attachments\/42\/source$/.test(API_CALLS[0]),
    API_CALLS[0]);
  ok("A9 스크롤 컨테이너 안에 둔다(모달 폭 붕괴 방지)",
    !!bd.querySelector(".attach-diff-scroller table.is-source"));

  const empty = await openWith({ ...OK_RESP, rows: [], stats: { lines: 0 } });
  ok("A10 빈 문서는 '비어 있습니다'", /비어 있습니다/.test(empty.textContent));
  ok("A10b 빈 문서에는 표를 만들지 않는다", !empty.querySelector("table.is-source"));
}

// ── (B) 강등·절단 ────────────────────────────────────────────────────────────
console.log("\n[B] 강등 · 절단 표면화");
{
  const bin = await openWith({
    viewable: false, reason: "binary", attachment_id: 42, filename: "book.pdf",
    version: { version_number: 1, created_by_role: "user", size: 2048, sha256: "ff".repeat(8),
      created_at: "2026-08-07" },
  }, { filename: "book.pdf" });
  ok("B1 바이너리는 원문 표를 만들지 않는다", !bin.querySelector("table.is-source"));
  ok("B2 지원하지 않는 형식임을 알린다", /원문 보기를 지원하지 않습니다/.test(bin.textContent));
  ok("B3 메타 표로 강등(조용한 빈 화면 금지)", !!bin.querySelector("table.attach-diff-meta"));
  ok("B3b 메타에 크기·sha 가 있다", /2KB|2048/.test(bin.textContent) && /ff/.test(bin.textContent));

  // 원본 read 실패는 서버가 **503** 으로 답한다 → `apiFetch` 가 throw → catch 경로.
  // 서버가 payload 에 `error` 를 실어야 사용자가 한국어 사유를 본다(없으면 `Service Unavailable`).
  const unavail = await openWith({
    viewable: false, reason: "source_unavailable",
    error: "원본 파일을 읽을 수 없어 원문을 표시하지 못했습니다.",
  }, undefined, 503);
  ok("B4 원본 read 실패 사유가 화면에 도달한다(503 catch 경로)",
    /원본 파일을 읽을 수 없어/.test(unavail.textContent), unavail.textContent.slice(0, 80));
  ok("B4b 영문 HTTP 상태 문자열이 노출되지 않는다",
    !/Service Unavailable/.test(unavail.textContent));
  ok("B4c 서버가 503 payload 에 error 문구를 싣는다",
    /"error": "원본 파일을 읽을 수 없어 원문을 표시하지 못했습니다\."/.test(attachmentsPy));

  const capped = await openWith({
    ...OK_RESP, truncated: { source: false, rows: true }, stats: { lines: 20000 } });
  ok("B5 행 절단 배너", /문서가 길어/.test(capped.textContent) &&
    !!capped.querySelector(".attach-diff-notice.is-warn"));
  ok("B5b 절단돼도 본문은 렌더된다", !!capped.querySelector("table.is-source"));
  // "원문" 은 전량을 봤을 때만 쓸 수 있는 말 — 비교 모달이 명시적으로 금지한 것을 반복하지 않는다.
  ok("B5c 절단이면 제목이 '문서 앞부분' 으로 강도를 낮춘다",
    /문서 앞부분/.test(capped.querySelector(".attach-source-titleword").textContent));
  ok("B5d 절단이면 통계도 '앞 N행 표시' 로 말한다",
    /앞 \d+행 표시/.test(capped.querySelector(".attach-diff-stats").textContent),
    capped.querySelector(".attach-diff-stats").textContent);

  const srcCapped = await openWith({ ...OK_RESP, truncated: { source: true, rows: false } });
  ok("B6 원본 cap 절단 배너가 cap 크기를 밝힌다",
    /1MB/.test(srcCapped.textContent) && /이후 내용은 보이지 않습니다/.test(srcCapped.textContent));
}

// ── (C) 하이라이트 — 비교 모달과 같은 primitive·같은 저장 키 ──────────────────
console.log("\n[C] 구문 하이라이트");
{
  HL_STORE = {};
  const bd = await openWith(OK_RESP);
  ok("C1 .sql 이면 토글 노출", bd.querySelector(".attach-diff-hltoggle").hidden === false);
  ok("C2 라벨이 유형을 밝힌다", /SQL/.test(bd.querySelector(".attach-diff-hl-label").textContent));
  ok("C3 토큰 span 이 칠해진다",
    bd.querySelectorAll(".attach-diff-code [class^=code-tok-]").length > 0);
  // 끄면 평문 — 재요청 없이 재렌더(비교 모달과 동일 계약).
  const before = API_CALLS.length;
  const cb = bd.querySelector(".attach-diff-hl");
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change"));
  ok("C4 끄면 span 0(평문 경로)",
    bd.querySelectorAll(".attach-diff-code [class^=code-tok-]").length === 0);
  ok("C4b 토글은 재요청하지 않는다", API_CALLS.length === before);
  const cells = Array.from(bd.querySelectorAll("table.is-source tr.attach-diff-row td:nth-child(2)"));
  ok("C4c 꺼도 원문 무손실", cells.map((c) => c.textContent).join("\n") === SRC_LINES.join("\n"));
  ok("C5 끈 상태가 저장된다(비교 모달과 같은 키)", HL_STORE.attachDiffHighlight === "0");
  // 미지원 확장자는 토글 자체를 숨긴다 — 칠할 수 없는 화면의 거짓 어포던스 금지.
  const bin = await openWith({ ...OK_RESP, filename: "notes.xyz" }, { filename: "notes.xyz" });
  ok("C6 미지원 확장자는 토글 숨김", bin.querySelector(".attach-diff-hltoggle").hidden === true);
  const noRows = await openWith({ ...OK_RESP, rows: [], stats: { lines: 0 } });
  ok("C6b 칠할 본문이 없어도 토글 숨김",
    noRows.querySelector(".attach-diff-hltoggle").hidden === true);
  HL_STORE = {};
}

// ── (D) 배선 — composer.js 목록 행 ───────────────────────────────────────────
console.log("\n[D] 첨부 목록 행 배선");
{
  ok("D1 composer 가 원문 모달을 import",
    /import \{ openAttachmentDiffModal, openAttachmentSourceModal \} from "\.\/attach-diff\.js\?v=dev"/
      .test(composerJs));
  ok("D2 행에 클릭 어포던스 클래스(마우스 편의 히트영역)",
    /item\.classList\.add\("is-openable"\)/.test(composerJs));
  // **행이 아니라 파일명**이 버튼이다 — 행에 role=button 을 주면 그 안의 ⬇·🗑·버전 토글이
  // 버튼 안의 버튼이 되고 보조기술이 행 전체 텍스트를 버튼 이름으로 읽는다(§18.8 ux/security).
  ok("D3 행에는 role=button 을 주지 않는다(중첩 버튼 회피)",
    !/item\.setAttribute\("role", "button"\)/.test(composerJs) && !/item\.tabIndex = 0/.test(composerJs));
  ok("D3b 파일명이 버튼 시맨틱을 갖는다",
    /nameBtn\.setAttribute\("role", "button"\)/.test(composerJs) && /nameBtn\.tabIndex = 0/.test(composerJs));
  ok("D3c 파일명 버튼에 파일명 기반 aria-label",
    /nameBtn\.setAttribute\("aria-label", `\$\{a\.original_filename[^`]*\} 원문 보기`\)/.test(composerJs));
  ok("D4 파일명 클릭이 원문 모달을 연다(행 핸들러로 전파 안 함)",
    /nameBtn\.addEventListener\("click", \(ev\) => \{ ev\.stopPropagation\(\); openSource\(\); \}\)/.test(composerJs));
  ok("D5 Enter/Space 키보드 경로", /ev\.key !== "Enter" && ev\.key !== " "/.test(composerJs));
  // 행 안의 버튼(⬇·🗑·버전 토글)이 부모로 올라가면 삭제하려다 원문이 함께 열린다.
  const clickStart = composerJs.indexOf('item.addEventListener("click"');
  const clickBlock = composerJs.slice(clickStart, composerJs.indexOf("entry.appendChild(item);", clickStart));
  ok("D6 행 클릭이 안쪽 버튼을 걸러낸다",
    clickStart > 0 && /ev\.target\.closest\("button"\)/.test(clickBlock));
  // 드래그 선택 후 손을 떼면 click target 이 공통 조상(행)으로 승격된다 — `modal-dismiss.js`
  // 가 배경 dismiss 에서 봉인한 것과 같은 기전. press-pair + selection 가드로 막는다.
  ok("D6b 드래그 선택이 클릭으로 오인되지 않는다(press-pair 이동거리 가드)",
    /item\.addEventListener\("pointerdown"/.test(composerJs) &&
    /Math\.hypot\(ev\.clientX - pressAt\.x, ev\.clientY - pressAt\.y\) > 5/.test(clickBlock));
  ok("D6c 행 안에 선택 영역이 남아 있으면 열지 않는다",
    /!sel\.isCollapsed && sel\.anchorNode && item\.contains\(sel\.anchorNode\)/.test(clickBlock));
  ok("D7 hover 시각 어포던스 + 파일명 포커스 링 CSS",
    /\.attach-list-item\.is-openable:hover/.test(chatCss) &&
    /\.attach-list-item-name-text\[role="button"\]:focus-visible/.test(chatCss));
  ok("D7b 액션 버튼 위에서는 행 하이라이트를 끈다(삭제와 열기가 같은 신호를 갖지 않게)",
    /\.attach-list-item\.is-openable:has\(\.attach-list-item-actions:hover\)/.test(chatCss));
  ok("D8 커서 pointer", /\.attach-list-item\.is-openable\s*\{[^}]*cursor:\s*pointer/.test(chatCss));
  // 어포던스 문구는 사실과 맞춘다 — 서버 판정 기준이 kind 하나뿐이고 클라이언트가 그 값을 안다.
  ok("D8b 지원하지 않는 형식은 title 이 미리 그렇게 말한다",
    /const srcViewable = ATTACH_SOURCE_VIEWABLE_KINDS\.includes/.test(composerJs) &&
    /이 형식은 원문 보기를 지원하지 않습니다/.test(composerJs));
  // 프론트 사본이 서버 정본과 갈라지면 어포던스가 거짓말을 한다 — 두 집합을 대조해 잠근다.
  {
    const feKinds = (composerJs.match(/const ATTACH_SOURCE_VIEWABLE_KINDS = \[([^\]]*)\]/) || [])[1] || "";
    const beKinds = (storePy.match(/_VERSION_DIFF_TEXT_KINDS = \(([^)]*)\)/) || [])[1] || "";
    const norm = (t) => t.split(",").map((x) => x.trim().replace(/^["']|["']$/g, "")).filter(Boolean).sort().join(",");
    ok("D8c 프론트 kind 사본 == 서버 정본", norm(feKinds) && norm(feKinds) === norm(beKinds),
      `${norm(feKinds)} vs ${norm(beKinds)}`);
  }
  // 구버전 원문 경로 — docstring 이 "그 버전의 id 로 연다" 고 주장하므로 그 진입점이 실재해야 한다.
  ok("D8d 버전 이력 각 행에 그 버전 원문 진입점",
    /srcBtn\.className = "attach-list-version-src"/.test(composerJs) &&
    /openAttachmentSourceModal\(v\.id/.test(composerJs) &&
    /\.attach-list-version-src/.test(chatCss));
  // 휴지통(삭제된 첨부) 목록은 대상이 아니다 — 지운 파일을 여는 어포던스를 만들지 않는다.
  const trashStart = composerJs.indexOf("function _renderTrashAttachmentList");
  const trashFn = composerJs.slice(trashStart, trashStart + 3000);
  ok("D9 휴지통 목록에는 원문 진입점을 두지 않는다",
    trashStart > 0 && !/is-openable/.test(trashFn) && !/openAttachmentSourceModal/.test(trashFn));
}

// ── (E) 계약 ────────────────────────────────────────────────────────────────
console.log("\n[E] 계약");
{
  const specifiers = [...diffJs.matchAll(/from\s+"([^"]+)"/g)].map((m) => m[1]);
  ok("E1 모든 import specifier 에 ?v=dev",
    specifiers.length > 0 && specifiers.every((s) => s.includes("?v=dev")));
  ok("E2 배경 dismiss 는 저장소 단일 primitive", /bindBackdropDismiss\(backdrop, close\)/.test(diffJs));
  ok("E3 ESC 닫기 배선", (diffJs.match(/e\.key === "Escape"/g) || []).length >= 2);
  ok("E4 늦게 온 응답이 최신 선택을 덮지 않는다(seq 가드)",
    (diffJs.match(/if \(seq !== reqSeq\) return;/g) || []).length >= 3);
  // 렌더러 복제 0 — 원문 모달은 비교 모달의 identical 화면과 **같은 함수**를 쓴다.
  ok("E5 원문 렌더러는 하나뿐(`_renderSource`)",
    (diffJs.match(/function _renderSource\(/g) || []).length === 1 &&
    (diffJs.match(/_renderSource\(/g) || []).length >= 3);
  ok("E6 본문은 innerHTML 미사용(textContent 전용)",
    !/innerHTML/.test(M._renderSource.toString()));
  // 버전 파라미터 부재 계약 — 각 버전이 자기 id 를 가지므로 식별 경로를 둘로 만들지 않는다.
  ok("E7 프론트가 version 쿼리를 붙이지 않는다",
    !/source\?[^`"']*version=/.test(diffJs) && !/qs\.set\("version"/.test(diffJs));
  const srcFn = attachmentsPy.slice(attachmentsPy.indexOf("def get_attachment_source"),
    attachmentsPy.indexOf("def get_attachment_version_diff"));
  ok("E8 서버도 version 쿼리를 파싱하지 않는다",
    !/query_params\.get\("version"\)/.test(srcFn));
  // 본문 노출 게이트 — /diff 와 동형(신규 권한 코드 0).
  ok("E9 read.own/any 재사용(신규 권한 0)",
    /conversation\.attachment\.read\.own/.test(srcFn) && /conversation\.attachment\.read\.any/.test(srcFn));
  ok("E10 D21 pending 403 게이트", /_account_is_pending\(account\)/.test(srcFn) && /403/.test(srcFn));
  ok("E11 텍스트 kind 집합을 diff 와 공유", /_VERSION_DIFF_TEXT_KINDS/.test(srcFn));
  // 본문을 싣는 응답은 다운로드와 같은 저장 정책을 갖는다 — JSON 으로 감쌌다고 사라지면 안 된다.
  ok("E13 본문 응답에 no-store · nosniff 헤더",
    /"Cache-Control": "private, no-store"/.test(attachmentsPy) &&
    /"X-Content-Type-Options": "nosniff"/.test(attachmentsPy) &&
    (srcFn.match(/headers=_BODY_VIEW_HEADERS/g) || []).length >= 3);
  ok("E14 per-account rate limit(원클릭 트리거 + 클라 캐시 없음)",
    /RATE_SCOPE_ATTACHMENT_SOURCE/.test(srcFn) && /_search_rate_limit_check/.test(srcFn));
  ok("E15 ranged read 로 cap 만큼만 읽는다(전체 메모리 적재 금지)",
    /get_object_head_bytes\(object_key, max_bytes=cap\)/.test(srcFn) &&
    !/get_object_bytes\(/.test(srcFn));
  ok("E15b 절단 판정은 정본 크기로(ranged read 는 항상 cap 만큼 온다)",
    /source_truncated = int\(row\.get\("SizeBytes"\) or 0\) > cap/.test(srcFn));
  ok("E16 빈 ObjectKey 는 404(저장소 장애 503 으로 오분류 금지)",
    /if not object_key:/.test(srcFn) && /첨부 본문을 찾을 수 없습니다/.test(srcFn));
  ok("E17 except 는 storage 예외로 좁혀져 있다",
    /except \(storage_minio\.StorageConfigError, storage_minio\.StorageOperationError\)/.test(srcFn));
  ok("E18 절단된 앞부분의 줄 수를 전체로 말하지 않는다(lines_partial)",
    /lines_partial/.test(storePy) && /source_truncated=source_truncated/.test(srcFn) &&
    /lines_partial/.test(diffJs));
  for (const cls of [".attach-diff-panel", ".attach-diff-table", ".attach-diff-lineno",
    ".attach-diff-code", ".attach-diff-notice", ".attach-diff-meta", ".attach-diff-scroller"]) {
    ok(`E12 CSS 정의 존재 ${cls}`, chatCss.includes(cls));
  }
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
