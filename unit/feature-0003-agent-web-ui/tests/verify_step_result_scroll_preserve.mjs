// verify_step_result_scroll_preserve.mjs
// 실행 단계 패널의 "결과 보기" 내부 스크롤이 폴링 재렌더(body.innerHTML 재작성) 사이에
// 보존되는지 jsdom + 소스 추출 eval 로 격리 검증한다.
//
// 배경: 사이드 패널(_renderStepSidePanelBody)과 인라인 progress 카드(renderProgress)는
//   새 단계가 추가될 때마다 컨테이너를 통째로 재렌더한다. 이때 펼쳐 둔 결과 표
//   (.result-table-wrap)/미리보기(.step-result-preview)의 스크롤이 0 으로 되돌아가던 버그를
//   _snapshotStepResultScroll / _restoreStepResultScroll (stepKey=data-step-result-key 매칭)로 수정.
//
// 실행: node tests/verify_step_result_scroll_preserve.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 경로에서 자체 해석 — frontend-only 로컬 게이트.
//    jsdom 은 layout 을 계산하지 않으므로 scrollTop 은 설정값을 그대로 저장한다 — 내부 스크롤
//    보존 계약(키 기반 capture/restore) 검증에는 충분. 외부 패널 스크롤(scrollHeight 의존)의
//    시각적 최종 확인은 PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const appJs = readFileSync(join(STATIC, "app.js"), "utf8")
  // ITEM-P5b B3: progress 폴러/run 추적 도메인이 app/progress.js 로 이동 — 합본 검사.
  + readFileSync(join(STATIC, "app/progress.js"), "utf8");

// ── 1. 정적: 헬퍼 정의 + 두 재렌더 경로 배선 + data-step-result-key ─────────────
ok("[1] app.js: _snapshotStepResultScroll 정의", /function _snapshotStepResultScroll\(body\)\s*\{/.test(appJs));
ok("[1] app.js: _restoreStepResultScroll 정의", /function _restoreStepResultScroll\(body, map\)\s*\{/.test(appJs));
ok("[1] app.js: buildStepDetailEl 가 data-step-result-key(stepKey) 부여",
   /resultBody\.dataset\.stepResultKey\s*=\s*stepKey/.test(appJs));

// _renderStepSidePanelBody(사이드 패널) 배선
const sideBlk = appJs.slice(
  appJs.indexOf("function _renderStepSidePanelBody(pending) {"),
  appJs.indexOf("function formatElapsed("),
);
ok("[2] 사이드 패널: 재렌더 전 _snapshotStepResultScroll 호출",
   /const\s+\w+\s*=\s*_snapshotStepResultScroll\(body\)/.test(sideBlk));
ok("[2] 사이드 패널: 재렌더 후 _scheduleStepPanelScroll(body, …) 호출(동기+rAF)",
   /_scheduleStepPanelScroll\(body,\s*\w+/.test(sideBlk));
ok("[2] 사이드 패널: snapshot 이 innerHTML 재작성보다 앞",
   sideBlk.indexOf("_snapshotStepResultScroll(body)") < sideBlk.indexOf('body.innerHTML = ""'));
ok("[2] 사이드 패널: restore 스케줄이 innerHTML 재작성보다 뒤",
   sideBlk.lastIndexOf("_scheduleStepPanelScroll(body") > sideBlk.indexOf('body.innerHTML = ""'));

// renderProgress(인라인 progress 카드) 배선
const progBlk = appJs.slice(
  appJs.indexOf("function renderProgress("),
  appJs.indexOf("function clearProgressPollTimer("),
);
ok("[3] progress 카드: 재렌더 전 _snapshotStepResultScroll(progressStepsEl) 호출",
   /_snapshotStepResultScroll\(progressStepsEl\)/.test(progBlk));
ok("[3] progress 카드: 재렌더 후 _scheduleStepPanelScroll(progressStepsEl, …) 호출(동기+rAF)",
   /_scheduleStepPanelScroll\(progressStepsEl,\s*\w+/.test(progBlk));
// renderProgress 최상단 early-return 분기에도 innerHTML="" 가 있으므로, 재렌더용은 마지막 occurrence.
ok("[3] progress 카드: snapshot 이 재렌더 innerHTML 재작성보다 앞",
   progBlk.indexOf("_snapshotStepResultScroll(progressStepsEl)") < progBlk.lastIndexOf('progressStepsEl.innerHTML = ""'));
ok("[3] progress 카드: restore 스케줄이 재렌더 innerHTML 재작성보다 뒤",
   progBlk.lastIndexOf("_scheduleStepPanelScroll(progressStepsEl") > progBlk.lastIndexOf('progressStepsEl.innerHTML = ""'));

// ── 3b. 정적: _scheduleStepPanelScroll 이 동기 + requestAnimationFrame 두 번 복원 ──
const schedBlk = appJs.slice(
  appJs.indexOf("function _scheduleStepPanelScroll("),
  appJs.indexOf("function _renderStepSidePanelBody("),
);
ok("[3b] _scheduleStepPanelScroll: 동기 _applyStepPanelScroll 호출",
   /_applyStepPanelScroll\(container, resultScroll, atBottom, prevTop\)/.test(schedBlk));
ok("[3b] _scheduleStepPanelScroll: requestAnimationFrame 로 재적용(layout 확정 후 0-clamp 방지)",
   /requestAnimationFrame\(\(\)\s*=>\s*_applyStepPanelScroll\(/.test(schedBlk));
ok("[3b] _applyStepPanelScroll: 외부 스크롤 미추종 시 이전 위치 유지(prevTop clamp)",
   /Math\.min\(prevTop,\s*maxTop\)/.test(appJs));

// ── 4. 기능: 소스에서 헬퍼 2개를 추출해 jsdom 에서 실제 실행 ────────────────
const helpersStart = appJs.indexOf("function _snapshotStepResultScroll(body) {");
const helpersEnd = appJs.indexOf("function _renderStepSidePanelBody(pending) {");
ok("[4] 헬퍼 소스 추출 가능", helpersStart >= 0 && helpersEnd > helpersStart);
// B3 후속: 블록 내 함수가 export 화될 수 있다 — 주입 전 선언 export 접두만 제거.
const helpersSrc = appJs.slice(helpersStart, helpersEnd).replace(/^export (?=(async )?(function|const|let|var))/gm, "");

const dom = new JSDOM("<!DOCTYPE html><body><div id='panel'></div></body>");
const { document } = dom.window;
// requestAnimationFrame 스텁 — 예약된 콜백을 수집해 수동 flush 로 rAF 경로를 검증.
const rafCbs = [];
const requestAnimationFrame = (cb) => { rafCbs.push(cb); return rafCbs.length; };
const flushRaf = () => { const cbs = rafCbs.splice(0); cbs.forEach((cb) => cb()); };
// 전역으로 노출된 Map/querySelector 등은 window 컨텍스트에서 동작. 헬퍼를 eval 로 주입.
const factory = new dom.window.Function(
  "document", "Map", "requestAnimationFrame",
  helpersSrc + "\nreturn { _snapshotStepResultScroll, _restoreStepResultScroll, _applyStepPanelScroll, _scheduleStepPanelScroll };",
);
const { _snapshotStepResultScroll, _restoreStepResultScroll, _applyStepPanelScroll, _scheduleStepPanelScroll } =
  factory(document, dom.window.Map, requestAnimationFrame);

// 한 step 결과셋 DOM(사이드 패널 buildStepDetailEl 구조 모사)을 만든다.
function makeStep(panel, key, { expanded, scrollTop = 0, scrollLeft = 0, kind = "table" }) {
  const wrap = document.createElement("div");
  wrap.className = "step-result-wrap";
  wrap.dataset.stepResultKey = key;
  wrap.hidden = !expanded;
  const scroller = document.createElement("div");
  scroller.className = kind === "table" ? "result-table-wrap" : "step-result-preview";
  wrap.appendChild(scroller);
  panel.appendChild(wrap);
  if (expanded) { scroller.scrollTop = scrollTop; scroller.scrollLeft = scrollLeft; }
  return { wrap, scroller };
}

const panel = document.getElementById("panel");
// 초기 렌더: step A(펼침, 세로 스크롤됨), step B(펼침, 가로 스크롤됨), step C(접힘)
makeStep(panel, "0:t1", { expanded: true, scrollTop: 240, kind: "table" });
makeStep(panel, "1:t2", { expanded: true, scrollLeft: 88, kind: "preview" });
makeStep(panel, "2:t3", { expanded: false, scrollTop: 999, kind: "table" }); // hidden → scroll 무시

// 재렌더 전 스냅샷
const snap = _snapshotStepResultScroll(panel);
ok("[4] 스냅샷: 펼친 step 2개만 캡처(접힌 step 제외)", snap.size === 2);
ok("[4] 스냅샷: A 세로 스크롤 캡처", snap.get("0:t1") && snap.get("0:t1").top === 240);
ok("[4] 스냅샷: B 가로 스크롤 캡처", snap.get("1:t2") && snap.get("1:t2").left === 88);
ok("[4] 스냅샷: 접힌 C 미캡처", !snap.has("2:t3"));

// 폴링 재렌더 모사: 기존 항목 전부 파기 후 새 항목 재생성 + 새 단계 D 추가(단계 진행).
// 재생성된 scroller 는 scrollTop=0 (초기값) 으로 시작.
panel.innerHTML = "";
const a2 = makeStep(panel, "0:t1", { expanded: true, scrollTop: 0, kind: "table" });
const b2 = makeStep(panel, "1:t2", { expanded: true, scrollLeft: 0, kind: "preview" });
const c2 = makeStep(panel, "2:t3", { expanded: false, scrollTop: 0, kind: "table" });
const d2 = makeStep(panel, "3:t4", { expanded: true, scrollTop: 0, kind: "table" }); // 새 단계
ok("[4] 재렌더 직후: A scroller 초기화됨(0)", a2.scroller.scrollTop === 0);

// 복원
_restoreStepResultScroll(panel, snap);
ok("[5] 복원: A 세로 스크롤 240 복원", a2.scroller.scrollTop === 240);
ok("[5] 복원: B 가로 스크롤 88 복원", b2.scroller.scrollLeft === 88);
ok("[5] 복원: 접힌 C 는 스냅샷에 없어 변화 없음(0)", c2.scroller.scrollTop === 0);
ok("[5] 복원: 새 단계 D 는 스냅샷에 없어 0 유지", d2.scroller.scrollTop === 0);

// 방어: 빈 맵/누락 컨테이너에서 throw 없음
let threw = false;
try { _restoreStepResultScroll(panel, new dom.window.Map()); _restoreStepResultScroll(null, snap); }
catch (_) { threw = true; }
ok("[6] 방어: 빈 맵/null 컨테이너에서 예외 없음", !threw);

// ── 7. 기능: _scheduleStepPanelScroll 이 동기 + rAF 두 번 복원 ──────────────
// 실브라우저에서 재렌더 직후 동기 scrollLeft 쓰기는 layout 미확정으로 0-clamp 될 수 있어,
// rAF(layout 확정 후) 재적용이 실제 수정 지점이다. jsdom 은 clamp 안 하므로 동기도 값이
// 남지만, "동기 1회 + rAF 1회" 두 번 적용되는 배선 자체를 flush 로 검증한다.
panel.innerHTML = "";
const g = makeStep(panel, "1:t2", { expanded: true, scrollLeft: 0, kind: "preview" });
const snap7 = new dom.window.Map([["1:t2", { top: 0, left: 88 }]]);
rafCbs.length = 0;
_scheduleStepPanelScroll(panel, snap7, false, 0);
ok("[7] 동기 복원 즉시 반영(가로 88)", g.scroller.scrollLeft === 88);
ok("[7] rAF 콜백 1건 예약됨(layout 확정 후 재적용)", rafCbs.length === 1);
// 실브라우저 0-clamp 재현: rAF 실행 전 누군가 scroll 을 0 으로 되돌려도 rAF 가 재복원.
g.scroller.scrollLeft = 0;
flushRaf();
ok("[7] rAF flush 후 가로 88 재복원(0-clamp 복구 경로)", g.scroller.scrollLeft === 88);
ok("[7] rAF 큐 소진(재진입 경합 없음)", rafCbs.length === 0);

console.log(`\n${failed === 0 ? "OK" : "FAIL"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
