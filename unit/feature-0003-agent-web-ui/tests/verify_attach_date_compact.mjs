// verify_attach_date_compact.mjs
// attach-date-compact — 첨부 목록·버전 이력의 "첨부된 날짜" compact 표기 계약 검증.
//
// 사용자 요청(2026-08-06): "첨부파일이 첨부된 날짜도 compact하게 출력되도록 개선해주세요."
//
// 가장 위험한 축은 **시간대**다. 서버 `created_at` 은 오프셋 없는 로컬(KST) naive 문자열이고
// (`CreatedAt` 이 MySQL `NOW()` 기반 · 컨테이너 TZ=Asia/Seoul — 실측 2026-08-06 18:50 업로드가
// `2026-08-06T18:50:29`), 오프셋 없는 ISO date-time 을 `new Date()` 는 **로컬로** 해석하므로
// 그대로 넘겨야 맞다. 선행 cycle 의 `restorable_until` 은 반대로 UTC 라 `Z` 보정이 필요했다 —
// 같은 응답 안에서도 필드마다 다르므로, 여기에 `Z` 를 붙이는 회귀를 뮤테이션으로 잠근다.
//
// 검증 4축: (A) 포맷 함수 실행 (B) 시간대 (C) 렌더 배선(정적) (D) 뮤테이션 역검증.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const composerJs = readFileSync(join(STATIC, "app", "composer.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// 정본에서 함수 본문만 추출해 실행한다(로직 재구현 0).
function extractFunction(src, name) {
  const m = new RegExp(`(?:^|\\n)(?:async\\s+)?function\\s+${name}\\s*\\(`, "m").exec(src);
  if (!m) throw new Error(`함수 미발견: ${name}`);
  const start = m.index + (m[0].startsWith("\n") ? 1 : 0);
  let i = src.indexOf("{", m.index + m[0].length - 1);
  let depth = 0, inS = null, esc = false, tpl = 0;
  for (; i < src.length; i++) {
    const c = src[i];
    if (esc) { esc = false; continue; }
    if (c === "\\") { esc = true; continue; }
    if (inS) { if (c === inS) inS = null; continue; }
    if (c === '"' || c === "'") { inS = c; continue; }
    if (c === "`") { tpl = tpl ? 0 : 1; continue; }
    if (tpl) continue;
    if (c === "/" && src[i + 1] === "/") { i = src.indexOf("\n", i); if (i < 0) break; continue; }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error(`함수 종료 미발견: ${name}`);
}

const SRC_DATE = extractFunction(composerJs, "_attachWhenDate");
const SRC_FMT = extractFunction(composerJs, "_fmtAttachWhen");
const SRC_TITLE = extractFunction(composerJs, "_attachWhenTitle");

function build(source) {
  // eslint-disable-next-line no-new-func
  return new Function(`${SRC_DATE}\n${SRC_FMT}\n${SRC_TITLE}\nreturn {_fmtAttachWhen,_attachWhenTitle,_attachWhenDate};`)();
}
const F = build();

const pad = (n) => String(n).padStart(2, "0");
const local = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

// ── (A) 포맷 ─────────────────────────────────────────────────────────────────
console.log("(A) 포맷");
{
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 14, 20, 7);
  ok("A1 오늘은 HH:MM", F._fmtAttachWhen(local(today)) === "14:20");

  // 올해의 다른 날 — 오늘과 겹치지 않도록 1~2월과 11~12월 중 오늘이 아닌 날을 고른다.
  const otherMonth = now.getMonth() === 0 ? 6 : 0;
  const thisYear = new Date(now.getFullYear(), otherMonth, 6, 9, 5, 0);
  ok("A2 올해는 M/D", F._fmtAttachWhen(local(thisYear)) === `${otherMonth + 1}/6`);

  const lastYear = new Date(now.getFullYear() - 1, 7, 6, 9, 5, 0);
  const yy = String(now.getFullYear() - 1).slice(2);
  ok("A3 지난해는 YY/M/D", F._fmtAttachWhen(local(lastYear)) === `${yy}/8/6`);

  ok("A4 빈 값·잘못된 값은 빈 문자열",
    F._fmtAttachWhen(null) === "" && F._fmtAttachWhen("") === "" && F._fmtAttachWhen("nonsense") === "");
  ok("A5 title 은 전체 시각",
    F._attachWhenTitle(local(new Date(2026, 7, 6, 18, 50, 29))) === "2026-08-06 18:50");
  ok("A6 title 도 잘못된 값은 빈 문자열", F._attachWhenTitle("nope") === "");
}

// ── (B) 시간대 — 오프셋 없는 문자열은 로컬로 해석해야 한다 ────────────────────
console.log("(B) 시간대");
{
  const d = F._attachWhenDate("2026-08-06T18:50:29.585993");
  ok("B1 오프셋 없는 값을 로컬 시각으로 해석(시:분 보존)",
    d.getHours() === 18 && d.getMinutes() === 50);
  ok("B2 마이크로초 6자리를 파싱한다(NaN 아님)", d instanceof Date && !isNaN(d.getTime()));
  // Z 를 붙이면 KST(+9) 브라우저에서 9시간 밀린다 — 그 오해를 수치로 고정한다.
  const asUtc = new Date("2026-08-06T18:50:29.585993Z");
  const skewHours = Math.abs(asUtc.getTime() - d.getTime()) / 3600000;
  ok("B3 Z 를 붙이면 로컬 오프셋만큼 어긋난다(정본과 다른 값)",
    -new Date().getTimezoneOffset() === 0 ? true : skewHours > 0);
}

// ── (C) 렌더 배선(정적) ──────────────────────────────────────────────────────
console.log("(C) 렌더 배선");
{
  ok("C1 목록 메타줄이 whenChip 을 싣는다", /\$\{fmtSize\(a\.size \|\| 0\)\}\$\{whenChip\}/.test(composerJs));
  ok("C2 whenChip 이 created_at 으로 만들어진다", /_fmtAttachWhen\(a\.created_at\)/.test(composerJs));
  ok("C3 whenChip 에 전체 시각 title", /_attachWhenTitle\(a\.created_at\)/.test(composerJs));
  ok("C4 값이 없으면 칩 자체를 넣지 않는다(빈 ` · ` 방지)",
    /_fmtAttachWhen\(a\.created_at\)\s*\n?\s*\?/.test(composerJs));
  ok("C5 버전 이력 행에도 시각", /_fmtAttachWhen\(v\.created_at\)/.test(composerJs));
  ok("C6 렌더 값은 escapeHtml 을 거친다",
    /escapeHtml\(_fmtAttachWhen\(a\.created_at\)\)/.test(composerJs));
}

// ── (D) 뮤테이션 역검증 ──────────────────────────────────────────────────────
console.log("(D) 뮤테이션 역검증");
{
  // D1 — `Z` 를 붙이는 회귀(선행 cycle 의 restorable_until 보정을 잘못 이식한 형태).
  const mutZ = build.call(null);
  const srcZ = `${SRC_DATE.replace("new Date(String(iso))", 'new Date(String(iso) + "Z")')}\n${SRC_FMT}\n${SRC_TITLE}\nreturn {_fmtAttachWhen,_attachWhenTitle,_attachWhenDate};`;
  // eslint-disable-next-line no-new-func
  const MZ = new Function(srcZ)();
  const sample = "2026-08-06T18:50:29";
  const tzOffsetMin = new Date().getTimezoneOffset();
  const detected = tzOffsetMin === 0
    ? true  // UTC 러너에서는 두 해석이 같아 이 축을 구별할 수 없다 — 그 사실을 그대로 인정.
    : MZ._attachWhenTitle(sample) !== F._attachWhenTitle(sample);
  ok("D1 Z 부착 회귀가 검출된다(비-UTC 러너)", detected);
  if (tzOffsetMin === 0) console.log("        ⚠ 러너 TZ=UTC — D1 은 이 환경에서 판별력이 없다(라이브 KST 에서 유효).");

  // D2 — 오늘 분기를 제거하면(항상 M/D) 오늘 값이 시:분으로 나오지 않는다.
  const srcNoToday = `${SRC_DATE}\n${SRC_FMT.replace(/if \(sameDay\)[\s\S]*?;\n/, "")}\n${SRC_TITLE}\nreturn {_fmtAttachWhen,_attachWhenTitle,_attachWhenDate};`;
  // eslint-disable-next-line no-new-func
  const MN = new Function(srcNoToday)();
  const now = new Date();
  const todayIso = local(new Date(now.getFullYear(), now.getMonth(), now.getDate(), 14, 20, 7));
  ok("D2 오늘 분기 제거가 검출된다", MN._fmtAttachWhen(todayIso) !== "14:20");

  // D3 — 목록 배선을 되돌리면(whenChip 미삽입) C1 이 red 가 된다.
  const reverted = composerJs.replace("${fmtSize(a.size || 0)}${whenChip}", "${fmtSize(a.size || 0)}");
  ok("D3 목록 배선 제거가 검출된다",
    !/\$\{fmtSize\(a\.size \|\| 0\)\}\$\{whenChip\}/.test(reverted));
  void mutZ;
}

console.log(`\n결과: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
