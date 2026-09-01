// side-panels — 우측 오버레이 사이드 패널의 **단독 열림(exclusive)** 계약.
//
// 화면 우측에 `position: fixed; right: 0` 로 겹쳐 뜨는 패널이 셋이다:
//   #attachSidePanel(첨부 파일, z 180) · #stepSidePanel(실행 단계, z 181) ·
//   #profileDrawer(유저 프로필, z 200 + #profileBackdrop z 195).
// 셋은 서로를 모르고 각자 `hidden` 만 벗겨 왔기 때문에 동시에 열릴 수 있었고, 그때
// 화면에는 z-index 가 높은 하나만 보이면서 아래 패널이 **열린 채 가려진다**. 사용자에게는
// "닫았는데 다시 열려 있는" 상태로 보이고, 가려진 패널의 리사이즈 핸들·닫기 버튼은
// 클릭이 위 패널에 먹혀 접근 불가가 된다.
//
// 그래서 열기 경로를 한 곳으로 모은다 — 각 패널 소유 모듈이 자기 close 를 등록하고
// (`registerSidePanel`), 열 때는 `openSidePanel(key, openFn)` 을 통과한다.
//
// **왜 여기서 DOM 을 «감추지» 않는가**: 닫기는 `hidden` 클래스 부착만이 아니다 —
// 단계 패널은 라이브 티커를 멈춰야 하고(`_stopStepPanelTicker`), 프로필은 backdrop 도
// 함께 내려야 한다. 그 정리 책임은 상태를 소유한 모듈에 있으므로 이 모듈은 **등록된
// close 를 호출**할 뿐 DOM 규칙을 두 벌로 만들지 않는다.
//
// **그러나 «보이지 않는 것은 조작 대상도 아니다» 는 여기가 책임진다** (§16.6 접근성):
// 세 패널의 숨김 규칙은 **한 벌이 아니다** — `#attachSidePanel`·`#stepSidePanel` 의
// `.hidden` 은 `display: flex !important; transform: translateX(100%)`(슬라이드 아웃 전환용)
// 라 화면 밖으로 밀려날 뿐 **여전히 포커스 가능하고 aria-live 도 계속 읽혔고**,
// `#profileDrawer` 는 `.drawer.hidden` 이 `display` 를 건드리지 않아 base 의
// `.hidden { display: none !important }` 가 그대로 걸린다(= 이미 제거된 상태).
// 따라서 이 동기화의 **실효 대상은 앞의 둘**이며, 프로필은 무해한 중복이다.
// 등록된 패널의 class 변화를 관찰해 `hidden` ↔ `inert`/`aria-hidden` 을 **한 규칙으로**
// 맞춘다 — 관찰 기반이라 닫기 경로(× 버튼 · 빈 목록 자동 닫기 · 배타 닫기)마다 복제되지
// 않는다. CSS 쪽에도 `visibility: hidden`(전환 후)을 함께 두어, `inert` 미지원 엔진에서
// «읽히지도 않는데 포커스는 가는» 최악의 조합이 되지 않게 한다.
//
// 이 모듈은 **의존성이 없다**(순수 DOM/자료구조). app.js ↔ app/*.js 가 이미 순환
// import 관계라, 여기서 다른 모듈을 import 하면 순환이 한 겹 더 늘고 등록(top-level
// 부수효과)이 TDZ·미평가 모듈에 걸릴 수 있다. 이 불변식은 구조 테스트가 강제한다.

/** key → { close, elementId } 등록부. 모듈 평가 시점(= 최초 import)에 각 소유자가 채운다. */
const _panels = new Map();

/** 재진입 가드 — close 순회 중 발생한 중첩 요청을 무시한다(무한 재귀 차단). */
let _closing = false;

/** 관찰 중인 element → MutationObserver (중복 관찰 방지). */
const _observed = new WeakMap();

function _elOf(entry) {
  return entry && entry.elementId ? document.getElementById(entry.elementId) : null;
}

/** `inert` **기능 검출** — 미지원 엔진에서 `el.inert = true` 는 예외를 던지지 않고 그냥
 *  expando 프로퍼티가 되므로, try/catch 는 폴백을 만들지 못한다(도달 불가 코드). */
const _HAS_INERT = typeof HTMLElement === "function" && "inert" in HTMLElement.prototype;

/** `hidden` ↔ `inert`/`aria-hidden` 동기화 — 숨은 패널이 Tab·스크린리더에 남지 않게 한다.
 *
 *  `inert` 미지원이면 `aria-hidden` 도 걸지 않는다 — «접근성 트리에서는 지워졌는데 Tab 은
 *  들어가는» 조합이 아무것도 안 한 상태보다 나쁘기 때문이다. 그 엔진에서 포커스를 실제로
 *  끊는 것은 CSS 의 `visibility: hidden`(chat.css `.hidden` 규칙)이다. */
function _syncInteractivity(el) {
  if (!el) return;
  if (!_HAS_INERT) return;
  const hidden = el.classList.contains("hidden");
  el.inert = hidden;
  if (hidden) el.setAttribute("aria-hidden", "true");
  else el.removeAttribute("aria-hidden");
}

/** 등록된 패널의 class 변화를 관찰해 위 동기화를 건다(닫기 경로마다 복제하지 않기 위해). */
function _observe(el, elementId) {
  if (!el) {
    // 유일하게 남아 있던 무음 실패 경로 — 등록 시 요소가 없으면 이후 어떤 재시도도 없다.
    console.error("[side-panels] 접근성 동기화를 걸 수 없습니다 — 등록 시 요소 부재:", elementId);
    return;
  }
  if (_observed.has(el)) return;
  if (typeof MutationObserver !== "function") return;   // 비-브라우저 환경(테스트 harness)
  const obs = new MutationObserver(() => _syncInteractivity(el));
  obs.observe(el, { attributes: true, attributeFilter: ["class"] });
  _observed.set(el, obs);
}

/**
 * 사이드 패널 소유자가 자기 닫기 함수를 등록한다.
 *
 * @param {string} key           패널 식별자 (`"attach"` | `"step"` | `"profile"` …)
 * @param {object} opts
 * @param {() => void} opts.close      이 패널을 닫는 함수 (이미 닫혀 있어도 안전해야 한다)
 * @param {string}     opts.elementId  대응 DOM id — 접근성 동기화와 사후 단언이 쓴다.
 */
export function registerSidePanel(key, { close, elementId = "" } = {}) {
  // ⚠ 조용한 no-op 금지: 속성명 오타(`colse:`) 한 글자로 그 패널이 배타에서 통째로
  //   이탈하는데 증상은 «수정 전 겹침» 과 100% 같다. 신호가 없으면 사용자 제보 전까지
  //   아무도 모른다 — 등록 실패는 반드시 콘솔에 남긴다.
  if (!key || typeof close !== "function") {
    console.error("[side-panels] 등록 실패 — key 와 close(함수)가 필요합니다.", { key, close, elementId });
    return;
  }
  if (!elementId) {
    console.error("[side-panels] 등록 실패 — elementId 가 필요합니다(접근성 동기화·사후 단언 대상).", { key });
    return;
  }
  _panels.set(key, { close, elementId });
  const el = document.getElementById(elementId);
  _observe(el, elementId);
  _syncInteractivity(el);   // 초기 상태(대개 hidden)도 맞춘다.
}

/**
 * `exceptKey` 를 뺀 나머지 사이드 패널을 모두 닫는다.
 *
 * 한 패널의 close 가 던져도 나머지는 닫는다: 여기서 중단하면 "한 개만 열린다" 계약이
 * 깨진 채 진행되고, 그 결과가 정확히 이 모듈이 없애려는 겹침 상태다. 다만 **삼키되
 * 침묵하지는 않는다** — 계속 진행하는 것과 말하지 않는 것은 별개의 결정이다.
 *
 * @param {string} exceptKey 지금 열려는 패널의 key (없으면 전부 닫는다)
 */
export function closeOtherSidePanels(exceptKey = "") {
  if (_closing) {
    // 순회 중 중첩 요청은 무시한다 — 다만 관측 가능하게 남긴다. close 가 다른 패널을
    // «여는» 코드가 생기면 그 배타 요청이 여기서 조용히 사라지기 때문이다.
    console.warn("[side-panels] close 순회 중 중첩 요청 무시:", exceptKey);
    return;
  }
  _closing = true;
  try {
    _panels.forEach((entry, key) => {
      if (key === exceptKey) return;
      try { entry.close(); } catch (e) {
        console.error("[side-panels] close 실패 — 패널이 열린 채 남을 수 있습니다:", key, e);
      }
      // 관찰(MutationObserver)은 마이크로태스크라 이 턴 안에서는 아직 반영되지 않는다.
      // 배타 경로만큼은 **동기**로 맞춘다 — 여는 쪽이 이어서 포커스를 옮기는데 그 사이
      // 닫힌 패널이 여전히 포커스 가능하면 계약이 한 틱 동안 깨진다. 관찰자는 나머지
      // 닫기 경로(× 버튼 · 빈 목록 자동 닫기)를 덮는 그물로 남는다.
      _syncInteractivity(_elOf(entry));
    });
  } finally {
    _closing = false;
  }
  _assertOnlyOneOpen(exceptKey);
}

/**
 * 사후 단언 — `exceptKey` 외에 열려 있는 패널이 남으면 콘솔에 보고한다.
 *
 * **열거 출처가 `_panels` 가 아니라 DOM 이다.** 등록부만 순회하면 이 계약이 정작 무서워하는
 * 사건 하나 — **등록을 잊은 패널** — 을 원리적으로 볼 수 없다. `[data-side-panel]` 표식을
 * 물으면 «등록 안 됐지만 화면에 있는» 패널이 결과 축에서 잡힌다. 술어는 그대로
 * `classList.contains("hidden")` 이다(무엇을 묻는가가 아니라 **누구에게 묻는가** 를 바꾼다).
 *
 * ⚠ **덮지 못하는 것 (정직 표기)**: 이 단언은 `closeOtherSidePanels` 안에서만 돈다. 따라서
 * **등록부의 문을 아예 타지 않고 연** 패널은 트리거 자체가 없어 관측되지 않는다 — 그 표면은
 * 정적 가드(S5·S7)만 덮는다.
 */
function _assertOnlyOneOpen(exceptKey) {
  const exceptId = (_panels.get(exceptKey) || {}).elementId || "";
  const seen = new Set();
  const leftover = [];
  const consider = (el, id) => {
    if (!el) return;
    // id 가 없어도 버리지 않는다 — 표식만 붙이고 id 는 안 붙이는 조합(선택자를 클래스로
    // 쓰는 코드에서 흔하다)에서 겹침이 콘솔에 한 줄도 남지 않게 된다.
    const label = id || `[data-side-panel="${el.dataset ? el.dataset.sidePanel : ""}"]` || el.className;
    if (!label || label === exceptId || seen.has(label)) return;
    seen.add(label);
    if (!el.classList.contains("hidden")) leftover.push(label);
  };
  // ① DOM 표식 전수 — 등록 누락 패널까지 포함된다.
  document.querySelectorAll("[data-side-panel]").forEach((el) => consider(el, el.id));
  // ② 등록부 — 표식이 없는(아직 붙이지 않은) 등록도 빠뜨리지 않는다.
  _panels.forEach((entry, key) => { if (key !== exceptKey) consider(_elOf(entry), entry.elementId); });
  if (leftover.length) {
    console.error("[side-panels] 단독 열림 계약 위반 — 닫히지 않은 패널:", leftover, "(여는 패널:", exceptKey, ")");
  }
  return leftover;
}

/**
 * 사이드 패널을 연다 — **모든 열기는 이 문을 통과한다**.
 *
 * `openFn` 안에 패널별 열기 절차(너비 복원·탭 전환·목록 적재)를 담는다. 열기를
 * 중앙화하지 않고 «닫기만» 공통화하면, 계약은 "opener 3곳이 각자 잊지 않고 배타를
 * 호출한다" 는 규율에 의존하게 되고 그 규율은 정적 검사로만 지켜진다. 이 문을 두면
 * 호출 누락이라는 실패 모드 자체가 사라진다.
 *
 * 호출자는 **열 수 있는지 먼저 확인한 뒤** 이 함수를 부른다 — 열지도 못하면서 남의
 * 패널만 닫는 것은 순수 손실이다.
 *
 * @param {string} key    이 패널의 등록 key
 * @param {() => void} openFn  실제 열기 절차 (마지막에 `hidden` 을 벗긴다)
 */
export function openSidePanel(key, openFn) {
  if (typeof openFn !== "function") {
    console.error("[side-panels] openSidePanel 에 열기 함수가 없습니다:", key);
    return;
  }
  if (!_panels.has(key)) {
    console.error("[side-panels] 미등록 패널을 엽니다 — 배타 대상에서 빠집니다:", key);
  }
  closeOtherSidePanels(key);
  // ⚠ 닫기는 **이미 일어났다**. `openFn` 이 던지면 "열지도 못하면서 남의 패널만 닫은" 상태가
  //   되는데, 그건 이 모듈이 스스로 금지한 형태다. 사전 검사(`if (!panel) return`)는 요소
  //   부재만 덮고 렌더 예외는 못 덮으므로, 최소한 **관측 가능**하게 만든다 — close 예외에
  //   대해 "삼키되 침묵하지 않는다" 를 택했으니 open 쪽만 침묵하면 비대칭이다.
  try {
    openFn();
  } catch (e) {
    console.error("[side-panels] 열기 실패 — 다른 패널은 이미 닫힌 상태입니다:", key, e);
  }
  // 성공·실패 **양쪽에서** 동기화한다 — 여기서 건너뛰면 openFn 이 `hidden` 을 벗긴 뒤에
  // 던졌을 때 «보이는데 inert/aria-hidden» 조합이 남는다. 「hidden 여부와 inert 가 항상
  // 일치」를 불변식으로 두면 openFn 의 문장 순서에 기대지 않아도 된다.
  _syncInteractivity(_elOf(_panels.get(key)));
}

/** 등록된 패널 key 목록 (테스트·디버깅용 — 등록 누락을 밖에서 확인할 수 있게 한다). */
export function registeredSidePanelKeys() {
  return Array.from(_panels.keys());
}

/** 등록된 패널의 DOM id 목록 (구조 테스트가 index.html 전수와 대조한다). */
export function registeredSidePanelElementIds() {
  return Array.from(_panels.values()).map((e) => e.elementId).filter(Boolean);
}
