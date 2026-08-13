// verify_attach_source_compare.mjs
// REQ-20260813-attach-source-compare — **문서 원문 화면에서의 버전 비교**.
//
// 사용자 요청 (2026-08-13):
//   ① "첨부파일의 '문서 원문' 화면에서도 버전 간 비교를 수행할 수 있도록 구성해주세요."
//   ② "추가로, 같은 버전이나 / 버전 간 변경사항이 없는 경우에는 문서 원문을 그대로 출력하도록
//      구성해주세요."
//   ③ "기본적인 '버전 비교' 버튼은 [가장 원본인 버전 -> 가장 최신의 버전] 으로 비교하여 출력."
//
// 종전: 원문 보기 모달은 **비교 진입점이 0** 이었고(그 계약이 docstring 에 명시돼 있었다), 비교
// 모달에서 같은 버전 두 개를 고르면 "서로 다른 두 버전을 선택하세요" 안내만 남아 **본문이 없는
// 화면**이었다. 내용이 동일한 쌍(`identical`)은 이미 원문을 출력하고 있었으므로, "비교할 것이
// 없다" 는 같은 사실에 두 화면이 서로 다르게 답하던 비대칭이다.
//
// 검증 6축:
//   (A) 선택기 — 체인 2개 이상이면 노출·기본값은 이 버전·1개면 숨김(거짓 어포던스 금지).
//   (B) 비교 전환 — 다른 버전 선택 시 `/diff` 를 부르고 방향을 **오래된 → 새로운** 으로 정규화.
//   (C) 원문으로 수렴 — 같은 버전(요청 0) · 내용 동일(identical) 두 경로가 같은 원문 화면.
//   (D) 컨트롤 — diff 전용 컨트롤이 비교 상태에서만 나타나고, 그릴 표가 있을 때만 활성.
//   (E) 비교 모달의 같은-버전 화면 — `/source` 를 그 버전 id 로 부르고 사유 배너를 함께 싣는다.
//   (F) 계약 — 왕복 1회 유지 · `?version=` 부재 · 렌더러/판정면 복제 0 · CSS `[hidden]` 봉인 ·
//       서버 payload 의 체인 요약.
//
// 실행: node verify_attach_source_compare.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
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

// **URL 별 응답 stub** — 이 화면은 한 모달 안에서 `/source` 와 `/diff` 를 모두 부른다. 단일 응답
// stub 으로는 "어느 요청에 어떤 답이 갔는지" 를 구분할 수 없어, 방향 정규화·재요청 0 같은 축이
// vacuous 하게 통과한다.
let ROUTES = {};       // 매칭 정규식/문자열 → { body, status }
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
  // 실 `apiFetch` 와 같은 계약: non-2xx 는 throw 하고 메시지는 payload.error 를 고른다.
  apiFetch: async (url) => {
    API_CALLS.push(url);
    const hit = Object.keys(ROUTES).find((k) => url.includes(k));
    if (!hit) {
      const err = new Error(`stub 미등록 경로: ${url}`);
      err.status = 599;
      throw err;
    }
    const { body, status } = ROUTES[hit];
    if ((status || 200) >= 400) {
      const err = new Error(body?.error || body?.detail || "Service Unavailable");
      err.status = status;
      err.payload = body;
      throw err;
    }
    return body;
  },
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage: CH.detectCodeLanguage,
  paintCodeInto: CH.paintCodeInto,
  codeLanguageLabel: CH.codeLanguageLabel,
};
const EXPORTS = ["openAttachmentSourceModal", "openAttachmentDiffModal"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));

const SRC_LINES = ["-- v3 본문", "SELECT id, name", "  FROM users;"];
const CHAIN = [
  { id: 10, version_number: 1, created_by_role: "user", created_at: "2026-08-10",
    size: 90, sha256: "sha1", kind: "text", original_filename: "f.sql", is_latest: false },
  { id: 11, version_number: 2, created_by_role: "assistant", created_at: "2026-08-11",
    size: 95, sha256: "sha2", kind: "text", original_filename: "f.sql", is_latest: false },
  { id: 12, version_number: 3, created_by_role: "user", created_at: "2026-08-12",
    size: 108, sha256: "sha3", kind: "text", original_filename: "f.sql", is_latest: true },
];
const srcResp = (over) => ({
  viewable: true,
  attachment_id: 12,
  root_attachment_id: 10,
  filename: "f.sql",
  version: CHAIN[2],
  versions: CHAIN,
  rows: SRC_LINES.map((t, i) => ({ type: "equal", right_no: i + 1, right: t })),
  stats: { lines: SRC_LINES.length },
  truncated: { source: false, rows: false },
  caps: { source_bytes: 1048576, rows: 6000 },
  ...(over || {}),
});
const diffResp = (over) => ({
  root_attachment_id: 10,
  filename: "f.sql",
  comparable: true,
  identical: false,
  from: CHAIN[0],
  to: CHAIN[2],
  rows: [
    { type: "equal", left_no: 1, right_no: 1, left: "-- v1 본문", right: "-- v1 본문" },
    { type: "replace", left_no: 2, right_no: 2, left: "SELECT id", right: "SELECT id, name" },
  ],
  stats: { added: 1, removed: 1, left_lines: 2, right_lines: 2 },
  truncated: {},
  caps: { source_bytes: 1048576, rows: 6000 },
  ...(over || {}),
});

const tick = () => new Promise((r) => setTimeout(r, 0));
const q = (bd, sel) => bd.querySelector(sel);

/** 원문 모달을 열고 첫 응답까지 기다린다. */
const openSource = async (routes, opts) => {
  ROUTES = routes; API_CALLS = [];
  for (const el of Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))) el.remove();
  M.openAttachmentSourceModal(12, opts || { filename: "f.sql" });
  await tick(); await tick();
  return window.document.querySelector(".attach-source-backdrop");
};

/** 비교 기준 select 를 바꾸고 응답까지 기다린다. */
const pick = async (bd, value) => {
  const sel = q(bd, ".attach-source-cmp");
  sel.value = String(value);
  sel.dispatchEvent(new window.Event("change"));
  await tick(); await tick();
  return bd;
};

// ── (A) 비교 기준 선택기 ─────────────────────────────────────────────────────
console.log("\n[A] 비교 기준 선택기");
{
  const bd = await openSource({ "/source": { body: srcResp() } });
  ok("A1 원문 모달이 열린다", !!bd);
  const wrap = q(bd, ".attach-source-cmpctl");
  const sel = q(bd, ".attach-source-cmp");
  ok("A2 선택기가 노출된다(체인 3개)", !!wrap && wrap.hidden === false);
  ok("A3 옵션 = 체인 전체", Array.from(sel.options).map((o) => o.value).join(",") === "1,2,3");
  // 기본값이 이 버전 = 기본 화면이 원문이라는 사실이 컨트롤에도 드러난다.
  ok("A4 기본 선택 = 이 버전(v3)", sel.value === "3");
  ok("A5 자기 자신 옵션에 '이 버전' 표기",
    /이 버전/.test(Array.from(sel.options).find((o) => o.value === "3").textContent));
  ok("A5b 다른 옵션에는 그 표기가 없다",
    !/이 버전/.test(Array.from(sel.options).find((o) => o.value === "1").textContent));
  // 라벨은 비교 모달과 같은 헬퍼(`_versionLabel`) — 역할·최신 표기가 두 화면에서 같다.
  ok("A6 라벨에 작성 주체가 실린다",
    /AI 수정/.test(Array.from(sel.options).find((o) => o.value === "2").textContent));
  ok("A7 기본 화면은 원문(제목·표)",
    /문서 원문/.test(q(bd, ".attach-source-titleword").textContent) &&
    !!q(bd, "table.attach-diff-table.is-source"));

  // 버전이 하나뿐인 첨부 — 이 모달의 원래 대상. 고를 것이 하나면 컨트롤을 두지 않는다.
  const solo = await openSource({ "/source": {
    body: srcResp({ versions: [CHAIN[2]], version: CHAIN[2] }) } });
  ok("A8 체인 1개면 선택기 숨김", q(solo, ".attach-source-cmpctl").hidden === true);
  // 서버가 아직 `versions` 를 주지 않는 구버전 응답에서도 종전 동작(선택기 없음)이어야 한다.
  const legacy = await openSource({ "/source": { body: (() => {
    const r = srcResp(); delete r.versions; return r; })() } });
  ok("A9 versions 부재(구버전 응답)면 숨김 — 하위호환",
    q(legacy, ".attach-source-cmpctl").hidden === true);
  ok("A9b 그래도 원문은 그대로 렌더된다",
    !!q(legacy, "table.attach-diff-table.is-source"));
  // CSS 트랩: `.attach-diff-ctl{display:inline-flex}` 를 물려받으므로 `[hidden]` 이 먹지 않는다.
  ok("A10 [hidden] override 규칙이 CSS 에 있다(숨김이 실제로 먹는다)",
    /\.attach-source-cmpctl\[hidden\][\s\S]{0,80}display:\s*none/.test(chatCss));
}

// ── (B) 비교 전환 ───────────────────────────────────────────────────────────
console.log("\n[B] 비교 전환 (요청 ①)");
{
  const bd = await openSource({ "/source": { body: srcResp() }, "/diff": { body: diffResp() } });
  const before = API_CALLS.length;
  await pick(bd, 1);
  const diffCalls = API_CALLS.slice(before).filter((u) => u.includes("/diff"));
  ok("B1 다른 버전을 고르면 /diff 를 부른다", diffCalls.length === 1, API_CALLS.join(" | "));
  ok("B2 대상은 이 첨부 id", /\/api\/attachments\/12\/diff\?/.test(diffCalls[0] || ""));
  ok("B3 쌍은 from=1 to=3", /from_version=1/.test(diffCalls[0] || "") && /to_version=3/.test(diffCalls[0] || ""),
    diffCalls[0]);
  ok("B4 diff 표가 렌더된다(원문 표 아님)",
    !!q(bd, "table.attach-diff-table.is-split") && !q(bd, "table.is-source"));
  ok("B5 제목이 비교로 바뀐다", /버전 비교/.test(q(bd, ".attach-source-titleword").textContent));
  ok("B5b 제목 태그가 쌍을 밝힌다(v1 → v3)",
    /v1 → v3/.test(q(bd, ".attach-source-vertag").textContent),
    q(bd, ".attach-source-vertag").textContent);
  ok("B6 통계가 증감으로 바뀐다", /\+1 \/ -1/.test(q(bd, ".attach-diff-stats").textContent),
    q(bd, ".attach-diff-stats").textContent);

  // 방향 정규화 — 이 모달의 버전이 v3 인데 기준으로 더 **오래된** v1 을 골라도, 반대로 v1
  // 모달에서 v3 을 골라도 같은 쌍은 같은 방향(오래된 → 새로운)으로 요청돼야 한다. 그렇지
  // 않으면 같은 두 버전이 진입 경로에 따라 좌우가 뒤집혀 보인다.
  const older = await openSource({
    "/source": { body: srcResp({ attachment_id: 10, version: CHAIN[0] }) },
    "/diff": { body: diffResp() },
  });
  const mark = API_CALLS.length;
  await pick(older, 3);
  const call = API_CALLS.slice(mark).find((u) => u.includes("/diff")) || "";
  ok("B7 v1 화면에서 v3 을 골라도 from=1 to=3 (방향 정규화)",
    /from_version=1/.test(call) && /to_version=3/.test(call), call);
}

// ── (C) 원문으로 수렴 (요청 ②) ───────────────────────────────────────────────
console.log("\n[C] 같은 버전 · 변경 없음 → 원문 그대로 (요청 ②)");
{
  const bd = await openSource({ "/source": { body: srcResp() }, "/diff": { body: diffResp() } });
  await pick(bd, 1);
  ok("C0 전제 — 지금은 비교 화면", !!q(bd, "table.is-split"));
  const before = API_CALLS.length;
  await pick(bd, 3);   // 이 버전 = 같은 버전
  ok("C1 같은 버전을 고르면 원문 표로 돌아온다",
    !!q(bd, "table.attach-diff-table.is-source") && !q(bd, "table.is-split"));
  ok("C2 그 전환은 **재요청 0**(이미 받아 둔 원문 재사용)",
    API_CALLS.length === before, API_CALLS.slice(before).join(" | "));
  ok("C3 제목도 원문으로 되돌아온다",
    /문서 원문/.test(q(bd, ".attach-source-titleword").textContent));
  ok("C4 통계도 원문 기준(줄 수·크기)",
    /3줄/.test(q(bd, ".attach-diff-stats").textContent),
    q(bd, ".attach-diff-stats").textContent);
  const cells = Array.from(bd.querySelectorAll("table.is-source tr.attach-diff-row td:nth-child(2)"));
  ok("C5 원문 무손실", cells.map((c) => c.textContent).join("\n") === SRC_LINES.join("\n"));

  // 내용이 동일한 쌍 — 서버가 `identical` 로 답하고 `_renderBody` 가 원문을 그린다(선행 계약).
  // 원문 화면의 비교도 같은 렌더 경로를 타는지 확인한다: 두 경로가 같은 화면으로 수렴해야
  // "비교할 것이 없다" 는 한 사실에 화면이 둘이 되지 않는다.
  const same = await openSource({
    "/source": { body: srcResp() },
    "/diff": { body: diffResp({
      identical: true,
      rows: SRC_LINES.map((t, i) => ({ type: "equal", left_no: i + 1, right_no: i + 1, left: t, right: t })),
      stats: { added: 0, removed: 0, left_lines: 3, right_lines: 3 },
      from: CHAIN[1], to: CHAIN[2],
    }) },
  });
  await pick(same, 2);
  ok("C6 변경사항이 없으면 원문 표를 그린다",
    !!q(same, "table.attach-diff-table.is-source") && !q(same, "table.is-split"));
  // 배너의 **단정 강도**가 근거에 맞는지까지 본다(`_identicalFlags` — 선행 계약). 위 fixture 는
  // 두 버전의 sha256 이 다르므로(줄 비교는 CRLF·마지막 개행을 흡수한다) "완전히 동일" 이라고
  // 말해서는 안 된다 — 그 차이는 사용자에게 실재하고 크기·해시로 드러난다.
  ok("C7 그 사실을 배너로 알린다(빈 화면 금지)",
    /줄 내용은 같지만 두 파일이 완전히 동일하지는 않습니다/.test(same.textContent),
    same.textContent.slice(0, 160));
  const sameSha = await openSource({
    "/source": { body: srcResp() },
    "/diff": { body: diffResp({
      identical: true,
      rows: SRC_LINES.map((t, i) => ({ type: "equal", left_no: i + 1, right_no: i + 1, left: t, right: t })),
      stats: { added: 0, removed: 0, left_lines: 3, right_lines: 3 },
      from: { ...CHAIN[1], sha256: "shaX" }, to: { ...CHAIN[2], sha256: "shaX" },
    }) },
  });
  await pick(sameSha, 2);
  ok("C7b 해시까지 같으면 단정을 낮추지 않는다('내용이 동일합니다')",
    /두 버전의 내용이 동일합니다/.test(sameSha.textContent) &&
    /문서 원문/.test(sameSha.textContent),
    sameSha.textContent.slice(0, 160));
  ok("C7c 그 화면의 통계는 '차이 없음 — 원문 표시'",
    /차이 없음 — 원문 표시/.test(q(sameSha, ".attach-diff-stats").textContent),
    q(sameSha, ".attach-diff-stats").textContent);
  ok("C8 통계도 '차이 없음' 으로 말한다",
    /차이 없음/.test(q(same, ".attach-diff-stats").textContent),
    q(same, ".attach-diff-stats").textContent);
  const sameCells = Array.from(same.querySelectorAll("table.is-source tr.attach-diff-row td:nth-child(2)"));
  ok("C9 그 화면의 본문도 원문 무손실",
    sameCells.map((c) => c.textContent).join("\n") === SRC_LINES.join("\n"));
}

// ── (D) 컨트롤 상태 ─────────────────────────────────────────────────────────
console.log("\n[D] diff 전용 컨트롤 · 토글");
{
  const bd = await openSource({ "/source": { body: srcResp() }, "/diff": { body: diffResp() } });
  ok("D1 원문 화면에서는 보기 방식·맥락 토글이 없다(쓸 수 없는 컨트롤 상시 노출 금지)",
    q(bd, ".attach-diff-viewtoggle").hidden === true &&
    q(bd, ".attach-diff-ctxtoggle").hidden === true);
  await pick(bd, 1);
  ok("D2 비교 화면에서 나타난다",
    q(bd, ".attach-diff-viewtoggle").hidden === false &&
    q(bd, ".attach-diff-ctxtoggle").hidden === false);
  ok("D3 그릴 표가 있으니 활성",
    Array.from(bd.querySelectorAll(".attach-diff-mode")).every((b) => b.disabled === false) &&
    q(bd, ".attach-diff-ctxfull").disabled === false);
  // 단일열 전환은 같은 응답의 다른 표현 — 재요청하지 않는다.
  const before = API_CALLS.length;
  bd.querySelector('.attach-diff-mode[data-mode="unified"]').dispatchEvent(new window.Event("click"));
  await tick();
  ok("D4 단일열 전환이 재요청 없이 렌더된다",
    !!q(bd, "table.attach-diff-table.is-unified") && API_CALLS.length === before);
  ok("D4b 보기 방식이 비교 모달과 같은 키로 저장된다", HL_STORE.attachDiffViewMode === "unified");
  // 맥락 토글은 서버가 축약을 계산하므로 재요청이 필요하다(프론트 재구현 금지).
  const mark = API_CALLS.length;
  const ctx = q(bd, ".attach-diff-ctxfull");
  ctx.checked = true;
  ctx.dispatchEvent(new window.Event("change"));
  await tick(); await tick();
  const ctxCall = API_CALLS.slice(mark).find((u) => u.includes("/diff")) || "";
  ok("D5 맥락 토글은 같은 쌍을 context=full 로 재요청",
    /context=full/.test(ctxCall) && /from_version=1/.test(ctxCall) && /to_version=3/.test(ctxCall),
    ctxCall);
  HL_STORE = {};

  // 내용 동일 화면은 그릴 diff 표가 없다 → 컨트롤은 보이되 비활성(비교 모달과 같은 사유).
  const same = await openSource({
    "/source": { body: srcResp() },
    "/diff": { body: diffResp({ identical: true, stats: { added: 0, removed: 0, right_lines: 3 },
      rows: SRC_LINES.map((t, i) => ({ type: "equal", left_no: i + 1, right_no: i + 1, left: t, right: t })) }) },
  });
  await pick(same, 1);
  ok("D6 변경 없음 화면의 diff 전용 컨트롤은 비활성",
    Array.from(same.querySelectorAll(".attach-diff-mode")).every((b) => b.disabled === true) &&
    q(same, ".attach-diff-ctxfull").disabled === true);
  ok("D6b 비활성 사유가 title 로 전달된다",
    /차이가 없는 화면/.test(q(same, ".attach-diff-ctxtoggle").title),
    q(same, ".attach-diff-ctxtoggle").title);
  // 구문 색 토글은 원문·비교 양쪽에서 살아 있어야 한다(칠할 본문이 있는 화면이므로).
  ok("D7 변경 없음 화면에서도 구문 색 토글은 노출(원문도 칠할 본문이다)",
    q(same, ".attach-diff-hltoggle").hidden === false);

  // 비교 실패(예: 서버 오류) — 사유가 화면에 도달하고, 조용한 빈 화면이 되지 않는다.
  const failing = await openSource({
    "/source": { body: srcResp() },
    "/diff": { body: { error: "원본 파일을 읽을 수 없어 내용을 비교하지 못했습니다." }, status: 503 },
  });
  await pick(failing, 1);
  ok("D8 비교 실패 사유가 화면에 도달한다",
    /원본 파일을 읽을 수 없어/.test(failing.textContent));
  ok("D8b 실패 화면에 diff 표도 원문 표도 없다(거짓 본문 금지)",
    !q(failing, "table.attach-diff-table"));
  ok("D8c 실패 시 통계는 비운다(직전 값 잔존 금지)",
    q(failing, ".attach-diff-stats").textContent === "");
}

// ── (E) 비교 모달의 같은-버전 화면 (요청 ②의 다른 절반) ──────────────────────
console.log("\n[E] 비교 모달 — 같은 버전 두 개 선택");
{
  const versions = CHAIN.map((v) => ({
    id: v.id, version_number: v.version_number, original_filename: "f.sql",
    created_by_role: v.created_by_role, is_assistant_generated: v.created_by_role === "assistant",
    superseded: !v.is_latest, created_at: v.created_at,
  }));
  const openDiffModal = async (routes, preselect) => {
    ROUTES = routes; API_CALLS = [];
    for (const el of Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))) el.remove();
    M.openAttachmentDiffModal(12, versions, preselect);
    await tick(); await tick();
    return Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))
      .find((b) => !b.classList.contains("attach-source-backdrop"));
  };
  const bd = await openDiffModal({
    "/diff": { body: diffResp() },
    "/api/attachments/11/source": { body: srcResp({ attachment_id: 11, version: CHAIN[1] }) },
  });
  ok("E1 비교 모달이 열린다", !!bd && !!q(bd, ".attach-diff-from"));
  // 같은 버전 두 개를 고른다 — 종전에는 안내문만 남는 화면이었다.
  const mark = API_CALLS.length;
  q(bd, ".attach-diff-from").value = "2";
  q(bd, ".attach-diff-to").value = "2";
  q(bd, ".attach-diff-to").dispatchEvent(new window.Event("change"));
  await tick(); await tick();
  const srcCall = API_CALLS.slice(mark).find((u) => u.includes("/source")) || "";
  ok("E2 그 버전의 id 로 /source 를 부른다(체인 id — 경로 하나로 버전 특정)",
    /\/api\/attachments\/11\/source$/.test(srcCall), srcCall);
  ok("E3 /diff 를 from==to 로 부르지 않는다(400 계약 유지)",
    !API_CALLS.slice(mark).some((u) => /from_version=2&to_version=2/.test(u)));
  ok("E4 원문 표가 렌더된다", !!q(bd, "table.attach-diff-table.is-source"));
  ok("E5 종전 안내문은 사라졌다(본문 없는 화면 금지)",
    !/서로 다른 두 버전을 선택하세요/.test(bd.textContent));
  ok("E6 같은 버전을 골랐다는 사실을 배너로 알린다(제목은 여전히 '버전 비교')",
    /같은 버전을 선택했습니다/.test(bd.textContent) && /v2 원문/.test(bd.textContent),
    bd.textContent.slice(0, 140));
  ok("E7 통계는 원문 기준", /3줄/.test(q(bd, ".attach-diff-stats").textContent),
    q(bd, ".attach-diff-stats").textContent);
  // 재렌더(토글 조작)에도 배너가 유지되어야 한다 — 한 번만 append 하면 다음 렌더에서 사라진다.
  const hl = q(bd, ".attach-diff-hl");
  hl.checked = !hl.checked;
  hl.dispatchEvent(new window.Event("change"));
  await tick();
  ok("E8 배너가 재렌더에도 유지된다(렌더 옵션에 담김)",
    /같은 버전을 선택했습니다/.test(bd.textContent));
  ok("E9 재렌더 후에도 원문 표", !!q(bd, "table.is-source"));
  // 체인 payload 에 id 가 없는 구버전 형식 — 조용히 빈 화면을 주지 않는다.
  const noId = await (async () => {
    ROUTES = { "/diff": { body: diffResp() } }; API_CALLS = [];
    for (const el of Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))) el.remove();
    M.openAttachmentDiffModal(12, versions.map((v) => ({ ...v, id: undefined })));
    await tick(); await tick();
    const b = Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))
      .find((x) => !x.classList.contains("attach-source-backdrop"));
    b.querySelector(".attach-diff-from").value = "2";
    b.querySelector(".attach-diff-to").value = "2";
    b.querySelector(".attach-diff-to").dispatchEvent(new window.Event("change"));
    await tick(); await tick();
    return b;
  })();
  ok("E10 id 부재 시 사유를 알린다", /원문을 찾지 못했습니다/.test(noId.textContent));
}

// ── (F) 계약 ────────────────────────────────────────────────────────────────
console.log("\n[F] 계약");
{
  // 왕복 1회 — 체인 요약을 `/source` 가 함께 주므로 `/versions` 를 부르지 않는다.
  const bd = await openSource({ "/source": { body: srcResp() } });
  ok("F1 모달 진입 요청은 /source 한 번뿐",
    API_CALLS.length === 1 && /\/api\/attachments\/12\/source$/.test(API_CALLS[0]),
    API_CALLS.join(" | "));
  ok("F1b /versions 를 부르지 않는다", !API_CALLS.some((u) => u.includes("/versions")));
  ok("F2 서버가 체인 요약을 싣는다", /payload\["versions"\] = \[/.test(attachmentsPy));
  ok("F2b 체인 조회 실패는 비교만 없애고 원문은 준다(fail-soft)",
    /except Exception:[\s\S]{0,320}payload\["versions"\] = \[\]/.test(attachmentsPy));
  ok("F3 버전 요약 형식은 단일 정본(`_version_side`)",
    (attachmentsPy.match(/def _version_side\(/g) || []).length === 1 &&
    (attachmentsPy.match(/_version_side\(/g) || []).length >= 4);
  // 종전 계약 유지 — 식별 경로를 둘로 만들지 않는다.
  ok("F4 프론트가 /source 에 version 쿼리를 붙이지 않는다",
    !/source\?[^`"']*version=/.test(diffJs) && !/qs\.set\("version"/.test(diffJs));
  const srcFn = attachmentsPy.slice(attachmentsPy.indexOf("def get_attachment_source"),
    attachmentsPy.indexOf("def get_attachment_version_diff"));
  ok("F4b 서버도 version 쿼리를 파싱하지 않는다", !/query_params\.get\("version"\)/.test(srcFn));
  ok("F5 서버 /diff 의 from==to 400 계약은 그대로",
    /if from_version == to_version:/.test(attachmentsPy) &&
    /서로 다른 두 버전을 지정해야 합니다\./.test(attachmentsPy));
  // 렌더러·판정면 복제 0 — 이 저장소가 반복 관측한 "규칙 두 벌" 결함 기전의 봉인.
  ok("F6 원문 표 렌더러는 하나뿐(`_renderSource`)",
    (diffJs.match(/function _renderSource\(/g) || []).length === 1);
  ok("F6b 원문 화면 렌더러도 하나뿐(`_renderSourceBody`) — 두 모달이 공유",
    (diffJs.match(/function _renderSourceBody\(/g) || []).length === 1 &&
    (diffJs.match(/_renderSourceBody\(/g) || []).length >= 3);
  ok("F7 본문 상태 판정면은 하나뿐(`_bodyState`)",
    (diffJs.match(/function _bodyState\(/g) || []).length === 1 &&
    (diffJs.match(/_bodyState\(/g) || []).length >= 5);
  ok("F8 통계 문구도 공용(`_sourceStatsText`·`_diffStatsText`)",
    (diffJs.match(/function _sourceStatsText\(/g) || []).length === 1 &&
    (diffJs.match(/function _diffStatsText\(/g) || []).length === 1 &&
    (diffJs.match(/_sourceStatsText\(/g) || []).length >= 3 &&
    (diffJs.match(/_diffStatsText\(/g) || []).length >= 3);
  ok("F9 마크다운 배너 문구도 공용(두 화면이 같은 말)",
    (diffJs.match(/function _mdBlockedNotice\(/g) || []).length === 1 &&
    (diffJs.match(/_mdBlockedNotice\(/g) || []).length >= 3);
  ok("F10 ESM specifier 에 ?v=dev(모듈 이중 인스턴스 방지)",
    [...diffJs.matchAll(/from\s+"([^"]+)"/g)].map((m) => m[1]).every((s) => s.includes("?v=dev")));
  ok("F11 늦게 온 응답이 최신 선택을 덮지 않는다(seq 가드)",
    (diffJs.match(/if \(seq(?:Src)? !== reqSeq\) return;/g) || []).length >= 5);

  // 요청 ③ — 머리 진입점의 기본 쌍(정본 축은 verify_attach_version_diff B5, 여기서는 교차 확인).
  ok("F12 목록의 '버전 비교' 버튼은 최초 → 최신을 사전선택",
    /oldestNum === latestNum \? undefined : \{ from: oldestNum, to: latestNum \}/.test(composerJs));
  ok("F12b 그 사실이 title 로도 드러난다",
    /v\$\{oldestNum\}\(최초\) ↔ v\$\{latestNum\}\(최신\) 비교/.test(composerJs));
  ok("F13 각 버전 행의 ⇄ 는 그대로 '그 버전 ↔ 최신'(두 진입점의 역할 분리)",
    /openAttachmentDiffModal\(attachmentId, versions, \{ from: vnum, to: latestNum \}\)/.test(composerJs));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
