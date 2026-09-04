/* 패널의 상주 안내가 **실제로 DOM 에 그려지는가** — 문자열 검사가 아니라 렌더 결과.
 *
 * ai-connect.js 는 IIFE 이고 브리지 왕복을 전제하므로 통째로 실행할 수 없다. 대신 소스에서
 * `paintResidency` 함수만 **그대로 떼어내** 실제 DOM 에 물려 두 경우를 그린다.
 * ⚠ 떼어낸 것이 원본과 같은지는 길이·본문 대조로 확인한다(추출이 깨지면 vacuous pass 다).
 */
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";

const root = process.argv[2];
const js = readFileSync(`${root}/unit/feature-0003-agent-web-ui/src/static/ai-connect.js`, "utf8");
const html = readFileSync(`${root}/unit/feature-0003-agent-web-ui/src/static/ai-connect.html`, "utf8");

const start = js.indexOf("function paintResidency");
if (start < 0) { console.log("FAIL: paintResidency 를 찾지 못했다"); process.exit(1); }
const end = js.indexOf("\n  }", start);
const src = js.slice(start, end + 4);
/* ⚠ 추출 건전성 가드는 **구조 표지만** 본다. 여기서 문구까지 검사하면 「추출이 깨졌다」와
 * 「결함이 있다」가 같은 실패로 뭉개져, 대조군이 무엇을 잡았는지 알 수 없다
 * (실측 2026-09-04: 처음에 그렇게 만들었고 대조군이 엉뚱한 사유로 실패했다). */
if (!src.includes("clientResidency") || !src.includes("return") || src.length < 120) {
  console.log("EXTRACTION-BROKEN:", JSON.stringify(src.slice(0, 120)));
  process.exit(2);
}

const dom = new JSDOM(html, { runScripts: "outside-only" });
const { document } = dom.window;
if (!document.getElementById("clientResidency")) {
  console.log("FAIL: 문구가 가리키는 요소가 화면에 없다(#clientResidency)"); process.exit(1);
}
dom.window.eval(src + "\n;window.__paint = paintResidency;");
const paint = dom.window.__paint;
const read = () => document.getElementById("clientResidency").textContent;

paint(true);  const resident = read();
paint(false); const plain = read();

const ok =
  resident.includes("닫아도") && resident.includes("알림 영역") && resident.includes("종료") &&
  plain.includes("닫으면 연결이 끝납니다") && !plain.includes("닫아도") &&
  resident !== plain;

console.log(JSON.stringify({ resident, plain, verdict: ok ? "PASS" : "FAIL" }, null, 2));
process.exit(ok ? 0 : 1);
