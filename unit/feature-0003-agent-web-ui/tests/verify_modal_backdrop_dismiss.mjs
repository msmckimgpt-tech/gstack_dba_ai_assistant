// verify_modal_backdrop_dismiss.mjs
// modal-backdrop-dismiss: 좌측 사이드바 항목(대화/폴더)에서 열리는 모달을 "바깥 어두운 배경을
// 클릭했을 때만" 닫는다 — 즉 누름(pointerdown)과 뗌(pointerup)이 **둘 다 backdrop 자신**일 때만.
//
//   [결함] 기존 구현은 backdrop 에 `click` 리스너 + `e.target === backdrop` 검사였다. DOM `click`
//          의 target 은 mousedown/mouseup 두 지점의 **공통 조상**이라, 패널 안에서 누르고 배경에서
//          떼거나(텍스트 드래그 선택 후 바깥 놓기) 그 반대일 때도 target 이 backdrop 으로 승격돼
//          모달이 닫혔다 — 사용자 관점 "down 만 해도 / up 만 해도 닫힌다".
//   [수정] app.js `bindBackdropDismiss(backdrop, onDismiss)` primitive 단일화 + 전 모달 배선 교체.
//
// 검증 2축:
//   (A) 동작 — app.js 에서 헬퍼 본문을 추출해 최소 DOM 이벤트 shim 위에서 실제로 실행하고
//       press/release 조합별 dismiss 여부를 단언한다(정적 문자열 검사로는 잡히지 않는 계약).
//   (B) 배선 — 사이드바 항목이 여는 모달 6종이 전부 헬퍼를 쓰고, 결함 패턴(click + target===backdrop)
//       이 app.js / app/sidebar.js 에 잔존하지 않음을 단언(회귀 잠금).
//
// 실행: node verify_modal_backdrop_dismiss.mjs
//   (순수 정적 + 자체 이벤트 shim — jsdom/네트워크 비의존. 실제 렌더링/마우스 동작의 최종 확인은
//    PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const sidebarJs = readFileSync(join(STATIC, "app", "sidebar.js"), "utf8");

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
const helperSrc = extractFn(appJs, "bindBackdropDismiss");
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

ok("[터치] 패널에서 누르고 배경에서 뗌 → 안 닫힘 (패널 내부 제스처의 캡처는 유지)",
  scenario(({ backdrop, panel, press }) => press(panel, backdrop, { pointerType: "touch" })) === 0);

ok("배경 우클릭(button=2) → 안 닫힘",
  scenario(({ backdrop, press }) => press(backdrop, backdrop, { button: 2 })) === 0);

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

ok("비-primary 포인터(멀티터치 2번째 손가락) 단독 → 안 닫힘",
  scenario(({ backdrop, press }) => press(backdrop, backdrop, { isPrimary: false, pointerId: 2 })) === 0);

// ★ 멀티터치 간섭 회귀 잠금 (ux 패널 P3-2) — 화면에 다른 손가락이 얹혀 있어도 주 포인터의
//   정상 배경 탭은 닫혀야 한다(보조 pointerdown 이 주 포인터 상태를 지우면 안 됨).
ok("보조 손가락이 얹힌 채 주 포인터로 배경 탭 → 닫힘",
  scenario(({ backdrop, press }) => {
    backdrop.fire("pointerdown", { target: backdrop, isPrimary: false, pointerId: 2 });
    press(backdrop, backdrop, { pointerId: 1 });
  }) === 1);

// ── (B) 배선 검증 (회귀 잠금) ────────────────────────────────────────────────
ok("app.js: bindBackdropDismiss export", /export function bindBackdropDismiss\(/.test(appJs));

// 사이드바 항목이 여는 모달 4종(app.js) — 공유 링크 설정 / 참여 허용 확인 / 공유 / 대화 설정.
const APP_MODALS = ["promptShareExpiry", "confirmShareJoinable", "openShareDialog", "openConversationSettings"];
APP_MODALS.forEach((fn) => {
  const body = extractFn(appJs, fn);
  ok(`${fn}: 헬퍼로 배경 dismiss 배선`, !!body && body.includes("bindBackdropDismiss(backdrop"));
  ok(`${fn}: click+target===backdrop 결함 패턴 부재`,
    !!body && !/backdrop\.addEventListener\(\s*["']click["']/.test(body));
});

// 사이드바 항목이 여는 모달 2종(app/sidebar.js) — 폴더 설정 / 폴더로 이동.
const SIDEBAR_MODALS = ["openFolderSettings", "openMoveConversationDialog"];
SIDEBAR_MODALS.forEach((fn) => {
  const body = extractFn(sidebarJs, fn);
  ok(`${fn}: 헬퍼로 배경 dismiss 배선`, !!body && body.includes("bindBackdropDismiss(backdrop"));
  ok(`${fn}: click+target===backdrop 결함 패턴 부재`,
    !!body && !/backdrop\.addEventListener\(\s*["']click["']/.test(body));
});

ok("sidebar.js: app.js 로부터 bindBackdropDismiss import", /bindBackdropDismiss/.test(sidebarJs.slice(0, sidebarJs.indexOf("\n\n"))) || /import\s*\{[^}]*bindBackdropDismiss/s.test(sidebarJs));

// 파일 전역 — 결함 패턴이 어디에도 남지 않았는지(신규 모달이 옛 패턴을 복사하는 drift 차단).
ok("app.js 전역: backdrop click dismiss 잔존 0",
  !/backdrop\.addEventListener\(\s*["']click["']\s*,\s*\(e\)\s*=>\s*\{\s*if\s*\(e\.target === backdrop\)/.test(appJs));
ok("sidebar.js 전역: backdrop click dismiss 잔존 0",
  !/backdrop\.addEventListener\(\s*["']click["']\s*,\s*\(e\)\s*=>\s*\{\s*if\s*\(e\.target === backdrop\)/.test(sidebarJs));

// ESC / × 버튼 닫기 경로는 이번 변경의 영향 밖 — 회귀하지 않았음을 함께 잠근다.
[...APP_MODALS.map((f) => [appJs, f]), ...SIDEBAR_MODALS.map((f) => [sidebarJs, f])].forEach(([src, fn]) => {
  const body = extractFn(src, fn);
  ok(`${fn}: ESC 닫기 유지`, !!body && /e\.key === "Escape"/.test(body));
  ok(`${fn}: × 닫기 버튼 유지`, !!body && body.includes(".share-mgr-close"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
