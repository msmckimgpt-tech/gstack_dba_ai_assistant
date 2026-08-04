// verify_profile_icon_consistency.mjs
// TASK profile-icon-consistency 의 frontend 변경 4건을 jsdom 으로 격리 검증한다.
//   1. admin.js / app.js 가 동일한 identiconSvg/applyAvatar 헬퍼를 갖는다(정합).
//   2. 대화 드롭업 항목 레이아웃 순서: dot → icon → label → ds (사용자 요청 순서).
//   3. 제품 아이콘 미설정 시 Identicon SVG 폴백(이니셜 텍스트 아님).
//   4. 제품 명칭 조합이 "(약어) 명칭" 순서.
//
// 실행: NODE_PATH=/tmp/node_modules node verify_profile_icon_consistency.mjs
//   (jsdom 은 /tmp 에 임시 설치됨 — CI 미의존, frontend-only 변경 로컬 게이트)

import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── 공통: jsdom 환경 ────────────────────────────────────────────────────
const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;

const appSrc = readFileSync(join(STATIC, "app.js"), "utf8");
// feature-0038 Cycle 5: 제품/데이터소스 pane 은 admin/{products,datasources}.js 로 분리
//   (byte-동치 이동) — pane 소속 단언은 합본으로 검사한다.
const adminSrc = readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/products.js"), "utf8")
  + readFileSync(join(STATIC, "admin/datasources.js"), "utf8");

// ── 헬퍼 추출: identiconSvg / _identiconHash 를 양 파일에서 떼어 평가 ──────
function extractFn(src, name) {
  // function <name>( ... ) { ... } 한 정의 블록을 중괄호 밸런스로 추출.
  //   파라미터 구조분해({ a, b })의 중괄호를 본문 시작으로 오인하지 않도록,
  //   시그니처의 닫는 ')' 이후 첫 '{' 부터 depth 를 센다.
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  // 시그니처 괄호 밸런스로 파라미터 목록 끝(')')을 찾는다.
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
  return src.slice(start, end);
}

// ── 테스트 1: identicon 헬퍼 정합 (admin.js 가 app.js 와 동일 구현 보유) ──
console.log("\n[1] identicon 헬퍼 정합 (작업화면 프로필 ↔ 관리 콘솔)");
const appHash = extractFn(appSrc, "_identiconHash");
const appSvg = extractFn(appSrc, "identiconSvg");
const adminHash = extractFn(adminSrc, "_identiconHash");
const adminSvg = extractFn(adminSrc, "identiconSvg");
const adminApply = extractFn(adminSrc, "applyAvatar");
ok("app.js 에 _identiconHash 정의 존재", !!appHash);
ok("app.js 에 identiconSvg 정의 존재", !!appSvg);
ok("admin.js 에 _identiconHash 정의 존재(이식)", !!adminHash);
ok("admin.js 에 identiconSvg 정의 존재(이식)", !!adminSvg);
ok("admin.js 에 applyAvatar 정의 존재(이식)", !!adminApply);
ok("_identiconHash 가 app↔admin byte-identical", appHash === adminHash);
ok("identiconSvg 가 app↔admin byte-identical", appSvg === adminSvg);

// 평가해서 동일 seed → 동일 SVG 산출 확인
const evalSvg = new Function(`${appHash}\n${appSvg}\nreturn identiconSvg;`)();
const svgA = evalSvg("KR_QA", 100);
const svgB = evalSvg("KR_QA", 100);
ok("identiconSvg 결정론적(같은 seed → 같은 SVG)", svgA === svgB);
ok("identiconSvg 가 <svg> 산출", /^<svg /.test(svgA) && svgA.includes("<rect"));
ok("identiconSvg seed 다르면 다른 색/패턴", evalSvg("KR_QA", 100) !== evalSvg("DK_ONLINE", 100));

// ── 테스트 2 & 3: 드롭업 항목 레이아웃 순서 + Identicon 폴백 ──────────────
console.log("\n[2/3] 드롭업 항목 레이아웃 순서 + Identicon 폴백");
// buildProductDropupItem 와 의존 함수(connStatusMeta)·identicon 을 격리 평가.
const connMeta = extractFn(appSrc, "connStatusMeta");
const buildItem = extractFn(appSrc, "buildProductDropupItem");
// click 핸들러가 closeProductDropup/setActiveProduct 를 참조하므로 스텁 주입.
// ds-conn-test: buildProductDropupItem 이 데이터소스 배지 렌더 시 canOpenAdminConsole() 로 '연결 테스트'
//  버튼 노출 여부를 게이트한다. 본 하네스는 프로필 아이콘/레이아웃 순서(display-only 배지)를 검증하므로
//  false 스텁 → 기존 span 배지 경로(회귀 0)를 그대로 평가한다.
const harness = `
${appHash}
${appSvg}
${connMeta}
function closeProductDropup(){}
function setActiveProduct(){}
function canOpenAdminConsole(){ return false; }
${buildItem}
return buildProductDropupItem;
`;
const buildProductDropupItem = new Function("document", harness)(document);

// pinned 제품(아이콘 미설정) → dot, icon(Identicon svg), label, (ds 없음)
const item = buildProductDropupItem({
  mode: "pinned", pid: 7, label: "(KR_QA) 킹스레이드",
  selected: false, datasourceKey: null, datasources: null,
  connStatusOverall: "healthy", iconUrl: null, productKey: "KR_QA",
});
const kids = Array.from(item.children);
const clsSeq = kids.map((c) => String(c.getAttribute("class") || "").split(" ")[0]);
ok("첫 요소 = 상태 배지(dot)", clsSeq[0] === "product-dropup-item-dot");
ok("둘째 요소 = 프로필 아이콘", clsSeq[1] === "product-dropup-item-icon");
ok("셋째 요소 = 명칭 label", clsSeq[2] === "product-dropup-item-label");
const iconEl = kids[1];
ok("아이콘 미설정 시 Identicon SVG 폴백(이니셜 텍스트 아님)", !!iconEl.querySelector("svg"));
ok("명칭 label 텍스트 = '(약어) 명칭'", kids[2].textContent === "(KR_QA) 킹스레이드");

// pinned 제품(아이콘 설정) → icon 은 <img>
const item2 = buildProductDropupItem({
  mode: "pinned", pid: 8, label: "(DK) DK온라인",
  selected: true, datasourceKey: "mssql-qa", datasources: null,
  connStatusOverall: "unstable", iconUrl: "/api/products/8/icon", productKey: "DK",
});
const kids2 = Array.from(item2.children);
ok("아이콘 설정 시 <img> 사용", kids2[1].querySelector("img") && kids2[1].querySelector("img").src.includes("/api/products/8/icon"));
ok("단일 datasource → ds 배지 노출(4번째 요소군에 포함)", kids2.some((c) => String(c.getAttribute("class")||"").startsWith("product-dropup-item-ds")));
const dsIdx = kids2.findIndex((c) => String(c.getAttribute("class")||"").startsWith("product-dropup-item-ds"));
const lblIdx = kids2.findIndex((c) => String(c.getAttribute("class")||"").startsWith("product-dropup-item-label"));
ok("데이터소스 배지가 명칭 뒤(label < ds 순서)", lblIdx >= 0 && dsIdx > lblIdx);

// auto 항목 → 아이콘 없음(dot 만)
const itemAuto = buildProductDropupItem({ mode: "auto", pid: null, label: "Product · 제품", selected: true });
const autoKids = Array.from(itemAuto.children).map((c) => String(c.getAttribute("class") || "").split(" ")[0]);
ok("auto 항목은 프로필 아이콘 없음(dot 만)", !autoKids.includes("product-dropup-item-icon"));

// ── 테스트 4: 명칭 조합 순서 (소스 정적 검증) ────────────────────────────
console.log("\n[4] 제품 명칭 조합 '(약어) 명칭' 순서 (정적)");
const oldPat = /\$\{[\w.]+\.name\} \(\$\{[\w.]+\.product_key\}\)/g;  // "명칭 (약어)" 잔존
const newPatApp = (appSrc.match(/\(\$\{[\w.]+\.product_key\}\) \$\{[\w.]+\.name\}/g) || []).length;
const newPatAdmin = (adminSrc.match(/\(\$\{[\w.]+\.product_key\}\) \$\{[\w.]+\.name\}/g) || []).length;
ok("app.js 에 잔존 '명칭 (약어)' 0건", !oldPat.test(appSrc));
ok("admin.js 에 잔존 '명칭 (약어)' 0건", !oldPat.test(adminSrc));
ok("app.js '(약어) 명칭' 4건", newPatApp === 4);
ok("admin.js '(약어) 명칭' 3건", newPatAdmin === 3);

// ── 결과 ─────────────────────────────────────────────────────────────────
console.log(`\n=== ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed ? 1 : 0);
