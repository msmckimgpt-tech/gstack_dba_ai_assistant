// verify_hangul_qwerty.mjs
// hangul-qwerty-search: 한/영 자판 전환을 잊고 친 검색어도 결과를 내게 한다.
//
//   [결함] 사용자가 `ㅎㅋ`(=`gz`), `ㅈ듀`(=`web`), `rmffhqjf`(=`글로벌`) 를 검색창에 치면
//          어느 화면도 이를 흡수하지 못해 "검색 결과가 없습니다" 만 나왔다(사용자 보고 2건).
//   [수정] `static/hangul-qwerty.js` 저장소 단일 primitive 가 반대 자판 후보를 만들고,
//          모든 검색 지점이 원문과 후보를 함께 부분일치한다. 서버측 동형 정본은
//          `shared/hangul_qwerty.py` (같은 매핑표 — 아래 (C) 가 두 파일을 대조한다).
//
// 검증 4축:
//   (A) 변환 정확성 — 두벌식 표준 배열 왕복(한→영, 영→한) 케이스 표.
//   (B) 후보 계약 — searchVariants 의 첫 항목이 항상 원문(소문자), 중복·빈 값 없음,
//       matchesAnyVariant 가 빈 후보를 "전체 통과" 로 취급(빈 검색어 = 필터 없음).
//   (C) 매핑표 동기 — JS 와 Python 정본의 자모↔키 표가 **값 단위로 동일**함을 파일에서
//       파싱해 대조한다(한쪽만 고치는 drift 가 이 결함의 재발 기전).
//   (D) 배선 census — 검색 부분일치를 하는 모든 지점이 primitive 를 쓰고, 옛 `includes(q)`
//       직접 매칭이 남지 않았음을 **파일 목록 하드코딩 없이** 전-트리 walk 로 단언한다.
//
// 실행: node verify_hangul_qwerty.mjs
//   (순수 정적 + 자체 모듈 로드 — jsdom/네트워크 비의존.)

import { readFileSync, readdirSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const REPO = join(__dirname, "..", "..", "..");
const read = (...seg) => readFileSync(join(...seg), "utf8");

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ` :: ${detail}` : ""}`); }
}

// `.js` 는 이 저장소에 package.json type 이 없어 CJS 로 해석된다 — ESM 으로 로드하려고
// 확장자만 바꾼 사본을 임시 디렉터리에 두고 import 한다(원본 무수정).
const tmp = mkdtempSync(join(tmpdir(), "hq-"));
const primitiveSrc = read(STATIC, "hangul-qwerty.js");
const modPath = join(tmp, "hangul-qwerty.mjs");
writeFileSync(modPath, primitiveSrc, "utf8");
const HQ = await import(pathToFileURL(modPath).href);

/* ── (A) 변환 정확성 ─────────────────────────────────────────────────────── */
// 사용자 제시 4건 + 자모/겹받침/복합모음/쌍자음 경계 케이스.
const CASES = [
  ["ㅎㅋ", "gz"],                 // 자모만(미완성 조합) — 사용자 예시
  ["ㅈ듀", "web"],                // 자모 + 음절 혼합 — 사용자 예시
  ["글로벌", "rmffhqjf"],          // 받침 이월(ㄹ→다음 초성) — 사용자 예시
  ["스키드", "tmzlem"],            // 받침 이월 연속 — 사용자 예시
  ["안녕하세요", "dkssudgktpdy"],
  ["까치", "Rkcl"],               // 쌍자음(Shift)
  ["닭", "ekfr"],                 // 겹받침 ㄺ
  ["값", "rkqt"],                 // 겹받침 ㅄ
  ["의외", "dmldhl"],             // 복합모음 ㅢ/ㅚ
  ["뷁", "qnpfr"],                // 복합모음 ㅞ + 겹받침 ㄺ
  ["웹", "dnpq"],
  ["제품", "wpvna"],
  ["관리", "rhksfl"],
];
console.log("(A) 두벌식 변환 정확성");
for (const [ko, en] of CASES) {
  ok(`한→영 ${ko} → ${en}`, HQ.hangulToQwerty(ko) === en, `got ${HQ.hangulToQwerty(ko)}`);
  ok(`영→한 ${en} → ${ko}`, HQ.qwertyToHangul(en) === ko, `got ${HQ.qwertyToHangul(en)}`);
}
// 자판에 없는 문자는 조합을 끊고 그대로 통과 — 숫자·기호가 섞인 검색어 안전.
ok("비자판 문자 통과(mv_qa)", HQ.qwertyToHangul("_1 ") === "_1 ");
ok("한글 왕복 안정(뷁)", HQ.qwertyToHangul(HQ.hangulToQwerty("뷁")) === "뷁");

/* ── (B) 후보 계약 ──────────────────────────────────────────────────────── */
console.log("(B) searchVariants / matchesAnyVariant 계약");
ok("빈 검색어 → 후보 0", HQ.searchVariants("").length === 0 && HQ.searchVariants(null).length === 0);
ok("빈 후보는 전체 통과", HQ.matchesAnyVariant("무엇이든", []) === true);
{
  const v = HQ.searchVariants("ㅎㅋ");
  ok("첫 항목은 원문", v[0] === "ㅎㅋ");
  ok("반대 자판 후보 포함", v.includes("gz"));
}
{
  const v = HQ.searchVariants("Web");
  ok("원문은 소문자 정규화", v[0] === "web");
  ok("후보 중복 없음", new Set(v).size === v.length);
}
{
  // 한글 없는 순수 숫자·기호는 변환 후보가 생기지 않는다(무의미한 스캔 방지).
  const v = HQ.searchVariants("12-34");
  ok("변환 대상 없으면 후보 1개", v.length === 1, JSON.stringify(v));
}
{
  // 짧은 후보는 원래 맞던 검색을 오염시킨다 — `dk` → `아` 는 "글로벌 라이브" 까지 잡았다(실측).
  const v = HQ.searchVariants("dk");
  ok("1자 변환 후보는 배제(dk → '아' 미채택)", v.length === 1 && v[0] === "dk", JSON.stringify(v));
  ok("2자 이상 변환 후보는 채택(ㅎㅋ → gz)", HQ.searchVariants("ㅎㅋ").includes("gz"));
  // 반대 방향도 같다 — 1자 원문 `가` 가 `rk` 로 확장되면 marketing·worker 가 잡힌다.
  const v1 = HQ.searchVariants("가");
  ok("1자 원문은 확장하지 않음(가 → 'rk' 미생성)", v1.length === 1 && v1[0] === "가", JSON.stringify(v1));
}
ok("원문 매칭 보존", HQ.matchesSearchQuery("MV_QA 제품", "mv_qa"));
ok("반대 자판 매칭(글로벌 ← rmffhqjf)", HQ.matchesSearchQuery("글로벌 서비스", "rmffhqjf"));
ok("반대 자판 매칭(gz ← ㅎㅋ)", HQ.matchesSearchQuery("gz-prod", "ㅎㅋ"));
ok("무관한 검색어는 불일치", HQ.matchesSearchQuery("글로벌", "zzzz") === false);

/* ── (C) JS ↔ Python 매핑표 동기 ────────────────────────────────────────── */
console.log("(C) JS ↔ Python 정본 매핑표 동기");
const pySrc = read(REPO, "shared", "hangul_qwerty.py");
// 두 파일에서 "자모": "키" 쌍을 전부 뽑아 값 단위로 대조(표기·순서 차이 무관).
function pairsFrom(src, sectionStartRe, sectionEndRe) {
  const start = src.search(sectionStartRe);
  if (start < 0) return null;
  const rest = src.slice(start);
  const end = rest.search(sectionEndRe);
  const body = end > 0 ? rest.slice(0, end) : rest;
  const out = new Map();
  // 키는 따옴표(`"ㄱ": "r"`) 또는 bare identifier(`r: "ㄱ"`) 둘 다 허용 — JS/Python 표기 차이.
  const re = /(?:["']([^"']+)["']|([A-Za-z_$][\w$]*))\s*:\s*["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(body)) !== null) out.set(m[1] !== undefined ? m[1] : m[2], m[3]);
  return out;
}
const jsJamo = pairsFrom(primitiveSrc, /const JAMO_TO_KEY = \{/, /\n\};/);
const pyJamo = pairsFrom(pySrc, /^JAMO_TO_KEY = \{/m, /\n\}/);
ok("JAMO_TO_KEY 추출됨", jsJamo && pyJamo && jsJamo.size > 30 && pyJamo.size > 30,
   `js=${jsJamo && jsJamo.size} py=${pyJamo && pyJamo.size}`);
if (jsJamo && pyJamo) {
  const diff = [];
  for (const [k, v] of jsJamo) if (pyJamo.get(k) !== v) diff.push(`${k}:${v}≠${pyJamo.get(k)}`);
  for (const k of pyJamo.keys()) if (!jsJamo.has(k)) diff.push(`py-only ${k}`);
  ok("자모→키 표가 두 정본에서 동일", diff.length === 0, diff.join(", "));
}
const jsKey = pairsFrom(primitiveSrc, /const KEY_TO_JAMO = \{/, /\n\};/);
const pyKey = pairsFrom(pySrc, /^KEY_TO_JAMO = \{/m, /\n\}/);
if (jsKey && pyKey) {
  const diff = [];
  for (const [k, v] of jsKey) if (pyKey.get(k) !== v) diff.push(`${k}:${v}≠${pyKey.get(k)}`);
  for (const k of pyKey.keys()) if (!jsKey.has(k)) diff.push(`py-only ${k}`);
  ok("키→자모 표가 두 정본에서 동일", diff.length === 0, diff.join(", "));
} else {
  ok("KEY_TO_JAMO 추출됨", false, "파싱 실패");
}

/* ── (D) 배선 census (파일 목록 하드코딩 금지) ──────────────────────────── */
console.log("(D) 검색 지점 배선 census");
function walkJs(dir, acc = []) {
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === "vendor" || ent.name.startsWith(".")) continue;
    const p = join(dir, ent.name);
    if (ent.isDirectory()) walkJs(p, acc);
    else if (ent.name.endsWith(".js")) acc.push(p);
  }
  return acc;
}
const files = walkJs(STATIC);
// 검색어 변수를 haystack 에 직접 대는 옛 패턴. primitive 도입 후에는 어디에도 남지 않아야 한다.
//   (변수명에 키잉하지 않기 위해 "짧은 식별자 q/ql/query/needle 을 인자로 넘긴 includes/indexOf"
//    형태를 본다 — 새 검색창이 옛 관용구를 복사하면 여기서 걸린다.)
const LEGACY = /\.(includes|indexOf)\(\s*(q|ql|query|needle|term)\s*\)/;
const offenders = [];
for (const f of files) {
  const src = readFileSync(f, "utf8");
  if (LEGACY.test(src)) offenders.push(f.replace(STATIC + "/", ""));
}
ok("옛 직접 부분일치 잔존 0", offenders.length === 0, offenders.join(", "));

// primitive 를 import 하는 소비처가 실제로 존재해야 census 가 vacuous 하지 않다.
const importers = files.filter((f) => /from\s+["'][^"']*hangul-qwerty\.js/.test(readFileSync(f, "utf8")));
ok("primitive 소비처 ≥ 9", importers.length >= 9, `importers=${importers.length}`);
// 두 ESM 번들(작업 화면 app.js / 관리 콘솔 admin.js) 모두가 primitive 트리에 닿는지.
const importerNames = importers.map((f) => f.replace(STATIC + "/", ""));
ok("작업 화면 번들 배선", importerNames.includes("app.js"));
ok("관리 콘솔 번들 배선", importerNames.includes("admin.js"));

rmSync(tmp, { recursive: true, force: true });
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
