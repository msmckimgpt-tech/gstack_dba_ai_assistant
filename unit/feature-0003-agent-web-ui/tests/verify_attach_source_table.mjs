// verify_attach_source_table.mjs
// REQ-20260909-attach-csv-table — 첨부 `.csv`/`.tsv` 를 **표(격자)로** 렌더.
//
// 사용자 요청(2026-09-09): "DQA클라이언트 첨부파일 중, csv 확장자가 표 형태로 출력될 수 있도록
// 구성해주세요." — 종전에는 CSV 첨부를 열면 쉼표가 섞인 평문 줄 표가 나왔다(구문 색으로 구분자만
// 강조). 요청은 "구분자를 눈에 띄게" 가 아니라 "표로 보여 달라" 다.
//
// 검증 축:
//   (A) 파서 계약 — RFC 4180: 인용 필드·`""` 이스케이프·필드 안 구분자/개행·CRLF·BOM·빈 필드.
//       **깨진 입력에서도 값을 버리지 않는다**(짝 없는 따옴표, 인용 중간에서 끊긴 절단본) —
//       이 화면에는 서버가 앞부분만 잘라 보낸 본문이 실제로 도착한다.
//   (B) 무손실 왕복 — 파싱 결과를 다시 직렬화하면 원문과 필드 단위로 같다.
//   (C) 토글 판정 — `.csv`/`.tsv` 에서만, 그리고 **그릴 본문이 실제로 왔을 때만** 노출.
//       (이 모듈이 반복해 봉인한 «거짓 어포던스» 축 — 마크다운 토글과 같은 계약.)
//   (D) 렌더 구조 — 실제 모달을 몰아 `<table>`/`<thead>`/`<tbody>` 와 셀 값·행 번호를 단정한다.
//       스텁이 아니라 **정본 모듈**을 구동한다(렌더러 배선이 끊겨도 "함수가 있다" 는 통과한다).
//   (E) XSS — 셀 값의 `<script>`·`<img onerror>`·`javascript:` 가 **요소가 되지 않는다**.
//       (표 렌더는 `textContent` 만 쓰므로 구조적으로 안전해야 하고, 그 사실을 여기서 잠근다.)
//   (F) 원문 복귀 — 토글을 끄면 종전 줄 표로 돌아오고 내용은 byte 무손실. 선택은 영속된다.
//   (G) 상한 — 열/셀 상한 초과 시 조용히 자르지 않고 배너로 알린다(§16.7 G9-b).
//   (H) 배타 — `.md` 에는 표 토글이 없고, **변경이 있는 비교 화면**에도 없다(줄 대조 보존).
//       표를 보는 동안 구문 색 토글은 숨는다(칠할 원문 줄이 화면에 없다).
//   (I) CSS 계약 — sticky 머리글·`[hidden]` 강제가 스타일시트에 실재한다(jsdom 이 못 보는 축).
//
// 실행: node verify_attach_source_table.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인(정렬·간격·머리글 고정)은 PB-0009 실 DQA 클라이언트 — jsdom 은 픽셀을 못 본다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
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

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "https://app.local/" });
const { window } = dom;

// ── 정본 모듈 로드 ───────────────────────────────────────────────────────────
// 마크다운 하네스와 같은 관용구 — import 를 벗기고 정본 본문을 그대로 평가한다. 파서를 하네스에
// 복제하지 않는 것이 요점이다(복제하면 이 하네스는 자기 사본을 시험하게 된다).
const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/gm, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존"); process.exit(2); }

const CH_SRC = read("code-highlight.js").replace(/^export\s+/gm, "");
const CH = new Function(`${CH_SRC}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();

let API_RESPONSE = {};
let API_STATUS = 200;
let STORE = {};
const mkStubs = () => ({
  document: window.document,
  window,
  localStorage: {
    getItem: (k) => (k in STORE ? STORE[k] : null),
    setItem: (k, v) => { STORE[k] = String(v); },
    removeItem: (k) => { delete STORE[k]; },
  },
  requestAnimationFrame: (fn) => fn(),
  apiFetch: async () => {
    if (API_STATUS >= 400) {
      const err = new Error(API_RESPONSE.error || "Service Unavailable");
      err.status = API_STATUS;
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
  // 표 경로는 마크다운 파이프라인을 타지 않는다 — 이 스텁이 호출되면 그 자체가 결함 신호다.
  markdownToHtml: () => { MD_CALLS += 1; return "<p>md</p>"; },
});
let MD_CALLS = 0;
const EXPORTS = ["openAttachmentSourceModal", "openAttachmentDiffModal", "parseDelimitedText"];
const mkModule = () => {
  const s = mkStubs();
  return new Function(...Object.keys(s), `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(s));
};
const M = mkModule();
for (const n of EXPORTS) ok(`S1 로드됨 ${n}`, typeof M[n] === "function");
ok("S2 표 렌더 상한이 정본에 선언돼 있다", /TABLE_COL_CAP\s*=\s*\d+/.test(diffJs) && /TABLE_CELL_CAP\s*=\s*\d+/.test(diffJs));

const P = M.parseDelimitedText;

// ── (A) 파서 계약 ────────────────────────────────────────────────────────────
console.log("\n[A] RFC 4180 파서 계약");
{
  const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  ok("A1 단순 행/열", eq(P("a,b\nc,d", ","), [["a", "b"], ["c", "d"]]), JSON.stringify(P("a,b\nc,d", ",")));
  ok("A2 마지막 개행은 빈 행을 만들지 않는다", eq(P("a,b\n", ","), [["a", "b"]]), JSON.stringify(P("a,b\n", ",")));
  ok("A3 빈 필드 보존", eq(P("a,,c", ","), [["a", "", "c"]]));
  ok("A4 인용 필드 안의 구분자는 경계가 아니다",
    eq(P('a,"b,c",d', ","), [["a", "b,c", "d"]]), JSON.stringify(P('a,"b,c",d', ",")));
  ok("A5 `\"\"` 는 따옴표 한 글자", eq(P('"a""b"', ","), [['a"b']]), JSON.stringify(P('"a""b"', ",")));
  ok("A6 인용 필드 안의 개행은 행을 나누지 않는다",
    eq(P('"a\nb",c', ","), [["a\nb", "c"]]), JSON.stringify(P('"a\nb",c', ",")));
  ok("A7 CRLF 를 행 구분으로 인식(빈 필드가 생기지 않는다)",
    eq(P("a,b\r\nc,d", ","), [["a", "b"], ["c", "d"]]), JSON.stringify(P("a,b\r\nc,d", ",")));
  ok("A8 BOM 제거 (남으면 첫 머리글이 보이지 않는 글자로 시작한다)",
    eq(P("﻿id,name", ","), [["id", "name"]]), JSON.stringify(P("﻿id,name", ",")));
  ok("A9 TSV 구분자", eq(P("a\tb\nc\td", "\t"), [["a", "b"], ["c", "d"]]));
  ok("A10 행마다 열 수가 달라도 그대로 보존", eq(P("a,b,c\nd", ","), [["a", "b", "c"], ["d"]]));
  // 무손실 축 — 여기서 값이 사라지면 사용자는 "잘렸다" 는 배너만 보고 **무엇이** 사라졌는지 모른다.
  ok("A11 짝 없는 따옴표로 끝난 절단본도 값을 버리지 않는다",
    eq(P('a,"bc', ","), [["a", "bc"]]), JSON.stringify(P('a,"bc', ",")));
  ok("A12 필드 중간의 따옴표는 리터럴 (열이 밀리지 않는다)",
    eq(P('a"b,c', ","), [['a"b', "c"]]), JSON.stringify(P('a"b,c', ",")));
  ok("A13 빈 입력", eq(P("", ","), [[""]]), JSON.stringify(P("", ",")));
  ok("A14 빈 줄은 빈 레코드로 보존", eq(P("a\n\nb", ","), [["a"], [""], ["b"]]), JSON.stringify(P("a\n\nb", ",")));

  // codex 적대 리뷰 [P1] — 「마지막 레코드가 빈 필드 하나」로 꼬리를 판정하면 **명시적 빈 인용
  // 필드**가 통째로 사라지고, 화면이 "데이터 행은 없습니다" 라고 거짓을 말한다.
  ok("A15 명시적 빈 인용 필드 행은 꼬리가 아니다 (`h⏎\"\"`)",
    eq(P('h\n""', ","), [["h"], [""]]), JSON.stringify(P('h\n""', ",")));
  ok("A15b 그래도 개행으로 끝난 정상 CSV 에는 빈 행이 붙지 않는다",
    eq(P('h\n""\n', ","), [["h"], [""]]), JSON.stringify(P('h\n""\n', ",")));
  ok("A15c 단독 빈 인용 필드", eq(P('""', ","), [[""]]), JSON.stringify(P('""', ",")));
  ok("A15d 마지막 줄이 CRLF 로 끝나도 꼬리가 생기지 않는다",
    eq(P("a,b\r\n", ","), [["a", "b"]]), JSON.stringify(P("a,b\r\n", ",")));

  // codex 적대 리뷰 [P1] — 표준 파서는 `"a"b` 를 조용히 `ab` 로 읽는다. 값은 그대로 두되
  // **변형된 사실을 신고**해야 사용자가 원문 보기로 확인할 수 있다.
  const an = {};
  ok("A16 닫힌 인용 뒤 문자는 형식 이상으로 신고된다",
    eq(P('"a"b,c', ",", an), [["ab", "c"]]) && an.quoteAnomalies === 1,
    `${JSON.stringify(P('"a"b,c', ","))} anomalies=${an.quoteAnomalies}`);
  const an2 = {};
  P('a,"bc', ",", an2);
  ok("A16b 닫히지 않은 인용(절단본)도 신고된다", an2.quoteAnomalies === 1, String(an2.quoteAnomalies));
  const an3 = {};
  P('a,"b,c",d\n"x""y",z', ",", an3);
  ok("A16c 정상 인용은 신고하지 않는다 (거짓 경고 금지)", an3.quoteAnomalies === 0, String(an3.quoteAnomalies));
  const an4 = {};
  P("id,name\n1,홍길동", ",", an4);
  ok("A16d 인용이 없는 평범한 CSV 도 신고 0", an4.quoteAnomalies === 0, String(an4.quoteAnomalies));
  // codex 확인 라운드 [P2] — CRLF 스킵을 `endField()` 보다 먼저 하면 `i` 가 한 칸 앞서 있어
  // **정상** 인용 필드가 형식 이상으로 신고된다(정상 CSV 에 거짓 경고).
  const an5 = {};
  const r5 = P('"a"\r\n"b",c\r\n', ",", an5);
  ok("A16e CRLF 로 끝나는 정상 인용 필드는 신고 0 (거짓 경고 금지)",
    an5.quoteAnomalies === 0 && JSON.stringify(r5) === JSON.stringify([["a"], ["b", "c"]]),
    `${JSON.stringify(r5)} anomalies=${an5.quoteAnomalies}`);
  const an6 = {};
  P('"a"x\r\nb', ",", an6);
  ok("A16f 그래도 CRLF 앞의 진짜 형식 이상은 신고된다", an6.quoteAnomalies === 1, String(an6.quoteAnomalies));
}

// ── (B) 무손실 왕복 ──────────────────────────────────────────────────────────
console.log("\n[B] 무손실 왕복 (파싱 → 재직렬화)");
{
  const ser = (recs) => recs.map((r) => r.map((f) => (
    /[",\n]/.test(f) ? `"${f.replace(/"/g, '""')}"` : f)).join(",")).join("\n");
  const samples = [
    "id,name,note\n1,홍길동,\"줄이\n둘\"\n2,\"쉼표, 포함\",-",
    "a,b\nc,d\n",
    '"","x"',
    "단일열\n값1\n값2",
  ];
  let bad = null;
  for (const s of samples) {
    const once = P(s, ",");
    const twice = P(ser(once), ",");
    if (JSON.stringify(once) !== JSON.stringify(twice)) { bad = s; break; }
  }
  ok("B1 파싱은 멱등이다 (재직렬화 후 다시 파싱해도 같은 레코드)", bad === null, bad);
  const recs = P("id,name\n1,\"쉼표, 포함\"\n2,\"줄\n바꿈\"", ",");
  const flat = recs.flat().join(" ");
  ok("B2 모든 필드 값이 살아 있다",
    flat.includes("쉼표, 포함") && flat.includes("줄\n바꿈") && flat.includes("id") && flat.includes("name"),
    flat.slice(0, 120));
}

// ── 모달 구동 도우미 ─────────────────────────────────────────────────────────
const mkRows = (lines) => lines.map((t, i) => ({ type: "equal", left_no: i + 1, left: t, right_no: i + 1, right: t }));
const mkResp = (filename, lines, extra) => ({
  viewable: true,
  attachment_id: 11,
  filename,
  version: { version_number: 1, size: 256, is_latest: true },
  stats: { lines: lines.length },
  caps: { source_bytes: 1048576, rows: 6000 },
  truncated: {},
  rows: mkRows(lines),
  ...(extra || {}),
});
const tick = () => new Promise((r) => setTimeout(r, 0));
const openSource = async (resp, opts) => {
  window.document.body.innerHTML = "";
  API_RESPONSE = resp; API_STATUS = 200;
  const mod = mkModule();
  mod.openAttachmentSourceModal(11, opts || { filename: resp.filename });
  await tick(); await tick();
  return window.document;
};

const CSV_LINES = ["id,name,amount", "1,홍길동,1200", "2,\"쉼표, 포함\",30.5", "3,,0"];
const CSV_RESP = mkResp("orders.csv", CSV_LINES);

// ── (C) 토글 판정 ────────────────────────────────────────────────────────────
console.log("\n[C] 표 토글 노출 판정 (거짓 어포던스 금지)");
{
  let doc = await openSource(CSV_RESP);
  const wrap = doc.querySelector(".attach-source-tabletoggle");
  ok("C1 `.csv` 첨부는 표 토글 노출", !!wrap && wrap.hidden === false);
  ok("C2 기본은 켬 (요청: 표 형태로 출력)",
    doc.querySelector(".attach-source-table-cb").checked === true);
  ok("C3 표를 보는 동안 구문 색 토글은 숨김",
    doc.querySelector(".attach-diff-hltoggle").hidden === true);

  doc = await openSource(mkResp("rows.tsv", ["id\tname", "1\t홍길동"]));
  ok("C4 `.tsv` 도 같은 토글", doc.querySelector(".attach-source-tabletoggle").hidden === false);
  // 토글 노출만 보면 **구분자가 틀려도 통과**한다 — 탭 파일을 쉼표로 가르면 전부 한 열이 된다.
  // 그래서 실제 셀 분할까지 단정한다(구분자가 렌더까지 도달하는지가 이 축의 요점).
  {
    const tsvTh = Array.from(doc.querySelectorAll("table.attach-source-table thead th")).map((e) => e.textContent);
    const tsvTd = Array.from(doc.querySelectorAll("table.attach-source-table tbody td")).map((e) => e.textContent);
    ok("C4b `.tsv` 는 탭으로 갈린다 (구분자가 렌더까지 도달)",
      JSON.stringify(tsvTh) === JSON.stringify(["#", "id", "name"])
      && JSON.stringify(tsvTd) === JSON.stringify(["2", "1", "홍길동"]),
      `${JSON.stringify(tsvTh)} / ${JSON.stringify(tsvTd)}`);
  }

  doc = await openSource(mkResp("schema.sql", ["SELECT 1;"]));
  ok("C5 `.sql` 첨부에는 표 토글 없음",
    doc.querySelector(".attach-source-tabletoggle").hidden === true);
  ok("C5b 그 화면의 구문 색 토글은 그대로 (선행 기능 무회귀)",
    doc.querySelector(".attach-diff-hltoggle").hidden === false);

  doc = await openSource({ ...CSV_RESP, viewable: false, rows: [] });
  ok("C6 바이너리(viewable=false)는 토글 없음",
    doc.querySelector(".attach-source-tabletoggle").hidden === true);
  doc = await openSource({ ...CSV_RESP, rows: [] });
  ok("C7 빈 문서도 토글 없음", doc.querySelector(".attach-source-tabletoggle").hidden === true);

  window.document.body.innerHTML = "";
  API_STATUS = 503; API_RESPONSE = { error: "boom" };
  const mod = mkModule();
  mod.openAttachmentSourceModal(11, { filename: "orders.csv" });
  await tick(); await tick();
  ok("C8 조회 실패도 토글 없음",
    window.document.querySelector(".attach-source-tabletoggle").hidden === true);
  API_STATUS = 200;

  // 호출부가 파일명을 안 넘기는 경로(말풍선 칩) — 서버 응답의 filename 으로 판정이 정정돼야 한다.
  doc = await openSource(CSV_RESP, {});
  ok("C9 파일명 없이 열어도 응답의 filename 으로 표 토글이 뜬다",
    doc.querySelector(".attach-source-tabletoggle").hidden === false);
  STORE = {};
}

// ── (D) 렌더 구조 ────────────────────────────────────────────────────────────
console.log("\n[D] 렌더 구조 — 격자가 실제로 만들어지는가");
{
  MD_CALLS = 0;
  const doc = await openSource(CSV_RESP);
  const table = doc.querySelector("table.attach-source-table");
  ok("D1 표 요소 생성", !!table);
  ok("D2 줄번호 원문 표가 아니다 (표 뷰에서는 줄 표가 없어야 한다)",
    doc.querySelectorAll("table.attach-diff-table.is-source").length === 0);
  ok("D3 마크다운 파이프라인을 타지 않는다 (값에 파서를 물리지 않는다)", MD_CALLS === 0, `md 호출 ${MD_CALLS}회`);
  const ths = Array.from(table ? table.querySelectorAll("thead th") : []).map((e) => e.textContent);
  ok("D4 첫 행이 머리글 (행 번호 열 + 3개 열)",
    JSON.stringify(ths) === JSON.stringify(["#", "id", "name", "amount"]), JSON.stringify(ths));
  const trs = Array.from(table ? table.querySelectorAll("tbody tr") : []);
  ok("D5 데이터 행 3개", trs.length === 3, String(trs.length));
  const cells = trs.map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.textContent));
  ok("D6 행 번호는 파일 레코드 번호 (머리글=1 이므로 데이터는 2,3,4)",
    cells.map((c) => c[0]).join(",") === "2,3,4", JSON.stringify(cells.map((c) => c[0])));
  ok("D7 인용 필드가 한 셀로 들어간다 (`쉼표, 포함`)",
    cells[1] && cells[1][2] === "쉼표, 포함", JSON.stringify(cells[1]));
  ok("D8 빈 필드도 셀로 존재 (열이 밀리지 않는다)",
    cells[2] && cells[2][2] === "" && cells[2][3] === "0", JSON.stringify(cells[2]));
  ok("D9 수치 셀은 우측 정렬 클래스", !!(trs[0] && trs[0].querySelector("td.is-num")),
    trs[0] && trs[0].innerHTML.slice(0, 160));
  ok("D10 텍스트 셀에는 수치 클래스가 붙지 않는다",
    !!(trs[0] && trs[0].querySelectorAll("td")[2] && !trs[0].querySelectorAll("td")[2].classList.contains("is-num")));

  // 머리글만 있는 파일 — 빈 격자를 조용히 두지 않는다.
  const d2 = await openSource(mkResp("head.csv", ["id,name"]));
  ok("D11 머리글 한 줄뿐이면 그 사실을 말한다",
    /머리글 행만/.test(d2.querySelector(".attach-diff-body").textContent),
    d2.querySelector(".attach-diff-body").textContent.slice(0, 80));

  // codex [P1] 의 화면 쪽 귀결 — 데이터 행이 **있는데** "없습니다" 로 읽히던 자리.
  const d3 = await openSource(mkResp("emptyquoted.csv", ["id", '""']));
  ok("D12 명시적 빈 인용 필드 행이 표에 남는다 (거짓 «데이터 없음» 금지)",
    d3.querySelectorAll("table.attach-source-table tbody tr").length === 1
    && !/머리글 행만/.test(d3.querySelector(".attach-diff-body").textContent),
    d3.querySelector(".attach-diff-body").textContent.slice(0, 80));

  // codex [P1] — 값이 변형된 사실을 화면이 말한다.
  const d4 = await openSource(mkResp("odd.csv", ["id,name", '1,"a"b']));
  ok("D13 따옴표 형식 이상을 배너로 신고한다",
    /따옴표 형식이 표준과 다른 칸이 1개/.test(d4.querySelector(".attach-diff-body").textContent),
    d4.querySelector(".attach-diff-body").textContent.slice(0, 140));
  // ⚠ `doc` 는 같은 `window.document` 참조라 앞 케이스를 재사용하면 마지막 렌더를 보게 된다
  //   (초판이 그 함정에 걸려 거짓 FAIL 을 냈다). 정상 CSV 를 **다시 열어** 대조한다.
  const d5 = await openSource(CSV_RESP);
  ok("D13b 정상 CSV 에는 그 배너가 뜨지 않는다 (거짓 경고 금지)",
    !/따옴표 형식이/.test(d5.querySelector(".attach-diff-body").textContent),
    d5.querySelector(".attach-diff-body").textContent.slice(0, 140));
  STORE = {};
}

// ── (E) XSS ──────────────────────────────────────────────────────────────────
console.log("\n[E] 셀 값은 값으로만 들어간다");
{
  const evil = [
    "id,payload",
    '1,"<script>window.__pwned=1</script>"',
    '2,"<img src=x onerror=""window.__pwned=2"">"',
    '3,"<a href=""javascript:alert(1)"">클릭</a>"',
  ];
  window.__pwned = undefined;
  const doc = await openSource(mkResp("evil.csv", evil));
  const table = doc.querySelector("table.attach-source-table");
  ok("E1 표는 그려진다", !!table);
  ok("E2 `<script>` 요소가 생기지 않는다", doc.querySelectorAll("script").length === 0);
  ok("E3 `<img>`·`<a>` 요소가 생기지 않는다",
    !!table && table.querySelectorAll("img, a, iframe").length === 0, table && table.innerHTML.slice(0, 200));
  ok("E4 마크업은 **텍스트로** 남는다 (값이 사라지지 않는다)",
    !!table && table.textContent.includes("<script>") && table.textContent.includes("onerror"),
    table && table.textContent.slice(0, 120));
  ok("E5 스크립트가 실행되지 않았다", window.__pwned === undefined);
  STORE = {};
}

// ── (F) 원문 복귀 · 영속 ─────────────────────────────────────────────────────
console.log("\n[F] 원문 복귀 · 선택 영속");
{
  const doc = await openSource(CSV_RESP);
  const cb = doc.querySelector(".attach-source-table-cb");
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("F1 끄면 표가 사라진다", doc.querySelectorAll("table.attach-source-table").length === 0);
  const lines = Array.from(doc.querySelectorAll("td.attach-diff-code")).map((td) => td.textContent);
  ok("F2 종전 줄 표로 돌아오고 내용은 byte 무손실",
    JSON.stringify(lines) === JSON.stringify(CSV_LINES), JSON.stringify(lines));
  ok("F3 원문으로 돌아오면 구문 색 토글이 다시 보인다",
    doc.querySelector(".attach-diff-hltoggle").hidden === false);
  ok("F4 선택이 저장된다", STORE.attachSourceTable === "0", JSON.stringify(STORE));

  const doc2 = await openSource(CSV_RESP);
  ok("F5 다음 열람에도 유지된다 (원문 보기 상태)",
    doc2.querySelector(".attach-source-table-cb").checked === false
    && doc2.querySelectorAll("table.attach-source-table").length === 0);
  const cb2 = doc2.querySelector(".attach-source-table-cb");
  cb2.checked = true;
  cb2.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("F6 다시 켜면 표로 돌아온다", doc2.querySelectorAll("table.attach-source-table").length === 1);
  STORE = {};
}

// ── (G) 상한 ─────────────────────────────────────────────────────────────────
console.log("\n[G] 상한 — 조용히 자르지 않는다");
{
  const wide = ["h".repeat(1), Array.from({ length: 320 }, (_, i) => `c${i}`).join(",")];
  wide[0] = Array.from({ length: 320 }, (_, i) => `h${i}`).join(",");
  const docW = await openSource(mkResp("wide.csv", wide));
  const th = docW.querySelectorAll("table.attach-source-table thead th");
  ok("G1 열 상한 적용 (행 번호 열 + 200열)", th.length === 201, String(th.length));
  ok("G2 열 절단을 배너로 알린다",
    /표가 너무 커서/.test(docW.querySelector(".attach-diff-body").textContent),
    docW.querySelector(".attach-diff-body").textContent.slice(0, 100));

  // 셀 상한 — 열 20개 × 3000행 = 60,000 셀 > 30,000.
  const many = ["c0,c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13,c14,c15,c16,c17,c18,c19"];
  for (let i = 0; i < 3000; i++) many.push(Array.from({ length: 20 }, (_, j) => `${i}-${j}`).join(","));
  const docM = await openSource(mkResp("many.csv", many));
  const rows = docM.querySelectorAll("table.attach-source-table tbody tr").length;
  ok("G3 셀 상한으로 행이 잘린다", rows > 0 && rows < 3000, String(rows));
  ok("G4 행 절단도 배너로 알린다",
    /표가 너무 커서/.test(docM.querySelector(".attach-diff-body").textContent));
  STORE = {};
}

// ── (H) 배타 ─────────────────────────────────────────────────────────────────
console.log("\n[H] 다른 화면·다른 형식과의 배타");
{
  const docMd = await openSource(mkResp("spec.md", ["# 제목", "본문"]));
  ok("H1 `.md` 첨부에는 표 토글이 없다",
    docMd.querySelector(".attach-source-tabletoggle").hidden === true);
  ok("H2 그 화면의 마크다운 토글은 그대로 (선행 기능 무회귀)",
    docMd.querySelector(".attach-source-mdtoggle").hidden === false);
  STORE = {};

  // 비교 모달 — 변경이 있는 diff 화면에서는 표로 바꾸면 줄 대조가 사라진다.
  window.document.body.innerHTML = "";
  API_RESPONSE = {
    comparable: true,
    identical: false,
    filename: "orders.csv",
    from: { version_number: 1 }, to: { version_number: 2 },
    stats: { added: 1, removed: 1, identical: false },
    truncated: {},
    caps: { rows: 6000 },
    rows: [
      { type: "replace", left_no: 1, left: "a,b", right_no: 1, right: "a,c" },
    ],
  };
  const mod = mkModule();
  mod.openAttachmentDiffModal(11, [
    { id: 11, version_number: 1, original_filename: "orders.csv" },
    { id: 12, version_number: 2, original_filename: "orders.csv" },
  ]);
  await tick(); await tick();
  ok("H3 변경이 있는 비교 화면에는 표 토글이 뜨지 않는다 (줄 대조 보존)",
    window.document.querySelector(".attach-source-tabletoggle").hidden === true);

  // 같은 내용(identical) 화면은 원문 출력이므로 표가 뜻을 갖는다.
  window.document.body.innerHTML = "";
  API_RESPONSE = {
    comparable: true,
    identical: true,
    filename: "orders.csv",
    from: { version_number: 1 }, to: { version_number: 2 },
    stats: { added: 0, removed: 0, identical: true },
    truncated: {},
    caps: { rows: 6000 },
    rows: mkRows(CSV_LINES),
  };
  const mod2 = mkModule();
  mod2.openAttachmentDiffModal(11, [
    { id: 11, version_number: 1, original_filename: "orders.csv" },
    { id: 12, version_number: 2, original_filename: "orders.csv" },
  ]);
  await tick(); await tick();
  ok("H4 내용이 같은 비교 화면(=원문 출력)에서는 표 토글이 뜬다",
    window.document.querySelector(".attach-source-tabletoggle").hidden === false);
  ok("H5 그 화면도 실제로 격자로 그려진다",
    window.document.querySelectorAll("table.attach-source-table").length === 1);
  STORE = {};
}

// ── (J) 폴백 ─────────────────────────────────────────────────────────────────
console.log("\n[J] 표로 만들 수 없으면 원문으로 떨어진다 (조용히 비우지 않는다)");
{
  // 값이 하나도 없는 본문(개행만) — 서버는 `viewable:true` + 행 3개를 주므로 토글이 뜨고
  // 렌더가 시도된다. 여기서 빈 격자를 그리면 사용자는 "고장" 으로 읽는다.
  const doc = await openSource(mkResp("blank.csv", ["", "", ""]));
  ok("J1 빈 격자를 그리지 않는다", doc.querySelectorAll("table.attach-source-table").length === 0);
  ok("J2 원문 줄 표로 떨어진다", doc.querySelectorAll("table.attach-diff-table.is-source").length === 1);
  ok("J3 폴백 사유를 말한다",
    /표로 만들 수 있는 내용이 없어/.test(doc.querySelector(".attach-diff-body").textContent),
    doc.querySelector(".attach-diff-body").textContent.slice(0, 100));
  ok("J4 컨트롤을 화면과 일치시킨다 (체크는 켜졌는데 원문이 보이는 상태를 만들지 않는다)",
    doc.querySelector(".attach-source-table-cb").checked === false);
  ok("J5 강등이므로 저장값은 건드리지 않는다 (다음 열람에서 다시 시도)",
    STORE.attachSourceTable === undefined, JSON.stringify(STORE));
  STORE = {};
}

// ── (I) CSS 계약 ─────────────────────────────────────────────────────────────
console.log("\n[I] CSS 계약 (jsdom 이 못 보는 축 — 규칙 존재만 단정)");
{
  ok("I1 표 스타일 존재", /\.attach-source-table\s*\{/.test(chatCss));
  ok("I2 머리글 sticky (스크롤해도 열 이름이 남는다)",
    /\.attach-source-table thead th\s*\{[^}]*position:\s*sticky/.test(chatCss),
    (chatCss.match(/\.attach-source-table thead th\s*\{[^}]*\}/) || [""])[0].slice(0, 120));
  ok("I3 sticky 와 함께 `border-collapse: separate` (collapse 면 테두리가 함께 스크롤된다)",
    /\.attach-source-table\s*\{[^}]*border-collapse:\s*separate/.test(chatCss));
  ok("I4 `[hidden]` 강제 — 토글 숨김 계약이 CSS 층에서 무력화되지 않는다",
    /\.attach-source-tabletoggle\[hidden\]\s*(,[^{]*)?\{[^}]*display:\s*none/.test(chatCss)
    || /\.attach-source-mdtoggle\[hidden\],\s*\n?\.attach-source-tabletoggle\[hidden\]\s*\{[^}]*display:\s*none/.test(chatCss));
  ok("I5 셀 값의 줄바꿈·연속 공백 보존 (인용 필드는 여러 줄일 수 있다)",
    /\.attach-source-table-cell\s*\{[^}]*white-space:\s*pre-wrap/.test(chatCss));
  // 실측 캡처에서 적발된 두 축 — 선언만 있고 효과가 없던 자리.
  ok("I5b 값 상한은 **셀 래퍼**에 있다 (`td` 에 두면 table-layout:auto 가 무시한다)",
    /\.attach-source-table-cell\s*\{[^}]*max-width:/.test(chatCss)
    && !/\.attach-source-table th,\s*\n?\.attach-source-table td\s*\{[^}]*max-width:/.test(chatCss));
  ok("I5c 행 번호는 접히지 않는다 (`td` 의 pre-wrap 이 번호 열을 덮어쓰지 않는다)",
    /\.attach-source-table-no\s*\{[^}]*white-space:\s*nowrap/.test(chatCss)
    && !/\.attach-source-table th,\s*\n?\.attach-source-table td\s*\{[^}]*white-space:/.test(chatCss));
  ok("I6 표 wrap 이 자체 스크롤 컨테이너가 아니다 (sticky 기준이 부모 scroller 여야 한다)",
    !/\.attach-source-tablewrap\s*\{[^}]*overflow/.test(chatCss));
}

console.log(`\n결과: ${passed} PASS · ${failed} FAIL`);
process.exit(failed === 0 ? 0 : 1);
