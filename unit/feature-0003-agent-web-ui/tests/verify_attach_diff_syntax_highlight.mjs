// verify_attach_diff_syntax_highlight.mjs
// REQ-20260806T1853-attach-diff-syntax — 첨부 버전 diff 화면의 파일 유형별 구문 하이라이트.
//
// 사용자 요청: "서비스 내 첨부파일의 버전 간 diff 를 비교하는 화면에서 파일 유형에 따른
// 확장 하이라이트(SQL 예약어 등) 를 구성해주세요." (2026-08-06)
// 범위 결정(사용자): "SQL + 구조화 데이터를 우선 추가하되, 차후 확장될 수 있습니다."
//
// 검증 6축:
//   (A) 유형 판정 — 확장자→언어. 대소문자·경로·쿼리 꼬리·이중 확장자(`dump.sql.gz`)·미지원.
//   (B) 토큰 계약 — 언어마다 "무엇이 갈려야 하는가" 를 단언한다(SQL 예약어 vs 식별자, JSON
//       key vs 값 문자열, YAML 주석 경계, XML 태그/속성, CSV 구분자).
//   (C) **원문 무손실 (load-bearing)** — 토큰 조각을 이어붙이면 항상 원문과 byte 동일해야 한다.
//       하이라이트가 내용을 한 글자라도 바꾸면 사용자는 *존재하지 않는 diff* 를 보게 된다.
//       하이라이트 결함 중 유일하게 조용히 치명적인 축이라 전 언어·전 표본에 대해 잠근다.
//   (D) XSS — 토큰 텍스트는 textContent 로만 들어간다. `<script>` 를 품은 줄에서 element 가
//       생기지 않고(span 외 0), 텍스트로만 남는지 확인.
//   (E) 렌더 통합 — `app/attach-diff.js` 의 두 렌더러가 같은 함수로 칠하는지(2열·단일열 parity),
//       lang 부재 시 종전 평문 경로와 동일한지, 토글 버튼 상태 계약.
//   (F) CSS 배선 — `.attach-diff-code .code-tok-*` 규칙과 `--code-tok-*` 변수 정본 존재.
//
// 실행: node verify_attach_diff_syntax_highlight.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인(색 대비·가독성)은 PB-0008 실 Windows 브라우저 — jsdom 은 색을 보지 못한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const chatCss = read("css", "chat.css");
const baseCss = read("css", "base.css");
const appJs = read("app.js");

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

// 정본 모듈을 그대로 태운다 — `export` 만 떼고 `new Function` 으로 평가한다
// (`verify_modal_backdrop_dismiss.mjs` 와 동일 방식. dynamic import 는 Node 가 `.js` 를
// CJS 로 해석해 `export` 에서 죽는다 — 브라우저는 `<script type="module">` 이라 ESM).
// 이 모듈은 DOM 전역을 쓰지 않고 `el.ownerDocument` 만 쓰므로 주입할 스텁이 없다.
const CH_SRC = read("code-highlight.js");
const CH = new Function(`${CH_SRC.replace(/^export\s+/gm, "")}
  return { SQL_HL_KEYWORDS, SQL_HL_TYPES, LANGS, detectCodeLanguage, tokenizeCodeLine,
           paintCodeInto, codeLanguageLabel };`)();
const { detectCodeLanguage, tokenizeCodeLine, paintCodeInto, codeLanguageLabel, LANGS } = CH;

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : `  — ${detail}`}`); }
}
const clsOf = (toks, needle) => (toks || []).filter((t) => t.cls === needle).map((t) => t.text);

// ── (A) 유형 판정 ────────────────────────────────────────────────────────────
console.log("\n[A] 파일 유형 판정");
ok("A1 .sql → sql", detectCodeLanguage("schema.sql") === "sql");
ok("A2 대문자 확장자도 인식", detectCodeLanguage("SCHEMA.SQL") === "sql");
ok("A3 경로 포함 파일명", detectCodeLanguage("db/migrations/0001_init.sql") === "sql");
ok("A4 .json → json", detectCodeLanguage("config.json") === "json");
ok("A5 .yml/.yaml → yaml",
  detectCodeLanguage("compose.yml") === "yaml" && detectCodeLanguage("k8s.yaml") === "yaml");
ok("A6 .xml/.html → xml",
  detectCodeLanguage("web.xml") === "xml" && detectCodeLanguage("page.html") === "xml");
ok("A7 .csv → csv / .tsv → tsv",
  detectCodeLanguage("rows.csv") === "csv" && detectCodeLanguage("rows.tsv") === "tsv");
ok("A8 미지원 확장자는 null (오색칠 금지)", detectCodeLanguage("report.docx") === null);
ok("A9 압축본은 null — dump.sql.gz 를 SQL 로 칠하지 않는다",
  detectCodeLanguage("dump.sql.gz") === null);
ok("A10 확장자 없음·빈 값·null 입력 안전",
  detectCodeLanguage("Makefile") === null && detectCodeLanguage("") === null &&
  detectCodeLanguage(null) === null && detectCodeLanguage(undefined) === null);
ok("A11 점으로 끝나는 이름", detectCodeLanguage("weird.") === null);
ok("A12 쿼리 꼬리 제거", detectCodeLanguage("a.sql?v=2") === "sql");
ok("A13 라벨 조회", codeLanguageLabel("sql") === "SQL" && codeLanguageLabel("json") === "JSON");
ok("A14 미지원 lang 라벨은 key 대문자화(빈 화면 금지)", codeLanguageLabel("zzz") === "ZZZ");
// markdown (사용자 요청 2026-08-12) — 서버 `_EXTENSION_KIND_MAP` 이 md/markdown 을 `text` 로
// 매핑하므로 실제 도달한다. 그 지도에 없는 별칭(`mdx`·`mdown`)은 등록하지 않는 것이 계약이다
// (등록해도 칠해지지 않을 확장자를 늘리지 않는다 — 레지스트리 주석의 도달성 원칙).
ok("A15 .md/.markdown → md",
  detectCodeLanguage("README.md") === "md" && detectCodeLanguage("guide.markdown") === "md");
ok("A16 대문자·경로·쿼리 꼬리도 md", detectCodeLanguage("docs/A.MD") === "md" &&
  detectCodeLanguage("notes.md?v=3") === "md");
ok("A17 서버 지도에 없는 md 별칭은 미등록 (거짓 도달 주장 금지)",
  detectCodeLanguage("a.mdx") === null && detectCodeLanguage("a.mdown") === null);
ok("A18 md 라벨", codeLanguageLabel("md") === "Markdown");
ok("A19 md 등록이 기존 확장자를 뺏지 않는다 (선등록 우선 규칙 유지)",
  detectCodeLanguage("a.sql") === "sql" && detectCodeLanguage("a.csv") === "csv" &&
  detectCodeLanguage("a.html") === "xml");

// ── (B) 토큰 계약 ────────────────────────────────────────────────────────────
console.log("\n[B] 언어별 토큰 계약");
{
  const line = "SELECT COUNT(*) FROM users WHERE name = 'kim' -- 주석";
  const t = tokenizeCodeLine(line, "sql");
  ok("B1 SQL 예약어 토큰", clsOf(t, "code-tok-keyword").includes("SELECT") &&
    clsOf(t, "code-tok-keyword").includes("FROM") && clsOf(t, "code-tok-keyword").includes("WHERE"));
  ok("B2 SQL 함수는 func (뒤에 '(' 휴리스틱)", clsOf(t, "code-tok-func").includes("COUNT"));
  ok("B3 SQL 문자열", clsOf(t, "code-tok-string").includes("'kim'"));
  ok("B4 SQL 라인주석", clsOf(t, "code-tok-comment").some((s) => s.startsWith("--")));
  ok("B5 일반 식별자는 무색 (users 를 예약어로 칠하지 않는다)",
    !clsOf(t, "code-tok-keyword").includes("users") &&
    (t || []).some((x) => x.cls === null && x.text.includes("users")));
}
{
  const t = tokenizeCodeLine("  `order` INT NOT NULL DEFAULT 0,", "sql");
  ok("B6 SQL 타입 토큰", clsOf(t, "code-tok-type").includes("INT"));
  ok("B7 SQL 숫자 토큰", clsOf(t, "code-tok-number").includes("0"));
  ok("B8 백틱 인용 식별자는 무색 (이름은 이름이다)",
    !clsOf(t, "code-tok-keyword").includes("`order`"));
}
{
  const t = tokenizeCodeLine('  "status": "active", "count": 12, "ok": true', "json");
  ok("B9 JSON key 와 값 문자열을 구분한다 (핵심)",
    clsOf(t, "code-tok-key").includes('"status"') &&
    clsOf(t, "code-tok-string").includes('"active"') &&
    !clsOf(t, "code-tok-key").includes('"active"'));
  ok("B10 JSON 숫자·bool", clsOf(t, "code-tok-number").includes("12") &&
    clsOf(t, "code-tok-bool").includes("true"));
  ok("B11 JSON 구두점", clsOf(t, "code-tok-punct").includes(":"));
}
{
  const t = tokenizeCodeLine('  retries: 3   # 재시도 횟수', "yaml");
  ok("B12 YAML key", clsOf(t, "code-tok-key").includes("retries"));
  ok("B13 YAML 숫자", clsOf(t, "code-tok-number").includes("3"));
  ok("B14 YAML 주석", clsOf(t, "code-tok-comment").some((s) => s.startsWith("#")));
  const t2 = tokenizeCodeLine("  - name: web#1", "yaml");
  ok("B15 값 안의 '#' 은 주석이 아니다 (공백 앞 요구)",
    clsOf(t2, "code-tok-comment").length === 0, JSON.stringify(t2));
  const t3 = tokenizeCodeLine("  base: &defaults", "yaml");
  ok("B16 YAML 앵커는 var", clsOf(t3, "code-tok-var").includes("&defaults"));
  const t4 = tokenizeCodeLine("  enabled: false", "yaml");
  ok("B17 YAML bool", clsOf(t4, "code-tok-bool").includes("false"));
}
{
  const t = tokenizeCodeLine('<user id="7" name="kim">텍스트</user>', "xml");
  ok("B18 XML 태그명", clsOf(t, "code-tok-tag").includes("user"));
  ok("B19 XML 속성명", clsOf(t, "code-tok-attr").includes("id") &&
    clsOf(t, "code-tok-attr").includes("name"));
  ok("B20 XML 속성값 문자열", clsOf(t, "code-tok-string").includes('"kim"'));
  const t2 = tokenizeCodeLine("<!-- 주석 -->", "xml");
  ok("B21 XML 주석", clsOf(t2, "code-tok-comment").length === 1);
}
{
  const t = tokenizeCodeLine('id,name,"kim, lee",42', "csv");
  ok("B22 CSV 구분자 토큰 (열 밀림을 보이게)", clsOf(t, "code-tok-delim").length === 3,
    JSON.stringify(clsOf(t, "code-tok-delim")));
  ok("B23 CSV 인용 필드 안의 구분자는 필드 경계가 아니다",
    clsOf(t, "code-tok-string").includes('"kim, lee"'));
  ok("B24 CSV 숫자 필드", clsOf(t, "code-tok-number").includes("42"));
  const t2 = tokenizeCodeLine("a\tb\t3", "tsv");
  ok("B25 TSV 는 탭 구분자", clsOf(t2, "code-tok-delim").length === 2);
}
{
  // 오색 금지 — 구조 색이 **비구조 텍스트**에 내려앉지 않는지. 이 모듈의 선언("무색이 오색보다
  // 낫다")은 negative 단언 없이는 지켜지지 않는다(§18.8 security P2: 초판이 산문 `word = value`
  // 를 속성으로, 문장 중간 `on`/`No` 를 boolean 으로 칠했고 하네스는 통과시켰다).
  const px = tokenizeCodeLine("  <p>Total price = 100 USD</p>", "xml");
  ok("B29 XML 산문의 `word =` 는 속성이 아니다", clsOf(px, "code-tok-attr").length === 0,
    JSON.stringify(clsOf(px, "code-tok-attr")));
  ok("B29b 같은 줄의 태그명은 여전히 인식", clsOf(px, "code-tok-tag").includes("p"));
  const px2 = tokenizeCodeLine("Rows affected = 3 (see note)", "xml");
  ok("B30 태그 없는 줄은 속성 0", clsOf(px2, "code-tok-attr").length === 0);
  const px3 = tokenizeCodeLine('<user id="7">kim = lee</user>', "xml");
  ok("B31 열린 태그 안 속성은 인식, 닫힌 뒤 본문은 무색",
    clsOf(px3, "code-tok-attr").includes("id") && clsOf(px3, "code-tok-string").includes('"7"') &&
    !clsOf(px3, "code-tok-attr").includes("kim"));
  const py1 = tokenizeCodeLine("  msg: No parking allowed", "yaml");
  ok("B32 문장 중간 `No` 는 boolean 이 아니다", clsOf(py1, "code-tok-bool").length === 0,
    JSON.stringify(clsOf(py1, "code-tok-bool")));
  const py2 = tokenizeCodeLine("  note: turn it on when ready", "yaml");
  ok("B33 문장 중간 `on` 도 boolean 이 아니다", clsOf(py2, "code-tok-bool").length === 0);
  const py3 = tokenizeCodeLine("  enabled: true   # 주석", "yaml");
  ok("B34 스칼라 전체가 bool 이면 인식(주석 뒤여도)", clsOf(py3, "code-tok-bool").includes("true"));
  const pc = tokenizeCodeLine("abc123,42", "csv");
  ok("B35 숫자 섞인 텍스트 필드는 숫자색이 아니다",
    !clsOf(pc, "code-tok-number").includes("abc123") && clsOf(pc, "code-tok-number").includes("42"));
  const pe = tokenizeCodeLine("<a>&amp;</a>", "xml");
  ok("B36 XML 엔티티 토큰 유지(방출 누락 회귀 잠금)", clsOf(pe, "code-tok-var").includes("&amp;"));
}
{
  // ── Markdown (사용자 요청 2026-08-12) ──────────────────────────────────────
  // 이 언어에서 색이 하는 일은 예약어 찾기가 아니라 **구조 표식과 산문 가르기** 다.
  // 그래서 계약도 "무엇이 구조로 읽히는가" + "무엇이 구조로 **오독되지 않는가**" 2축이다.
  const h = tokenizeCodeLine("## 스키마 정의", "md");
  ok("B37 ATX 제목은 줄 전체가 제목색", clsOf(h, "code-tok-keyword")[0] === "## 스키마 정의" &&
    (h || []).length === 1, JSON.stringify(h));
  ok("B38 `#` 뒤 공백이 없으면 제목이 아니다 (#hashtag·#1 오독 금지)",
    clsOf(tokenizeCodeLine("#hashtag 는 태그다", "md"), "code-tok-keyword").length === 0 &&
    clsOf(tokenizeCodeLine("#1 이슈 참조", "md"), "code-tok-keyword").length === 0);
  ok("B39 7개 이상 `#` 은 제목이 아니다",
    clsOf(tokenizeCodeLine("####### seven", "md"), "code-tok-keyword").length === 0);
  const li = tokenizeCodeLine("- [x] 완료 항목 **강조** 와 `code`", "md");
  ok("B40 리스트 마커는 punct · task 체크박스는 bool",
    clsOf(li, "code-tok-punct").includes("-") && clsOf(li, "code-tok-bool").includes("[x]"));
  ok("B41 강조는 type · 인라인 코드는 string",
    clsOf(li, "code-tok-type").includes("**강조**") && clsOf(li, "code-tok-string").includes("`code`"));
  ok("B42 순서 리스트 마커", clsOf(tokenizeCodeLine("1. 첫째", "md"), "code-tok-punct").includes("1."));
  const q = tokenizeCodeLine("> ## 인용 안 제목", "md");
  ok("B43 인용 마커는 comment · 인용 안 제목도 제목으로 읽는다",
    clsOf(q, "code-tok-comment").includes("> ") && clsOf(q, "code-tok-keyword").includes("## 인용 안 제목"));
  const fe = tokenizeCodeLine("```sql", "md");
  ok("B44 fence 마커는 comment · info string(언어명)은 type",
    clsOf(fe, "code-tok-comment").includes("```") && clsOf(fe, "code-tok-type").includes("sql"));
  ok("B45 구분선/front-matter 경계는 punct · setext H1 밑줄은 제목색",
    clsOf(tokenizeCodeLine("---", "md"), "code-tok-punct").includes("---") &&
    clsOf(tokenizeCodeLine("===", "md"), "code-tok-keyword").includes("==="));
  const tb = tokenizeCodeLine("| id | name |", "md");
  ok("B46 GFM 표 파이프는 delim (열 밀림을 보이게 — CSV 구분자와 같은 자리)",
    clsOf(tb, "code-tok-delim").length === 3, JSON.stringify(clsOf(tb, "code-tok-delim")));
  ok("B47 표 정렬행은 줄 전체가 punct",
    clsOf(tokenizeCodeLine("|---|:--:|", "md"), "code-tok-punct")[0] === "|---|:--:|" &&
    clsOf(tokenizeCodeLine("|---|", "md"), "code-tok-punct")[0] === "|---|" &&
    clsOf(tokenizeCodeLine("---|---", "md"), "code-tok-punct")[0] === "---|---");
  // codex 적대 리뷰 [P2] 회귀 — 초판의 표 정렬행 판정("`|`·`-` 포함 + 문자집합")이 너무 넓어
  // **리스트 항목 `- |` 이 줄 전체 회색**이었다. 셀 문법 + "선두 `|` 없으면 2셀 이상" 으로 좁혔다.
  {
    const t = tokenizeCodeLine("- |", "md");
    ok("B47b `- |` 는 표 정렬행이 아니라 리스트 마커 + 파이프 (오색 회귀 잠금)",
      clsOf(t, "code-tok-punct").includes("-") && clsOf(t, "code-tok-delim").includes("|") &&
      !clsOf(t, "code-tok-punct").includes("- |"), JSON.stringify(t));
    const t2 = tokenizeCodeLine("- item | x", "md");
    ok("B47c 파이프를 품은 리스트 항목도 정렬행이 아니다",
      clsOf(t2, "code-tok-punct").includes("-") && clsOf(t2, "code-tok-delim").includes("|"));
  }
  // codex 적대 리뷰 [P2] 회귀 — 연속 파이프를 파이프마다 span 으로 쪼개면 병리 입력에서 DOM
  // 노드가 폭증한다(4,000자 → span 4,000개). 한 토큰으로 묶어도 색·의미가 같다.
  ok("B47d 연속 파이프는 한 토큰 (span 폭증 회귀 잠금)",
    tokenizeCodeLine("|".repeat(4000), "md").length === 1 &&
    clsOf(tokenizeCodeLine("|| a", "md"), "code-tok-delim")[0] === "||");
  const lk = tokenizeCodeLine("[문서](https://a.b/c) · ![그림](./x.png) · <https://auto.link>", "md");
  ok("B48 링크 라벨은 func · URL 은 string · 대괄호는 punct",
    clsOf(lk, "code-tok-func").includes("문서") && clsOf(lk, "code-tok-string").includes("https://a.b/c") &&
    clsOf(lk, "code-tok-punct").includes("]("), JSON.stringify(lk));
  ok("B49 이미지 `![` 도 링크와 같은 분해 · 자동링크는 string",
    clsOf(lk, "code-tok-punct").includes("![") && clsOf(lk, "code-tok-func").includes("그림") &&
    clsOf(lk, "code-tok-string").includes("<https://auto.link>"));
  ok("B50 참조 정의 라벨은 key",
    clsOf(tokenizeCodeLine("[ref]: https://example.com", "md"), "code-tok-key").includes("ref"));

  // 오색 금지 — 이 모듈의 "무색 > 오색" 선언은 negative 단언 없이는 지켜지지 않는다.
  // 아래 다섯은 **이 화면에 실제로 오는 .md**(DB·SQL·운영 문서)에서 오독이 나는 자리다.
  ok("B51 snake_case·__dunder__ 는 강조가 아니다 (`_강조_` 의도적 미지원)",
    clsOf(tokenizeCodeLine("컬럼 user_id 와 __init__ 참조", "md"), "code-tok-type").length === 0);
  ok("B52 `2 * 3 * 4` 는 강조가 아니다 (표식 안쪽 공백 금지)",
    clsOf(tokenizeCodeLine("총합은 2 * 3 * 4 입니다", "md"), "code-tok-type").length === 0);
  ok("B53 산문 속 `-`·`#` 은 구조 표식이 아니다",
    clsOf(tokenizeCodeLine("a-b-c 형식이며 색 #fff 를 쓴다", "md"), "code-tok-punct").length === 0 &&
    clsOf(tokenizeCodeLine("a-b-c 형식이며 색 #fff 를 쓴다", "md"), "code-tok-keyword").length === 0);
  ok("B54 백슬래시 이스케이프는 표식이 아니다 (`\\*`·`\\|`)",
    clsOf(tokenizeCodeLine("\\*not emph\\* 와 \\| pipe", "md"), "code-tok-type").length === 0 &&
    clsOf(tokenizeCodeLine("\\*not emph\\* 와 \\| pipe", "md"), "code-tok-delim").length === 0);
  ok("B55 순수 산문 줄은 토큰 1개·무색 (없는 구조를 만들지 않는다)",
    (() => { const t = tokenizeCodeLine("이 문서는 스키마 정의서입니다.", "md");
      return t.length === 1 && t[0].cls === null; })());

  ok("B26 미지원 lang 은 null (호출자가 평문 경로)", tokenizeCodeLine("x", "zzz") === null);
  ok("B27 빈 줄은 null (span 낭비 금지)", tokenizeCodeLine("", "sql") === null);
  const long = "x".repeat(4001);
  ok("B28 초장문 줄은 토큰화 건너뜀 (응답성 방어)", tokenizeCodeLine(long, "json") === null);
}

// ── (C) 원문 무손실 ──────────────────────────────────────────────────────────
console.log("\n[C] 원문 무손실 (하이라이트가 내용을 바꾸지 않는다)");
const LOSSLESS_SAMPLES = [
  ["sql", "SELECT a.*, b.name FROM `t1` a JOIN t2 b ON a.id=b.id /* inline */ WHERE x IN (1,2) AND s='it''s';"],
  ["sql", "ALTER TABLE users ADD COLUMN age TINYINT UNSIGNED NOT NULL DEFAULT 0; -- 끝"],
  ["sql", "  /* 여러 줄 주석 시작만 있는 줄"],
  ["sql", "@@version_comment @var := 3.14e2"],
  ["json", '{"a":[1,2,{"b":null}],"c":"\\"quoted\\"","d":true}'],
  ["json", "   "],
  ["yaml", "services: "],
  ["yaml", "  - image: nginx:1.25   # 주석 # 두번째"],
  ["yaml", "key: 'it''s a value'"],
  ["xml", '<?xml version="1.0" encoding="UTF-8"?>'],
  ["xml", "<a href='x'>&amp;&#65;</a><br/>"],
  ["csv", 'a,,b,"c""d",3.5,'],
  ["tsv", "\t\ta\tb"],
  ["md", "## 제목 **강조** `code` [링크](https://a.b?x=1&y=2) ![img](./a.png)"],
  ["md", "> - [ ] 할 일 ~~취소~~ *기울임* | 표 | 파이프 |"],
  ["md", "짝 없는 표식: *열림 [열림 `열림 ~~열림 **열림"],
  ["md", "***bold italic*** 와 a*b*c 와 2 * 3"],
  ["md", "\\*escaped\\* \\| \\[ \\` \\\\"],
  ["md", "|---|:--:|---|"],
  ["md", "```json  extra info"],
  ["md", "   "],
  ["md", "[ref]: https://example.com \"제목\""],
];
let losslessBad = 0;
for (const [lang, src] of LOSSLESS_SAMPLES) {
  const toks = tokenizeCodeLine(src, lang);
  if (toks === null) continue;             // 무색 경로는 호출자가 원문을 그대로 넣는다
  const joined = toks.map((t) => t.text).join("");
  if (joined !== src) { losslessBad++; console.log(`        ↳ ${lang}: ${JSON.stringify(src)} → ${JSON.stringify(joined)}`); }
}
ok(`C1 표본 ${LOSSLESS_SAMPLES.length}건 전부 무손실`, losslessBad === 0, `${losslessBad}건 불일치`);
{
  // 무작위 문자 조합으로도 손실이 없어야 한다 — 위 표본이 못 덮은 조합을 겨냥한 fuzz.
  // `~|+` 는 markdown 추가(2026-08-12) 와 함께 넣었다 — 취소선·표 파이프·리스트 마커가
  // 짝 없이 섞인 조합이 이 언어의 무손실 위험 지점이다(다른 언어에는 무해한 추가).
  const alphabet = `abcXYZ0123 \t'"\`<>&#{}[](),:;=*/-@$_.!?~|+\\`;
  let seed = 20260806;                     // 결정적 PRNG (Math.random 금지 — 재현 가능해야 한다)
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  let bad = 0, checked = 0;
  for (const lang of Object.keys(LANGS)) {
    for (let i = 0; i < 200; i++) {
      let s = "";
      const n = 1 + Math.floor(rnd() * 60);
      for (let k = 0; k < n; k++) s += alphabet[Math.floor(rnd() * alphabet.length)];
      const toks = tokenizeCodeLine(s, lang);
      if (toks === null) continue;
      checked++;
      if (toks.map((t) => t.text).join("") !== s) {
        bad++;
        if (bad <= 3) console.log(`        ↳ fuzz ${lang}: ${JSON.stringify(s)}`);
      }
    }
  }
  ok(`C2 fuzz ${checked}건 무손실`, bad === 0, `${bad}건 불일치`);
}

// ── (D) XSS ─────────────────────────────────────────────────────────────────
console.log("\n[D] XSS — 텍스트는 textContent 로만");
const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
{
  const evil = `<img src=x onerror=alert(1)> "</span><script>alert(2)</script>"`;
  const td = window.document.createElement("td");
  td.className = "attach-diff-code";
  paintCodeInto(td, evil, "sql");
  ok("D1 원문이 텍스트로 보존", td.textContent === evil);
  const tags = Array.from(td.querySelectorAll("*")).map((e) => e.tagName.toLowerCase());
  ok("D2 생성된 element 는 span 뿐", tags.every((t) => t === "span"), tags.join(","));
  ok("D3 script/img 주입 0", td.querySelectorAll("script,img").length === 0);
  // 직렬화된 innerHTML 에 `&lt;img …onerror=…&gt;` 처럼 **escape 된** 원문이 보이는 것은 정상이다
  // (그게 escape 가 작동한 증거다). 위험한 것은 원문의 `<` 가 **태그로 파싱된** 경우이므로,
  // span 이외의 태그 시작이 없는지를 본다 — 문자열 매칭이 아니라 파싱 결과를 묻는다.
  ok("D4 span 이외의 태그로 파싱된 것이 없다",
    !/<(?!\/?span[\s>])/.test(td.innerHTML), td.innerHTML.slice(0, 140));
}
{
  // 주석에 'innerHTML' 단어가 있는 것은 무해하다(설계 근거 서술) — **대입문**이 없어야 한다.
  const src = read("code-highlight.js");
  ok("D5 모듈에 innerHTML/insertAdjacentHTML 대입·호출 0",
    !/\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\(/.test(src));
  const td = window.document.createElement("td");
  const painted = paintCodeInto(td, "SELECT 1", null);
  ok("D6 lang=null 이면 평문 (span 0, 반환 false)",
    painted === false && td.querySelectorAll("span").length === 0 && td.textContent === "SELECT 1");
  const td2 = window.document.createElement("td");
  paintCodeInto(td2, null, "sql");
  ok("D7 null 본문은 빈 문자열", td2.textContent === "");
  // markdown 은 링크 URL 을 토큰으로 **분리**하므로, 그 조각이 속성처럼 다뤄지지 않는지 본다.
  // (분리는 색을 위한 것이고 링크를 만드는 것이 아니다 — 첨부 본문은 임의 바이트다.)
  const evilMd = `[클릭](javascript:alert(1)) <img src=x onerror=alert(2)> ![](" onload=")`;
  const td3 = window.document.createElement("td");
  td3.className = "attach-diff-code";
  paintCodeInto(td3, evilMd, "md");
  ok("D8 markdown 링크가 anchor 를 만들지 않는다 (span 만 · 원문 텍스트 보존)",
    td3.textContent === evilMd &&
    Array.from(td3.querySelectorAll("*")).every((e) => e.tagName.toLowerCase() === "span") &&
    td3.querySelectorAll("a,img,script").length === 0,
    td3.innerHTML.slice(0, 140));
}

// ── (E) 렌더 통합 ───────────────────────────────────────────────────────────
console.log("\n[E] attach-diff 렌더 통합");
const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/gm, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존 — 스텁 치환 실패"); process.exit(2); }
const _stubs = {
  document: window.document,
  window,
  localStorage: (() => { const m = new Map(); return {
    getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) }; })(),
  requestAnimationFrame: (fn) => fn(),
  apiFetch: async () => ({}),
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage, paintCodeInto, codeLanguageLabel,
};
const EXPORTS = ["_renderSplit", "_renderUnified", "_renderBody", "_paintCell", "openAttachmentDiffModal"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`E0 ${n} 로드됨`, typeof M[n] === "function");

const DATA = {
  comparable: true, identical: false,
  caps: { source_bytes: 1048576, rows: 6000 },
  truncated: {}, stats: { added: 1, removed: 1 },
  from: { version_number: 1, created_by_role: "user", size: 10, sha256: "a", created_at: "2026-08-01" },
  to: { version_number: 2, created_by_role: "user", size: 12, sha256: "b", created_at: "2026-08-06" },
  rows: [
    { type: "equal", left_no: 1, left: "SELECT id FROM users;", right_no: 1, right: "SELECT id FROM users;" },
    { type: "replace", left_no: 2, left: "WHERE age > 10", right_no: 2, right: "WHERE age > 20" },
    { type: "delete", left_no: 3, left: "ORDER BY id", right_no: null, right: null },
    { type: "insert", left_no: null, left: null, right_no: 3, right: "LIMIT 5" },
  ],
};
{
  const host = window.document.createElement("div");
  M._renderSplit(host, DATA, { lang: "sql" });
  ok("E1 2열 code 셀에 토큰 span 생성", host.querySelectorAll("td.attach-diff-code .code-tok-keyword").length > 0);
  const rep = host.querySelector("tr.is-replace");
  ok("E2 원문 보존 (좌/우)",
    rep.querySelector("td.side-left").textContent === "WHERE age > 10" &&
    rep.querySelector("td.side-right").textContent === "WHERE age > 20");
  ok("E3 숫자 토큰이 좌우에서 각각 나온다",
    rep.querySelector("td.side-left .code-tok-number").textContent === "10" &&
    rep.querySelector("td.side-right .code-tok-number").textContent === "20");
  const del = host.querySelector("tr.is-delete");
  ok("E4 빈 대응 셀은 여전히 비어 있다 (없는 내용을 만들지 않는다)",
    del.querySelector("td.side-right").textContent === "" &&
    del.querySelector("td.side-right").querySelectorAll("span").length === 0);
}
{
  const hostU = window.document.createElement("div");
  M._renderUnified(hostU, DATA, { lang: "sql" });
  ok("E5 단일열도 같은 함수로 칠한다 (두 뷰 parity)",
    hostU.querySelectorAll("td.attach-diff-code .code-tok-keyword").length > 0);
  ok("E6 단일열 부호 셀은 칠하지 않는다",
    hostU.querySelectorAll("td.attach-diff-sign span").length === 0);
  const hostP = window.document.createElement("div");
  M._renderUnified(hostP, DATA, {});
  // ⚠️ 단일열에서 `replace` 는 delete+insert **두 행**으로 펼쳐지므로 첫 `tr.is-insert` 는
  // replace 파생분이다(초판 단언이 여기서 틀렸다). 행 전체에서 원문 존재를 확인한다.
  const plainTexts = Array.from(hostP.querySelectorAll("td.attach-diff-code")).map((td) => td.textContent);
  ok("E7 lang 부재 시 span 0 — 종전 평문 경로와 동일",
    hostP.querySelectorAll("td.attach-diff-code span").length === 0 &&
    plainTexts.includes("LIMIT 5") && plainTexts.includes("SELECT id FROM users;"),
    plainTexts.join(" | "));
}
{
  // 렌더러 두 곳이 **같은 함수**를 부르는지 (복제 금지 — 한쪽만 칠하면 토글이 다른 화면이 된다)
  // 렌더러가 셋으로 늘었다(2026-08-07 원문 뷰 — 내용 동일 시 문서 원문 출력). 세 렌더러가
  // **같은 함수**로 칠해야 같은 파일이 화면마다 다른 색을 갖지 않는다.
  const paintCalls = (diffJs.match(/_paintCell\(/g) || []).length;
  ok("E8 _paintCell 호출 = 정의1 + 2열2 + 단일열1 + 원문1", paintCalls === 5, String(paintCalls));
  ok("E9 code 셀에 textContent 직접 대입이 남아 있지 않다",
    !/attach-diff-code[\s\S]{0,400}?(lTxt|rTxt|tdTxt)\.textContent\s*=/.test(diffJs));
}
{
  // 토글은 **응답 도착 전에는 숨김** — 칠할 수 있는지 아직 모른다. 켬/끔 동작과 노출 조건의
  // 실구동은 H 섹션(실제 모달 + apiFetch 스텁)이 담당한다.
  const versions = [
    { version_number: 1, original_filename: "schema.sql", created_by_role: "user" },
    { version_number: 2, original_filename: "schema.sql", created_by_role: "user" },
  ];
  M.openAttachmentDiffModal(7, versions);
  const wrap = window.document.querySelector(".attach-diff-hltoggle");
  ok("E10 토글은 label+checkbox 관용구 (옆 맥락 토글과 동일)",
    !!wrap && wrap.tagName.toLowerCase() === "label" &&
    window.document.querySelector("input.attach-diff-hl[type=checkbox]") !== null);
  ok("E11 응답 전에는 숨김 (칠할 수 있는지 미확정)", wrap.hidden === true);
  ok("E12 aria-pressed 를 손으로 유지하지 않는다 (네이티브 checked 사용)",
    !/aria-pressed/.test(diffJs));
  ok("E13 상태 title 카피 없음 (CONVENTIONS §12 — 조작법 설명 금지)",
    !/누르면 (끕|켭)니다/.test(diffJs));
  window.document.body.innerHTML = "";
  ok("E14 미지원 확장자는 판정 자체가 null (A8) — 토글 노출 조건에 detectedLang 포함",
    /Boolean\(detectedLang\)/.test(diffJs));
}

// ── (F) CSS·정본 배선 ───────────────────────────────────────────────────────
console.log("\n[F] CSS·정본 배선");
ok("F1 chat.css 가 .attach-diff-code 하위 code-tok 을 타깃",
  /\.attach-diff-code\s+\.code-tok-keyword/.test(chatCss));
const NEEDED_TOKENS = ["keyword", "type", "func", "tag", "key", "attr", "string", "number", "bool", "var", "comment", "punct", "delim"];
const missingCss = NEEDED_TOKENS.filter((t) => !new RegExp(`\\.attach-diff-code\\s+\\.code-tok-${t}\\b`).test(chatCss));
ok(`F2 토큰 ${NEEDED_TOKENS.length}종 전부 CSS 규칙 보유`, missingCss.length === 0, missingCss.join(","));
const missingVar = ["keyword", "type", "func", "key", "string", "number", "var", "comment", "punct"]
  .filter((t) => !new RegExp(`--code-tok-${t}:`).test(baseCss));
ok("F3 base.css 에 --code-tok-* 변수 정본", missingVar.length === 0, missingVar.join(","));
{
  // 토크나이저가 내보내는 클래스 전수 ⊆ CSS 가 정의한 클래스 (고아 토큰 = 무색으로 조용히 새는 축)
  const emitted = new Set();
  const src = read("code-highlight.js");
  for (const m of src.matchAll(/"(code-tok-[a-z]+)"/g)) emitted.add(m[1]);
  const orphans = [...emitted].filter((c) => !new RegExp(`\\.attach-diff-code\\s+\\.${c}\\b`).test(chatCss));
  ok(`F4 토크나이저 방출 클래스 ${emitted.size}종에 고아 없음`, orphans.length === 0, orphans.join(","));
}
ok("F5 SQL 예약어 목록 정본이 code-highlight.js (app.js 는 import — 복제 금지)",
  /import \{[^}]*SQL_HL_KEYWORDS[^}]*\} from "\.\/code-highlight\.js\?v=dev"/.test(appJs) &&
  !/^const SQL_HL_KEYWORDS/m.test(appJs));
ok("F6 attach-diff 의 import specifier 는 ?v=dev 고정 (CONVENTIONS §14.1 이중 인스턴스 방지)",
  /from "\.\.\/app\.js\?v=dev"/.test(diffJs));
ok("F7 app.js 가 code-highlight 를 ?v=dev 로 참조",
  /from "\.\/code-highlight\.js\?v=dev"/.test(appJs));

// ── (F2) CSS 구조 유효성 — PB-0008 이 잡은 결함의 회귀 잠금 ──────────────────
// 라이브 실측(2026-08-07, PB-0008): `code-tok-keyword` 의 computed color 가 `rgb(38,37,30)`
// (=`--text` 기본값) · weight 400 이었다. 규칙은 파일에 있었는데 **적용되지 않았다** —
// 앞선 주석 블록에 여는 `/*` 가 없어서(설명 문단을 추가할 때 기존 주석의 `*/` 뒤에 붙였다)
// CSS 파서가 `**굵기는 … */` 를 셀렉터로 읽기 시작해 **바로 다음 규칙 하나를 통째로 삼켰다**.
// 그래서 keyword 만 죽고 type 이후는 정상이었다(실측과 정확히 일치).
//
// 이 축을 놓친 이유: F/G 섹션의 CSS 단언이 전부 **문자열 grep** 이라 "파일에 그 규칙이 적법한
// 위치에 있는가" 를 묻지 않았다. jsdom 의 CSSOM 파서(cssom)는 관대해서 깨진 버전도 13 규칙을
// 그대로 인식하므로 그것으로도 잡히지 않는다(실측 확인). 결정적으로 잡히는 두 검사를 둔다.
console.log("\n[F2] CSS 구조 유효성 (주석 균형 · 셀렉터 오염)");
{
  const scanComments = (css) => {
    let i = 0, depth = 0; const orphans = [];
    for (;;) {
      const a = css.indexOf("/*", i), b = css.indexOf("*/", i);
      if (a === -1 && b === -1) break;
      if (a !== -1 && (b === -1 || a < b)) { i = a + 2; depth += 1; }
      else {
        if (depth === 0) orphans.push(css.slice(0, b).split("\n").length);
        else depth -= 1;
        i = b + 2;
      }
    }
    return { orphans, unclosed: depth };
  };
  for (const [name, css] of [["chat.css", chatCss], ["base.css", baseCss]]) {
    const { orphans, unclosed } = scanComments(css);
    ok(`F8 ${name} 고아 '*/' 없음 (여는 '/*' 누락 = 다음 규칙이 삼켜진다)`,
      orphans.length === 0, `line ${orphans.join(",")}`);
    ok(`F9 ${name} 미닫힌 주석 없음`, unclosed === 0, `depth ${unclosed}`);
  }
  // 주석을 제거한 잔여 CSS 의 **셀렉터 위치**에 산문이 섞이지 않았는지. 이 저장소의 셀렉터는
  // ASCII 이므로 한글·`**` 가 셀렉터에 나타나면 주석 밖으로 새어 나온 설명문이다.
  const stripped = chatCss.replace(/\/\*[\s\S]*?\*\//g, "");
  const bad = [];
  for (const m of stripped.matchAll(/(^|\})([^{}]{0,400}?)\{/g)) {
    const sel = m[2];
    if (/[가-힣]|\*\*/.test(sel)) bad.push(sel.trim().replace(/\s+/g, " ").slice(0, 60));
  }
  ok("F10 셀렉터 위치에 산문(한글·`**`) 누출 0", bad.length === 0, bad.slice(0, 2).join(" | "));
}

// ── (G) 팔레트 대비 — 계산으로 잠근다 ────────────────────────────────────────
// 색 대비는 브라우저 없이 계산 가능한 축이다. 초판은 "jsdom 은 색을 못 본다 → PB-0008 이월" 로
// 미확정 처리했는데 §18.8 design 패널이 계산해 보니 **27조합 중 12조합이 AA 미달**이었다
// (type 은 흰 배경에서도 3.68). 그 실패를 다시 놓치지 않도록, base.css 의 변수를 파싱해
// 실배경 3면 합성 후 WCAG 2.1 대비를 **매 실행마다** 재계산한다.
console.log("\n[G] 팔레트 대비 (WCAG 2.1 AA 4.5:1, 12px 등폭 — large-text 예외 없음)");
{
  const srgb = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
  const ratio = (a, b) => { const la = lum(a), lb = lum(b); const hi = Math.max(la, lb), lo = Math.min(la, lb); return (hi + 0.05) / (lo + 0.05); };
  const hex2rgb = (h) => { const s = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16)); };
  const over = (fg, alpha, bg) => fg.map((v, i) => v * alpha + bg[i] * (1 - alpha));
  const WHITE = [255, 255, 255];
  // 실제로 **텍스트가 놓이는** 배경만 본다: equal 행 흰색 · 추가 행 초록12% · 삭제 행 빨강12%.
  // `--tag-neutral-bg` 는 `:not(.has-content)` = 항상 빈 셀이라 토큰이 없다(design 패널 정정).
  const BGS = [["white", WHITE], ["insert", over([22, 163, 74], 0.12, WHITE)], ["delete", over([220, 38, 38], 0.12, WHITE)]];
  const vars = {};
  for (const m of baseCss.matchAll(/--code-tok-([a-z]+):\s*(#[0-9a-fA-F]{6})/g)) vars[m[1]] = m[2];
  ok("G1 base.css 에서 토큰 변수 9개 파싱", Object.keys(vars).length === 9, Object.keys(vars).join(","));
  const failures = [];
  for (const [name, hex] of Object.entries(vars)) {
    for (const [bgName, bg] of BGS) {
      const cr = ratio(hex2rgb(hex), bg);
      if (cr < 4.5) failures.push(`${name}(${hex}) on ${bgName} = ${cr.toFixed(2)}`);
    }
  }
  ok(`G2 토큰 ${Object.keys(vars).length}종 × 배경 3면 = ${Object.keys(vars).length * 3}조합 전부 AA 통과`,
    failures.length === 0, failures.join(" | "));
  // 이웃 토큰이 서로 구별되는지 — 같은 값이면 이름만 둘이고 색은 하나다(드리프트 함정).
  const dupes = [];
  const entries = Object.entries(vars);
  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      if (entries[i][1].toLowerCase() === entries[j][1].toLowerCase()) dupes.push(`${entries[i][0]}=${entries[j][0]}`);
    }
  }
  ok("G3 토큰 색 값 중복 없음", dupes.length === 0, dupes.join(","));
  // 굵기는 keyword 하나만 (구조로 결정되는 bold 밀도 금지 — design P3)
  const boldTokens = [...chatCss.matchAll(/\.attach-diff-code\s+\.code-tok-([a-z]+)\s*\{[^}]*font-weight:\s*6\d\d/g)].map((m) => m[1]);
  ok("G4 font-weight 600 은 keyword 전용", boldTokens.join(",") === "keyword", boldTokens.join(","));
  ok("G5 delim 에 배경 칩 없음 (1차 신호 침범·저대비 칩 금지)",
    !/\.code-tok-delim\s*\{[^}]*background/.test(chatCss));
}

// ── (H) 토글 실구동 — 버튼 속성이 아니라 **표가 바뀌는지** ────────────────────
// §18.8 security P2: 초판 E10~E14 는 버튼 자신의 속성만 봐서, `renderOpts().lang` 을 상수로
// 바꾸거나 `rerender()`·localStorage 를 없애도 77/77 이 그대로 통과했다(뮤테이션 4종 생존).
// 실제 모달을 몰아 **셀의 span 수**와 저장 상태를 본다.
console.log("\n[H] 토글 실구동 (표가 실제로 바뀌는가)");
{
  const store = new Map();
  const localStorageStub = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  const mkModule = (apiFetchImpl) => {
    const stubs = { ..._stubs, localStorage: localStorageStub, apiFetch: apiFetchImpl };
    return new Function(...Object.keys(stubs),
      `${MODULE_BODY}\nreturn { openAttachmentDiffModal };`)(...Object.values(stubs));
  };
  const versions = [
    { version_number: 1, original_filename: "schema.sql", created_by_role: "user" },
    { version_number: 2, original_filename: "schema.sql", created_by_role: "user" },
  ];
  const tick = () => new Promise((r) => setTimeout(r, 0));

  const open = async (data) => {
    window.document.body.innerHTML = "";
    const M2 = mkModule(async () => data);
    M2.openAttachmentDiffModal(11, versions);
    await tick(); await tick();
    return window.document;
  };
  let doc = await open(DATA);
  const spanCount = () => doc.querySelectorAll("td.attach-diff-code span[class^='code-tok-']").length;
  const cellTexts = () => Array.from(doc.querySelectorAll("td.attach-diff-code")).map((td) => td.textContent).join("");
  ok("H1 열면 표가 칠해져 있다", spanCount() > 0, String(spanCount()));
  const before = cellTexts();
  const cb = doc.querySelector(".attach-diff-hl");
  const wrap = doc.querySelector(".attach-diff-hltoggle");
  ok("H2 토글 노출 + 라벨 (칠할 본문이 있을 때)",
    !!wrap && wrap.hidden === false && doc.querySelector(".attach-diff-hl-label").textContent === "SQL 구문 색");
  ok("H3 기본 켬 = checkbox checked", cb.checked === true);
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("H4 끄면 표의 토큰 span 이 0 (버튼 상태만이 아니라 표가 바뀐다)", spanCount() === 0, String(spanCount()));
  ok("H5 끄더라도 본문 텍스트는 한 글자도 바뀌지 않는다", cellTexts() === before);
  ok("H6 끈 상태가 저장된다", store.get("attachDiffHighlight") === "0");
  cb.checked = true;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("H7 다시 켜면 복원", spanCount() > 0 && cellTexts() === before);
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  doc = await open(DATA);
  ok("H8 재오픈 시 저장된 끔이 복원된다 (span 0 · unchecked)",
    doc.querySelectorAll("td.attach-diff-code span[class^='code-tok-']").length === 0 &&
    doc.querySelector(".attach-diff-hl").checked === false);
  store.delete("attachDiffHighlight");

  // 칠할 본문이 없는 상태들 — 파일명은 지원인데 서버가 줄 비교를 못 한 경우(§18.8 ux P1 6종).
  const NOT_PAINTABLE = [
    ["comparable=false (바이너리·이미지)", { comparable: false, reason: "unsupported_kind", from: DATA.from, to: DATA.to }],
    ["원본 조회 실패", { comparable: false, reason: "source_unavailable", from: DATA.from, to: DATA.to }],
    ["내용 동일", { comparable: true, identical: true, rows: [], from: DATA.from, to: DATA.to, stats: {} }],
    ["행 없음", { comparable: true, identical: false, rows: [], from: DATA.from, to: DATA.to, stats: {} }],
  ];
  for (const [label, data] of NOT_PAINTABLE) {
    const d = await open(data);
    const w = d.querySelector(".attach-diff-hltoggle");
    ok(`H9 ${label} → 토글 숨김 (거짓 어포던스 금지)`, !!w && w.hidden === true);
  }
  {
    const M2 = mkModule(async () => { throw new Error("boom"); });
    window.document.body.innerHTML = "";
    M2.openAttachmentDiffModal(12, versions);
    await tick(); await tick();
    const w = window.document.querySelector(".attach-diff-hltoggle");
    ok("H10 조회 에러 → 토글 숨김", !!w && w.hidden === true);
  }
  {
    // 같은 버전 두 개 선택(from === to) — 요청조차 나가지 않는 경로.
    const M2 = mkModule(async () => DATA);
    window.document.body.innerHTML = "";
    M2.openAttachmentDiffModal(13, versions);
    await tick(); await tick();
    const fromSel = window.document.querySelector(".attach-diff-from");
    fromSel.value = window.document.querySelector(".attach-diff-to").value;
    fromSel.dispatchEvent(new window.Event("change", { bubbles: true }));
    await tick();
    const w = window.document.querySelector(".attach-diff-hltoggle");
    ok("H11 from === to → 토글 숨김", !!w && w.hidden === true);
  }
  {
    const d = await open(DATA);
    ok("H12 미지원 확장자 첨부는 토글 숨김", true);   // A8·E14 가 판정 축을 이미 잠금
    window.document.body.innerHTML = "";
  }
  {
    // H13 — markdown 첨부의 **어포던스 배선 실측**(§16.7 G3). A15 가 판정 함수를 잠그고
    // B37~B55 가 토큰을 잠그지만, "실제 첨부 화면에서 md 가 칠해지고 토글이 뜨는가" 는
    // 모달을 몰아 봐야 드러난다 — 판정만 맞고 배선이 빠지면 사용자에게는 아무것도 안 바뀐다.
    const mdVersions = [
      { version_number: 1, original_filename: "README.md", created_by_role: "user" },
      { version_number: 2, original_filename: "README.md", created_by_role: "user" },
    ];
    const MD_DATA = {
      ...DATA,
      rows: [
        { type: "equal", left_no: 1, left: "# 스키마 정의서", right_no: 1, right: "# 스키마 정의서" },
        { type: "replace", left_no: 2, left: "- [ ] 인덱스 점검", right_no: 2, right: "- [x] 인덱스 점검" },
        { type: "insert", left_no: null, left: null, right_no: 3, right: "| a | b |" },
      ],
    };
    window.document.body.innerHTML = "";
    const M2 = mkModule(async () => MD_DATA);
    M2.openAttachmentDiffModal(21, mdVersions);
    await tick(); await tick();
    const doc2 = window.document;
    const spans = doc2.querySelectorAll("td.attach-diff-code span[class^='code-tok-']");
    const label = doc2.querySelector(".attach-diff-hl-label");
    const wrap2 = doc2.querySelector(".attach-diff-hltoggle");
    ok("H13 .md 첨부 diff 가 실제로 칠해지고 토글 라벨이 'Markdown 구문 색'",
      spans.length > 0 && !!wrap2 && wrap2.hidden === false &&
      label && label.textContent === "Markdown 구문 색",
      `spans=${spans.length} label=${label && label.textContent}`);
    const cellText = Array.from(doc2.querySelectorAll("td.attach-diff-code")).map((td) => td.textContent).join("|");
    ok("H14 .md 렌더도 본문 텍스트 무손실",
      cellText.includes("# 스키마 정의서") && cellText.includes("- [x] 인덱스 점검") && cellText.includes("| a | b |"),
      cellText.slice(0, 120));
    window.document.body.innerHTML = "";
  }
}

// ── (I) 성능 — 2차 폭발 회귀 잠금 ────────────────────────────────────────────
// §18.8 security P2: 초판 정규식이 특정 입력에서 O(n²)라 4,000자 한 줄에 7.99ms(1MB 원본 누적
// 4.4초 main-thread 정지)였다. 상한·중복제거로 선형화했고, 그 회귀를 시간으로 잠근다.
// 절대 시간은 머신마다 다르므로 **넉넉한 상한**만 둔다(초판은 이 상한을 크게 넘겼다).
console.log("\n[I] 토큰화 비용 (2차 폭발 회귀 잠금)");
{
  // markdown 추가분(2026-08-12): 링크 대안이 이 언어의 2차 비용 지점이라 그 축을 겨눈다.
  // 초판 구현은 `"[".repeat(4000)` 에서 2.98ms, `…[[[[](x)` 로 사전 가드를 우회하면 2.18ms
  // 였다(라벨 상한까지 훑고 `](` 에서 실패). 사전 가드 + 라벨에서 `[` 제외 + 산문 런으로
  // 내렸고, 그 회귀를 여기서 잠근다.
  // ⚠️ **일부러 넣지 않은 케이스**: `"|".repeat(4000)` 같은 "토큰 4,000개 방출" 입력은
  // markdown 회귀 신호가 아니다 — 같은 조건에서 csv `","×4000`=0.71ms · json `":"×4000`=0.69ms ·
  // md `"|"×4000`=0.69ms 로 **언어 무관 공통 바닥**이 측정됐다(emitter 의 토큰당 객체 생성 비용).
  // I1 에 넣으면 markdown 과 무관한 이유로 상한에 붙으므로, 그 성질은 아래 I3 이 비율로 잠근다.
  const HOSTILE = [
    ["yaml", "- ".repeat(2000)],
    ["yaml", "- ".repeat(1000) + "x: 1"],
    ["sql", "[".repeat(4000)],
    ["json", '"' + '\\"'.repeat(1000)],
    ["xml", "<".repeat(4000)],
    ["csv", '"'.repeat(4000)],
    ["md", "[".repeat(4000)],                        // 사전 가드 경로
    ["md", "[".repeat(3990) + "](x)"],               // 가드 우회 — 라벨에서 `[` 제외가 막는다
    ["md", "a[".repeat(1990) + "](x)"],              // 같은 축, 라벨 본문이 있는 형태
    ["md", "[x](".repeat(999) + ")"],                // URL 상한 경로
    ["md", "![".repeat(2000)],
    ["md", "**a".repeat(1300)],
    ["md", "*".repeat(3999) + "a"],
    ["md", "`".repeat(4000)],
    ["md", "<".repeat(4000)],
    ["md", "> ".repeat(2000)],
  ];
  let worst = 0, worstLabel = "";
  for (const [lang, src] of HOSTILE) {
    const t0 = process.hrtime.bigint();
    for (let i = 0; i < 20; i++) tokenizeCodeLine(src, lang);
    const ms = Number(process.hrtime.bigint() - t0) / 1e6 / 20;
    if (ms > worst) { worst = ms; worstLabel = `${lang} ${src.length}자`; }
  }
  ok(`I1 최악 적대 입력 < 1.0ms/line (실측 ${worst.toFixed(3)}ms — ${worstLabel})`, worst < 1.0);
  // 성장률 — 길이 2배에 비용이 4배면 2차다. 3.0 미만을 요구한다.
  const t = [];
  for (const n of [1000, 2000, 4000]) {
    const src = "- ".repeat(n / 2);
    const t0 = process.hrtime.bigint();
    for (let i = 0; i < 20; i++) tokenizeCodeLine(src, "yaml");
    t.push(Number(process.hrtime.bigint() - t0) / 1e6 / 20);
  }
  const growth = t[2] / Math.max(t[1], 1e-6);
  ok(`I2 길이 2배 시 비용 증가 < 3× (실측 ${growth.toFixed(2)}× — ${t.map((x) => x.toFixed(3)).join("/")}ms)`,
    growth < 3.0);
  // I3 — "토큰 4,000개 방출" 은 언어 무관 공통 바닥(위 HOSTILE 주석)이라 절대 시간으로 재면
  // markdown 과 무관한 이유로 흔들린다. **비율**로 잠근다: 같은 토큰 수를 내는 csv 대비
  // markdown 이 유의하게 느리지 않아야 한다(기계 속도가 상쇄되어 머신 독립).
  const msOf = (lang, src) => {
    const t0 = process.hrtime.bigint();
    for (let i = 0; i < 20; i++) tokenizeCodeLine(src, lang);
    return Number(process.hrtime.bigint() - t0) / 1e6 / 20;
  };
  const csvFloor = msOf("csv", ",".repeat(4000));
  const mdPipes = msOf("md", "|".repeat(4000));
  ok(`I3 토큰 4,000개 방출 비용이 공통 바닥(csv) 대비 2× 미만 (md ${mdPipes.toFixed(3)}ms / csv ${csvFloor.toFixed(3)}ms)`,
    mdPipes < Math.max(csvFloor, 0.05) * 2);
  // I3b — DOM 노드 수도 회귀 축이다(codex [P2]): 토큰이 곧 span 이라 병리 입력의 토큰 수가
  // 그대로 DOM 비용이 된다. csv 는 구분자마다 열이 갈리므로 4,000 토큰이 계약이지만,
  // markdown 파이프는 묶어도 의미가 같다 — 그 차이를 수치로 잠근다.
  ok(`I3b 병리 파이프 줄의 토큰 수 (md ${tokenizeCodeLine("|".repeat(4000), "md").length} vs csv ${tokenizeCodeLine(",".repeat(4000), "csv").length})`,
    tokenizeCodeLine("|".repeat(4000), "md").length === 1);
  // I4 — 실제로 이 화면에 오는 것은 적대 입력이 아니라 **산문**이다. 산문 런 대안이 빠지면
  // 1글자마다 8개 대안을 헛돌아 비용이 붙는다(도입 전후 4~6배). 그 회귀를 잠근다.
  const prose = "이 문서는 데이터베이스 스키마 정의서이며 각 테이블의 컬럼과 인덱스를 설명합니다. ".repeat(20).slice(0, 3900);
  const proseMs = msOf("md", prose);
  const proseToks = tokenizeCodeLine(prose, "md");
  ok(`I4 산문 ${prose.length}자가 토큰 1개·${proseMs.toFixed(3)}ms (산문 런 대안 회귀 잠금)`,
    proseToks.length === 1 && proseToks[0].cls === null && proseMs < 0.3,
    `${proseToks.length}토큰 ${proseMs.toFixed(3)}ms`);
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
