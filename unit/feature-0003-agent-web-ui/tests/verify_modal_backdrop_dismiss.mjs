// verify_modal_backdrop_dismiss.mjs
// modal-backdrop-dismiss: 어두운 배경(backdrop/overlay)을 눌러 모달을 닫는 동작을, **누름
// (pointerdown)과 뗌(pointerup)이 둘 다 그 배경 자신**일 때만으로 한정한다.
//
//   [결함] 구 구현은 `click` 리스너 + `e.target === <배경>` 검사(일부는 `mousedown` 단독)였다.
//          DOM `click` 의 target 은 mousedown/mouseup 두 지점의 **공통 조상**이라, 패널 안에서
//          누르고 배경에서 떼거나(텍스트 드래그 선택 후 바깥 놓기) 그 반대일 때도 target 이
//          배경으로 승격돼 모달이 닫혔다 — 사용자 관점 "down 만 해도 / up 만 해도 닫힌다".
//          `mousedown` 단독은 뗌을 보지도 않고 더 이르게 닫았다.
//   [수정] `static/modal-dismiss.js` 의 **저장소 단일 primitive** `bindBackdropDismiss` 로 통일.
//          별도 모듈인 이유: ESM 번들이 둘(작업 화면 `app.js` / 관리 콘솔 `admin.js`)이라 한쪽에
//          두면 다른 쪽이 복제할 수밖에 없고, **그 복제가 이 결함을 만든 기전**이다.
//
// 검증 2축:
//   (A) 동작 — 정본 모듈에서 헬퍼 본문을 추출해 최소 DOM 이벤트 shim 위에서 실제로 실행하고
//       press/release 조합별 dismiss 여부를 단언한다(정적 문자열 검사로는 잡히지 않는 계약).
//   (B) 배선 — 배경 dismiss 를 배선하는 **모든 표면**(작업 화면 6 + 프로필 사용내역 + 관리 콘솔
//       사용기록·감사 purge + 그래프 도움말 + 검색 모달)이 primitive 를 쓰고, 옛 판정이 어디에도
//       남지 않았음을 **식별자에 키잉하지 않는** 전-트리 census 로 단언한다(최초 sweep 이
//       `backdrop` 만 보다가 `overlay` 명명 3곳을 놓친 실패의 회귀 잠금).
//
// 실행: node verify_modal_backdrop_dismiss.mjs
//   (순수 정적 + 자체 이벤트 shim — jsdom/네트워크 비의존. 실제 렌더링/포인터 동작의 최종 확인은
//    PB-0008 Windows-browser: `tests/pb0008_modal_backdrop_dismiss.py`.)

import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
// primitive 는 저장소 단일 모듈 — 작업 화면(app.js)과 관리 콘솔(admin.js) 두 ESM 번들이 공유.
const primitiveJs = read("modal-dismiss.js");
const appJs = read("app.js");
const sidebarJs = read("app", "sidebar.js");
const profileJs = read("app", "profile.js");
const adminUsageJs = read("admin", "usage.js");
const adminAuditJs = read("admin", "audit.js");
const graphCoreJs = read("graph", "graph-core.js");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// function <name>(...) / export function <name>(...) 한 정의 블록을 중괄호 밸런스로 추출.
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
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
  return end < 0 ? null : src.slice(start, end);
}

// ── (A) 동작 검증 ────────────────────────────────────────────────────────────
const helperSrc = extractFn(primitiveJs, "bindBackdropDismiss");
ok("bindBackdropDismiss 추출됨", !!helperSrc);

// 최소 DOM shim — backdrop > panel 2단 트리. 패널 위 이벤트는 backdrop 까지 버블링하며 target 은
// 패널로 유지되므로(리스너는 backdrop 에만 붙는다) 버블 경로 자체는 시뮬레이션하지 않는다.
//
// ★ 실 브라우저의 **3가지 의미론**을 모델링한다 — 이걸 빼면 하네스가 vacuous 해진다:
//   (a) 이벤트 순서·target 승격: pointerdown(누른 곳) → pointerup(뗀 곳) →
//       click(target = 둘의 **공통 조상**). 이 승격이 원 결함의 기전.
//   (b) **implicit pointer capture**: touch/pen 은 pointerdown 대상에 캡처가 자동으로 걸려
//       pointerup 이 그 대상으로 retarget 된다(마우스는 캡처 없음). 핸들러가
//       `releasePointerCapture` 를 부르면 그때부터 실제 히트테스트 위치로 돌아온다.
//   (c) click 이 아예 발행되지 않는 상호작용(스크롤바 드래그 등)도 표현 가능.
class FakeNode {
  constructor(label) { this.label = label; this._ls = new Map(); this._captured = new Set(); }
  addEventListener(type, fn) {
    if (!this._ls.has(type)) this._ls.set(type, []);
    this._ls.get(type).push(fn);
  }
  hasPointerCapture(id) { return this._captured.has(id); }
  setPointerCapture(id) { this._captured.add(id); }
  releasePointerCapture(id) { this._captured.delete(id); }
  // isTrusted 기본 true — 브라우저가 실제 입력에서 만드는 이벤트를 모델링한다.
  // 합성 이벤트(`el.click()` / `dispatchEvent`)는 호출측이 isTrusted:false 를 명시한다.
  fire(type, { target = this, button = 0, isPrimary = true, pointerId = 1, isTrusted = true } = {}) {
    (this._ls.get(type) || []).forEach((fn) => fn({ type, target, button, isPrimary, pointerId, isTrusted }));
  }
}

const bindBackdropDismiss = new Function(`${helperSrc}; return bindBackdropDismiss;`)();

function scenario(steps) {
  const backdrop = new FakeNode("backdrop");
  const panel = new FakeNode("panel");
  let dismissed = 0;
  bindBackdropDismiss(backdrop, () => { dismissed++; });

  // 한 번의 포인터 상호작용.
  //   pointerType "mouse"(기본) — 캡처 없음. "touch" — implicit capture 를 down 대상에 건다.
  //   emitClick=false — 브라우저가 click 을 발행하지 않는 상호작용(스크롤바 드래그 등).
  const press = (downTarget, upTarget, {
    button = 0, isPrimary = true, pointerId = 1, pointerType = "mouse", emitClick = true,
  } = {}) => {
    if (pointerType !== "mouse") downTarget.setPointerCapture(pointerId);   // (b) implicit capture
    backdrop.fire("pointerdown", { target: downTarget, button, isPrimary, pointerId });
    // 캡처가 아직 살아 있으면 pointerup 은 캡처 대상으로 retarget, 해제됐으면 실제 뗀 곳.
    const upResolved = downTarget.hasPointerCapture(pointerId) ? downTarget : upTarget;
    backdrop.fire("pointerup", { target: upResolved, button, isPrimary, pointerId });
    if (emitClick && button === 0 && isPrimary) {
      const clickTarget = downTarget === upTarget ? downTarget : backdrop;  // (a) 공통 조상 승격
      backdrop.fire("click", { target: clickTarget, button, isPrimary, pointerId });
    }
  };
  steps({ backdrop, panel, press });
  return dismissed;
}

ok("[마우스] 배경에서 누르고 배경에서 뗌 → 닫힘",
  scenario(({ backdrop, press }) => press(backdrop, backdrop)) === 1);

ok("[마우스] 패널에서 누르고 배경에서 뗌 → 안 닫힘 (지침 textarea 드래그 선택 후 바깥 놓기)",
  scenario(({ backdrop, panel, press }) => press(panel, backdrop)) === 0);

ok("[마우스] 배경에서 누르고 패널에서 뗌 → 안 닫힘",
  scenario(({ backdrop, panel, press }) => press(backdrop, panel)) === 0);

ok("[마우스] 패널에서 누르고 패널에서 뗌 → 안 닫힘",
  scenario(({ panel, press }) => press(panel, panel)) === 0);

// ★ implicit pointer capture 회귀 잠금 (ux 패널 P1-1) — 해제하지 않으면 터치에서 pointerup 이
//   무조건 backdrop 으로 retarget 돼 "누른 위치만으로 닫힘" 이 되고 원 결함이 그대로 남는다.
ok("[터치] 배경에서 누르고 패널에서 뗌 → 안 닫힘 (implicit pointer capture 해제 필요)",
  scenario(({ backdrop, panel, press }) => press(backdrop, panel, { pointerType: "touch" })) === 0);

ok("[터치] 배경에서 누르고 배경에서 뗌 → 닫힘 (캡처 해제가 정상 경로를 깨지 않음)",
  scenario(({ backdrop, press }) => press(backdrop, backdrop, { pointerType: "touch" })) === 1);

// (주의) 이 케이스는 `downOk` 가 이미 false 라 **캡처 유지 여부와 무관하게** 통과한다 —
//  캡처 축의 판별력은 위 "[터치] 배경→패널" 케이스가 담당한다. 여기서는 터치 경로에서도
//  AC2 가 성립함만 확인한다(§18.8 design 패널 P3-4 지적 반영해 라벨 정직화).
ok("[터치] 패널에서 누르고 배경에서 뗌 → 안 닫힘 (AC2, 캡처 축은 위 케이스가 담당)",
  scenario(({ backdrop, panel, press }) => press(panel, backdrop, { pointerType: "touch" })) === 0);

// ★ 보조 버튼 가드 회귀 잠금 — 1차 단언은 `press()` 가 비주 버튼에 click 을 안 쏘는 탓에
//   primitive 의 판정 단계에 **도달조차 못해** `downOk = true` 로 갈아도 통과하던 vacuous 였다
//   (§18.8 design 패널 P2-3, 뮤테이션으로 실증). 브라우저는 우클릭에 `click` 대신
//   `contextmenu` 를 쏘지만, 여기서 검증하는 것은 "**click 이 오더라도** 보조 버튼 제스처는
//   인정하지 않는다" 는 primitive 의 계약이므로 click 까지 명시적으로 넣어 가드를 실제로 친다.
ok("배경 우클릭 down/up 뒤 click 이 와도 → 안 닫힘 (button 가드)",
  scenario(({ backdrop }) => {
    backdrop.fire("pointerdown", { target: backdrop, button: 2 });
    backdrop.fire("pointerup", { target: backdrop, button: 2 });
    backdrop.fire("click", { target: backdrop, button: 2 });
  }) === 0);

ok("배경 좌클릭 press 후 pointercancel → 뒤이은 pointerup+click 으로 안 닫힘",
  scenario(({ backdrop }) => {
    backdrop.fire("pointerdown", { target: backdrop });
    backdrop.fire("pointercancel", { target: backdrop });
    backdrop.fire("pointerup", { target: backdrop });
    backdrop.fire("click", { target: backdrop });
  }) === 0);

ok("press 없이 합성 click 단독 → 안 닫힘 (물리 포인터 제스처만 인정 — 의도)",
  scenario(({ backdrop }) => { backdrop.fire("click", { target: backdrop, isTrusted: false }); }) === 0);

// ★ 장전(armed) 수명 회귀 잠금 — §18.8 ux·design 패널이 **양쪽 다** 실제 헬퍼를 돌려 실증한
//   결함. "배경에서 down+up 했는데 브라우저가 click 을 안 쏜" 제스처가 장전을 남기면, 그 뒤
//   도착한 click 하나가 사용자가 누른 적 없는 모달을 닫는다(폴더 지침 작성분 소실).
ok("click 미발행 제스처로 장전된 뒤 도착한 합성 click → 안 닫힘 (장전 잔류 봉인)",
  scenario(({ backdrop, press }) => {
    press(backdrop, backdrop, { emitClick: false });          // 장전만 남기는 제스처
    backdrop.fire("click", { target: backdrop, isTrusted: false });
  }) === 0);

ok("click 미발행 제스처로 장전된 뒤, pointerdown 이 소실된 채 도착한 up+click → 안 닫힘",
  scenario(({ backdrop, panel }) => {
    backdrop.fire("pointerdown", { target: backdrop });
    backdrop.fire("pointerup", { target: backdrop });          // click 미발행 → 장전 잔류 시도
    // 다음 제스처의 pointerdown 이 자식의 stopPropagation 등으로 backdrop 에 도달하지 못한 상황:
    // 패널에서 시작한 드래그인데 뗌·click 만 backdrop 이 본다.
    backdrop.fire("pointerup", { target: backdrop });
    backdrop.fire("click", { target: backdrop });
  }) === 0);

ok("정상 배경 클릭 뒤 곧바로 도착한 여분의 click → 추가 dismiss 없음 (armed 1회 소비)",
  scenario(({ backdrop, press }) => {
    press(backdrop, backdrop);
    backdrop.fire("click", { target: backdrop });
  }) === 1);

ok("press 없이 pointerup 단독 → 안 닫힘 (모달이 커서 아래에서 열린 직후 유령 dismiss 차단)",
  scenario(({ backdrop }) => { backdrop.fire("pointerup", { target: backdrop }); }) === 0);

// ★ ghost click 회귀 잠금 (ux 패널 P2-1) — 브라우저가 click 을 발행하지 않는 상호작용에서는
//   dismiss 도 일어나지 않아야 한다(실행 단계가 click 이라는 계약의 직접 단언).
ok("배경에서 down/up 했지만 브라우저가 click 미발행(스크롤바 드래그류) → 안 닫힘",
  scenario(({ backdrop, press }) => press(backdrop, backdrop, { emitClick: false })) === 0);

ok("연속 2회 배경 클릭 → 매번 닫힘 판정(상태 누수 없음)",
  scenario(({ backdrop, press }) => { press(backdrop, backdrop); press(backdrop, backdrop); }) === 2);

ok("드래그-이탈(안→밖) 직후 정상 배경 클릭 → 정확히 1회만 닫힘",
  scenario(({ backdrop, panel, press }) => { press(panel, backdrop); press(backdrop, backdrop); }) === 1);

ok("비-primary 포인터(멀티터치 2번째 손가락) 단독 → 안 닫힘 (click 이 와도)",
  scenario(({ backdrop }) => {
    backdrop.fire("pointerdown", { target: backdrop, isPrimary: false, pointerId: 2 });
    backdrop.fire("pointerup", { target: backdrop, isPrimary: false, pointerId: 2 });
    backdrop.fire("click", { target: backdrop, isPrimary: false, pointerId: 2 });
  }) === 0);

// ★ 멀티터치 간섭 회귀 잠금 (ux 패널 P3-2) — 화면에 다른 손가락이 얹혀 있어도 주 포인터의
//   정상 배경 탭은 닫혀야 한다(보조 pointerdown 이 주 포인터 상태를 지우면 안 됨).
// ★ 순서가 핵심 — 보조 pointerdown 은 주 포인터가 **누르고 있는 도중**에 와야 가드를 친다.
//   1차 단언은 보조를 주 press 앞에 쏘아 가드를 우회했고, `isPrimary` 가드를 통째로 지워도
//   통과하던 vacuous 였다(§18.8 design 패널 P2-3).
ok("주 포인터로 배경을 누른 도중 보조 손가락이 패널에 접촉해도 → 정상 닫힘 (멀티터치 간섭 차단)",
  scenario(({ backdrop, panel }) => {
    backdrop.fire("pointerdown", { target: backdrop, pointerId: 1 });                    // 주: 배경 누름
    backdrop.fire("pointerdown", { target: panel, isPrimary: false, pointerId: 2 });     // 보조: 패널 접촉
    backdrop.fire("pointerup", { target: panel, isPrimary: false, pointerId: 2 });       // 보조: 뗌
    backdrop.fire("pointerup", { target: backdrop, pointerId: 1 });                      // 주: 배경에서 뗌
    backdrop.fire("click", { target: backdrop, pointerId: 1 });
  }) === 1);

// ── (B) 배선 검증 (전 static 트리 회귀 잠금) ───────────────────────────────
ok("modal-dismiss.js: primitive export (저장소 단일 정본)",
  /export function bindBackdropDismiss\(/.test(primitiveJs));
ok("app.js: primitive 를 자체 정의하지 않고 공용 모듈에서 import",
  !/^export function bindBackdropDismiss\(/m.test(appJs)
  && /import \{ bindBackdropDismiss \} from "\.\/modal-dismiss\.js\?v=dev";/.test(appJs));

// 배경 dismiss 를 배선하는 **모든** 표면. 요청 범위(좌측 항목 6종) + 동형 오버레이 + 검색 모달.
// [파일, 함수, backdrop 식별자, 소스]
const SURFACES = [
  ["app.js", "promptShareExpiry", "backdrop", appJs],
  ["app.js", "confirmShareJoinable", "backdrop", appJs],
  ["app.js", "openShareDialog", "backdrop", appJs],
  ["app.js", "openConversationSettings", "backdrop", appJs],
  ["app/sidebar.js", "openFolderSettings", "backdrop", sidebarJs],
  ["app/sidebar.js", "openMoveConversationDialog", "backdrop", sidebarJs],
  ["app/profile.js", "showProfileUsageConvModal", "overlay", profileJs],
  ["admin/usage.js", "showUsageConvModal", "overlay", adminUsageJs],
  ["admin/audit.js", "openAuditPurgeModal", "overlay", adminAuditJs],
];
SURFACES.forEach(([file, fn, ident, src]) => {
  const body = extractFn(src, fn);
  ok(`${file} ${fn}: primitive 로 배경 dismiss 배선`,
    !!body && body.includes(`bindBackdropDismiss(${ident}`));
  ok(`${file} ${fn}: 옛 판정(click/mousedown + target 검사) 부재`,
    // ⚠ 역참조는 **두 번째** 그룹(이벤트 인자명). 첫 역검증에서 `\1`(이벤트 종류)로 잘못 걸어
    // 옛 패턴을 복원해도 통과하던 vacuous 단언이었다 — 그룹 번호를 고정으로 박지 말 것.
    !!body && !new RegExp(`${ident}\\.addEventListener\\(\\s*["'](?:click|mousedown|mouseup)["']\\s*,\\s*\\((\\w+)\\)\\s*=>\\s*\\{\\s*if\\s*\\(\\1\\.target === ${ident}\\)`).test(body));
});

// 검색 모달(구 TASK-0077/0078 손수 구현) 이관 — 전용 상태 플래그까지 사라졌는지.
ok("app.js 검색 모달: primitive 로 이관", /bindBackdropDismiss\(overlay, closeSearchModal\)/.test(appJs));
ok("app.js 검색 모달: 전용 mousedownOnOverlay/mouseupOnOverlay 상태 소멸(주석 외)",
  appJs.split("\n").filter((l) => /mousedownOnOverlay|mouseupOnOverlay/.test(l) && !/^\s*\/\//.test(l)).length === 0);

// 그래프 뷰 도움말 오버레이 — 실제 dismiss 표면은 `inset:0` 전용 배경 자식 하나(오버레이를 전면
// 덮으므로 오버레이 바인딩은 dead code). 자식 부재 시 오버레이 폴백.
ok("graph/graph-core.js 도움말: 전용 배경 자식(폴백 오버레이)에 primitive 배선",
  /const dismissSurface = ov\.querySelector\("\[data-amg-help-close\]"\) \|\| ov;/.test(graphCoreJs)
  && /bindBackdropDismiss\(dismissSurface, \(\) => _metaGraphHideHelp\(\)\)/.test(graphCoreJs));
ok("graph/graph-core.js 도움말: 옛 classList/attribute 기반 click 판정 부재",
  !/hasAttribute\("data-amg-help-close"\)\s*\|\|\s*t\.classList\.contains\("amg-help-overlay"\)/.test(graphCoreJs));

// 두 번들 모두 같은 정본을 import 하는가(복제 = 이 결함을 만든 기전).
[["app/sidebar.js", sidebarJs], ["app/profile.js", profileJs],
 ["admin/usage.js", adminUsageJs], ["admin/audit.js", adminAuditJs],
 ["graph/graph-core.js", graphCoreJs]].forEach(([file, src]) => {
  // import 문은 단일행/다중행 둘 다 있으므로 "import 블록 안에 식별자가 있고 + 자체 정의가 없다" 로 본다.
  const imported = /import\s*\{[^}]*\bbindBackdropDismiss\b[^}]*\}\s*from\s*["'][^"']+["']/s.test(src);
  ok(`${file}: bindBackdropDismiss 를 import (자체 정의 아님)`,
    imported && !/function bindBackdropDismiss\(/.test(src));
});

// ★ 전 static 트리 census — 신규 모달이 옛 패턴을 복사하는 drift 를 구조적으로 차단.
//   ⚠ 두 가지를 절대 하지 않는다(둘 다 실패 이력이 있다):
//     (1) **식별자에 키잉하지 않는다** — 최초 sweep 이 `backdrop` 만 보다가 `overlay` 명명 3곳을
//         놓쳤다. 수신자 식별자를 정규식에서 캡처해 대조한다.
//     (2) **파일 목록을 손으로 나열하지 않는다** — 그러면 "이미 고친 파일"만 보게 되어, 새 파일에
//         옛 패턴이 들어와도 통과한다(§18.8 ux 패널 P2-2: 33개 중 6개만 보고 "전수" 라 단정했다).
//         디렉토리를 재귀 walk 한다.
function walkJs(dir, acc = []) {
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === "vendor") continue;   // 미니파이 3rd-party — 재작성 대상 아님
    const full = join(dir, ent.name);
    if (ent.isDirectory()) walkJs(full, acc);
    else if (ent.name.endsWith(".js")) acc.push(full);
  }
  return acc;
}

// 핸들러 **본문만** 중괄호 밸런스로 떠서 "수신자 자신을 target 과 비교하는가" 를 본다.
// 화살표/함수식·괄호 유무·`===`/`!==`·`&&` 축약 등 표기 변형에 걸리지 않는다.
// ⚠ 고정 길이 lookahead 를 쓰면 **바로 뒤에 등록된 다른 리스너**의 본문을 잘못 읽는다
//   (실제로 `app.js:1792` 의 click 리스너가 인접 keydown 의 `ev.target !== item` 을 물어
//    오검출됐다) — 반드시 자기 본문 경계 안에서만 판정한다.
function handlerBody(src, from) {
  const rest = src.slice(from);
  const m = rest.match(/^\s*(?:\((\w*)\)|(\w+))\s*=>\s*\{|^\s*function\s*\w*\s*\((\w*)\)\s*\{/);
  if (!m) return null;   // 이름 참조(`el.addEventListener("click", _select)`)·표현식 본문 → 판정 불가, 건너뜀
  let i = from + m[0].length - 1, depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) return src.slice(from, i + 1); }
  }
  return null;
}

function legacyDismissSites(src) {
  const hits = [];
  const re = /(\w+)\.addEventListener\(\s*["'](click|mousedown|mouseup)["']\s*,/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const receiver = m[1];
    const body = handlerBody(src, re.lastIndex);
    if (!body) continue;
    if (new RegExp(`\\w+\\.target\\s*[!=]==\\s*${receiver}\\b`).test(body)) {
      hits.push(`${receiver}.addEventListener("${m[2]}", …)`);
    }
  }
  return hits;
}

const ALL_JS = walkJs(STATIC);
ok(`census 대상이 전 static 트리(vendor 제외 ${ALL_JS.length}개 파일) — 하드코딩 목록 아님`,
  ALL_JS.length >= 20 && ALL_JS.some((f) => f.endsWith("modal-dismiss.js")));
const violations = [];
ALL_JS.forEach((f) => {
  if (f.endsWith("modal-dismiss.js")) return;   // primitive 자신은 계약의 정의부
  legacyDismissSites(readFileSync(f, "utf8")).forEach((h) => violations.push(`${f.replace(STATIC + "/", "")}: ${h}`));
});
ok(`전 static 트리: "target 을 수신자 자신과 비교하는" 배경 dismiss 잔존 0`
   + (violations.length ? ` — ${violations.join(" · ")}` : ""), violations.length === 0);

// 자기검증 — 위 detector 가 실제로 옛 패턴을 잡는가(탐지기가 조용히 죽으면 census 는 무의미).
const SAMPLES = [
  'overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });',
  'overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });',
  'ov.addEventListener("click", function (ev) { if (ev.target === ov) hide(); });',
  'bd.addEventListener("click", e => { if (e.target !== bd) return; close(); });',
  'x.addEventListener("mouseup", (ev) => { ev.target === x && close(); });',
];
ok("census detector 자기검증 — 표기 변형 5종을 전부 검출",
  SAMPLES.every((sample) => legacyDismissSites(sample).length === 1));
ok("census detector 자기검증 — primitive 배선·행 클릭 핸들러는 오검출 안 함",
  legacyDismissSites('bindBackdropDismiss(overlay, close);').length === 0
  && legacyDismissSites('overlay.addEventListener("click", (e) => { const b = e.target.closest("[data-nav]"); if (!b) return; go(b); });').length === 0);
ok("census detector 자기검증 — 인접 리스너 본문을 물어오지 않음(고정 lookahead 회귀)",
  legacyDismissSites('item.addEventListener("click", _select);\n'
    + 'item.addEventListener("keydown", (ev) => { if (ev.target !== item) return; go(); });').length === 0);

// ESC / × 버튼 닫기 경로 회귀 잠금.
[["app.js", "promptShareExpiry", appJs], ["app.js", "confirmShareJoinable", appJs],
 ["app.js", "openShareDialog", appJs], ["app.js", "openConversationSettings", appJs],
 ["app/sidebar.js", "openFolderSettings", sidebarJs],
 ["app/sidebar.js", "openMoveConversationDialog", sidebarJs]].forEach(([file, fn, src]) => {
  const body = extractFn(src, fn);
  ok(`${file} ${fn}: ESC 닫기 유지`, !!body && /e\.key === "Escape"/.test(body));
  ok(`${file} ${fn}: × 닫기 버튼 유지`, !!body && body.includes(".share-mgr-close"));
});
[["app/profile.js", "showProfileUsageConvModal", profileJs, "profileUsageConvClose"],
 ["admin/usage.js", "showUsageConvModal", adminUsageJs, "usageConvModalClose"]].forEach(([file, fn, src, closeId]) => {
  const body = extractFn(src, fn);
  ok(`${file} ${fn}: ESC 닫기 유지`, !!body && /e\.key === "Escape"/.test(body));
  ok(`${file} ${fn}: × 닫기 버튼 유지`, !!body && body.includes(closeId));
});

// ── (C) 리스너 수명 실측 (정규식 단언 금지) ─────────────────────────────────
// §18.8 design 패널 P2-1: "close() 안에 removeEventListener 문자열이 있다" 는 정규식 단언은
// **누수 0 을 증명하지 못한다** — 이 두 모달은 loading→data 로 **재렌더**되므로, 이전 인스턴스의
// onEsc 를 떼지 않으면 열 때마다 하나씩 샌다(패널이 6회 열기 → 6개 잔존으로 실증).
// 그래서 실제 렌더 함수의 **수명 로직을 재현**해 document 리스너 수를 센다.
function simulateLifecycle(bodySrc, prevId) {
  // 대상 함수에서 수명 관련 3줄(prev 가드 · close 정의 · addEventListener)만 뽑아 재현한다.
  const usesModalClose = /typeof prev\._modalClose === "function"/.test(bodySrc)
                          && /overlay\._modalClose = close;/.test(bodySrc);
  const closeRemoves = /const close = \(\) => \{[^}]*removeEventListener\("keydown", onEsc\)/.test(bodySrc);
  const doc = { listeners: new Set() };
  const dom = new Map();
  const open = () => {
    const prev = dom.get(prevId);
    if (prev) {
      if (usesModalClose && prev.close) prev.close();
      else dom.delete(prevId);            // 노드만 제거 — 리스너는 남는다
    }
    const inst = { onEsc: {} };
    inst.close = () => { dom.delete(prevId); if (closeRemoves) doc.listeners.delete(inst.onEsc); };
    dom.set(prevId, inst);
    doc.listeners.add(inst.onEsc);
    return inst;
  };
  return { open, doc, dom, prevId };
}
[["app/profile.js showProfileUsageConvModal", profileJs, "showProfileUsageConvModal", "profileUsageConvOverlay"],
 ["admin/usage.js showUsageConvModal", adminUsageJs, "showUsageConvModal", "usageConvModalOverlay"]].forEach(
  ([label, src, fn, prevId]) => {
    const body = extractFn(src, fn);
    const sim = simulateLifecycle(body || "", prevId);
    sim.open();                       // loading 렌더
    const inst = sim.open();          // data 렌더 (재렌더)
    ok(`${label}: 재렌더 후 document keydown 리스너 1개 (누수 0)`, sim.doc.listeners.size === 1);
    inst.close();                     // 배경/× 로 닫기
    ok(`${label}: 닫은 뒤 document keydown 리스너 0개`, sim.doc.listeners.size === 0);
    for (let i = 0; i < 5; i++) { sim.open(); sim.open(); sim.dom.get(prevId).close(); }
    ok(`${label}: 열고 닫기 5회 반복 후에도 잔존 0 (선형 누적 없음)`, sim.doc.listeners.size === 0);
  });

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
