// verify_attach_version_tree_ui.mjs
// REQ-20260814-attach-version-tree-ui — 첨부 버전 비교의 **축 토글**(이 계보 안 / 계보 간 시간순).
//
// 사용자 결정(2026-08-14): assistant 수정본이 별도 계보로 분기하면서 "최신" 이 두 뜻이 됐다 —
// **계보 내 최신**(이 체인의 최고 버전)과 **시간순 최신**(같은 파일의 모든 계보 중 가장 나중).
// 화면에서도 두 축을 고를 수 있어야 하며, 축에 따라 `<select>` 값의 의미와 요청 파라미터가
// **함께** 바뀐다(version_number ↔ attachment_id / from_version ↔ from_attachment_id).
// 한쪽만 바뀌면 엉뚱한 쌍을 비교하거나 서버가 400 을 던진다 — 그 짝을 여기서 고정한다.
//
// 정본 모듈을 jsdom 위에서 그대로 실행한다(로직 재구현 0). 최종 시각 확인은 PB-0008.
// 실행: node verify_attach_version_tree_ui.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const composerJs = read("app", "composer.js");
const messagesJs = read("app", "messages.js");
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
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/m, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존"); process.exit(2); }

const CH = new Function(`${read("code-highlight.js").replace(/^export\s+/gm, "")}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();

/** 모달을 띄우고 fetch URL 을 기록하는 하네스. */
function mount({ versions, lineages }) {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  const { window } = dom;
  const calls = [];
  const stubs = {
    document: window.document,
    window,
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    requestAnimationFrame: (fn) => fn(),
    apiFetch: async (url) => {
      calls.push(String(url));
      return { comparable: true, identical: false, stats: { added: 0, removed: 0 },
               caps: { source_bytes: 1, rows: 1 },
               truncated: { from_source: false, to_source: false, rows: false },
               from: { version_number: 1 }, to: { version_number: 2 }, rows: [] };
    },
    bindBackdropDismiss: () => {},
    showToast: (m) => calls.push(`toast:${m}`),
    escapeHtml: (v = "") => String(v),
    detectCodeLanguage: CH.detectCodeLanguage,
    paintCodeInto: CH.paintCodeInto,
    codeLanguageLabel: CH.codeLanguageLabel,
  };
  const M = new Function(...Object.keys(stubs),
    `${MODULE_BODY}\nreturn { openAttachmentDiffModal };`)(...Object.values(stubs));
  M.openAttachmentDiffModal(101, versions, undefined, lineages);
  const root = window.document.querySelector(".attach-diff-backdrop");
  return { window, root, calls };
}

const VERSIONS = [
  { version_number: 1, created_by_role: "user", original_filename: "r.sql" },
  { version_number: 2, created_by_role: "user", original_filename: "r.sql" },
];
const LINEAGES = [
  // 서버는 시간순 **최신 우선**으로 준다.
  { head_attachment_id: 202, version_number: 1, is_assistant_generated: true, is_current_lineage: false },
  { head_attachment_id: 101, version_number: 2, is_assistant_generated: false, is_current_lineage: true },
];

// ── A. 토글 노출 조건 ──────────────────────────────────────────────────────
{
  const { root } = mount({ versions: VERSIONS, lineages: LINEAGES });
  ok("A1 계보 2개면 축 토글이 뜬다", !!root.querySelector(".attach-diff-axistoggle"));
  ok("A2 축 버튼 2개(계보 안 / 시간순)", root.querySelectorAll(".attach-diff-axis").length === 2);
  ok("A3 기본 축은 '이 계보 안'",
    root.querySelector('.attach-diff-axis[data-axis="lineage"]').classList.contains("is-active"));
}
{
  const { root } = mount({ versions: VERSIONS, lineages: [LINEAGES[1]] });
  ok("A4 계보가 하나면 토글을 숨긴다(선택지 1개짜리 토글 금지)",
    !root.querySelector(".attach-diff-axistoggle"));
}

// ── B. 축 전환이 옵션 값의 **의미**를 바꾼다 ───────────────────────────────
{
  const { root } = mount({ versions: VERSIONS, lineages: LINEAGES });
  const fromSel = root.querySelector(".attach-diff-from");
  const vals0 = Array.from(fromSel.options).map((o) => o.value);
  ok("B1 계보 안 축의 옵션 값 = version_number", vals0.join(",") === "1,2");

  root.querySelector('.attach-diff-axis[data-axis="time"]').dispatchEvent(
    new root.ownerDocument.defaultView.Event("click"));
  const vals1 = Array.from(root.querySelector(".attach-diff-from").options).map((o) => o.value);
  ok("B2 시간순 축의 옵션 값 = attachment_id", vals1.join(",") === "101,202");
  ok("B3 시간순은 과거→최신 순서(좌=기준, 우=비교)",
    vals1[0] === "101" && vals1[vals1.length - 1] === "202");
  const labels = Array.from(root.querySelector(".attach-diff-from").options).map((o) => o.textContent);
  ok("B4 옵션 라벨이 계보 소유자를 밝힌다",
    labels.some((t) => t.includes("AI 수정본")) && labels.some((t) => t.includes("사용자 업로드")));
  ok("B5 현재 계보를 표시한다", labels.some((t) => t.includes("현재")));
  ok("B6 축 버튼 활성 상태가 따라간다",
    root.querySelector('.attach-diff-axis[data-axis="time"]').classList.contains("is-active")
    && !root.querySelector('.attach-diff-axis[data-axis="lineage"]').classList.contains("is-active"));
}

// ── C. 요청 파라미터가 축과 **함께** 바뀐다 ────────────────────────────────
{
  const { root, calls } = mount({ versions: VERSIONS, lineages: LINEAGES });
  root.querySelector('.attach-diff-axis[data-axis="time"]').dispatchEvent(
    new root.ownerDocument.defaultView.Event("click"));
  // 모달의 load() 는 async — 마이크로태스크를 소진해 fetch 기록이 쌓이게 한다.
  for (let i = 0; i < 8; i++) await Promise.resolve();
  const timeCalls = calls.filter((u) => u.includes("from_attachment_id"));
  ok("C1 시간순 축은 from_attachment_id/to_attachment_id 로 요청",
    timeCalls.length > 0 && timeCalls[timeCalls.length - 1].includes("to_attachment_id"));
  ok("C2 시간순 요청에 version 파라미터가 섞이지 않는다",
    timeCalls.length > 0 && !timeCalls[timeCalls.length - 1].includes("from_version"));
}

// ── D. 배선·구조 잠금 ──────────────────────────────────────────────────────
ok("D1 messages.js 가 lineages 를 모달에 넘긴다",
  /openAttachmentDiffModal\(att\.id, versions, preselect, lineages\)/.test(messagesJs));
ok("D2 messages.js 가 계보 2개면 버전 1개여도 모달을 연다",
  /versions\.length < 2 && lineages\.length < 2/.test(messagesJs));
ok("D3 composer.js 버전 박스도 lineages 를 전달(경로 간 비대칭 방지)",
  /_renderAttachmentVersionsBox\(versionsBox, Array\.isArray\(vresp\?\.versions\)/.test(composerJs)
  && /\{ from: vnum, to: latestNum \}, lineages\)/.test(composerJs));
ok("D4 요청 파라미터 구성이 _diffParams 한 곳으로 모인다(축 추가 시 누락 방지)",
  /_diffParams\(from, to\)/.test(diffJs) && /_diffParams\(fromSel\.value, toSel\.value\)/.test(diffJs));
ok("D5 축 전환 시 전체-펼침 캐시를 버린다(이전 축 결과 재사용 금지)",
  /axis = next;[\s\S]{0,300}fullRowsCache = null/.test(diffJs));
ok("D6 CSS 는 보기방식 토글과 같은 위젯을 공유", /\.attach-diff-axis\b/.test(chatCss));

// ── E. §18.8 적대 리뷰 반영 축 ─────────────────────────────────────────────
ok("E1 [P1] AI 수정본 칩은 v1 이어도 비교 버튼을 얻는다(핵심 시나리오 진입점)",
  /_isAiEdit\s*=\s*!!\(att\.is_assistant_generated/.test(messagesJs)
  && /att\.id && \(verNum > 1 \|\| _isAiEdit\)/.test(messagesJs));
ok("E2 [P2] 동일 선택 원문 분기가 축을 인지한다(시간순 값은 이미 attachment_id)",
  /axis === "time"[\s\S]{0,120}Number\(from \|\| 0\)/.test(diffJs));
ok("E3 [P2] 전체-펼침 캐시 키에 축이 들어간다(축 간 키 충돌 방지)",
  /pairKey = \(\) => `\$\{axis\}:/.test(diffJs));
ok("E4 [P2] 펼침 응답이 도착해도 축·선택이 바뀌었으면 버린다",
  /axisAtRequest !== axis/.test(diffJs));
ok("E5 [P2] versions 가 비어도 파일명 폴백으로 죽지 않는다",
  /lins\[0\]\?\.original_filename/.test(diffJs));

// E6 — 실제로 versions 없이 계보만으로 열어 본다(예외가 나면 mount 가 던진다).
{
  const { root } = mount({ versions: [], lineages: LINEAGES });
  ok("E6 [P2] 계보만 있고 버전이 없어도 모달이 뜬다", !!root && !!root.querySelector(".attach-diff-axistoggle"));
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
