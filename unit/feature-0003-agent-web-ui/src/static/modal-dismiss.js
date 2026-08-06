// modal-dismiss.js — 모달 바깥(어두운 배경) 클릭으로 닫는 동작의 **저장소 단일 primitive**.
//
// 왜 별도 모듈인가: 이 앱은 ES module 번들이 둘이다(작업 화면 `app.js` 트리 / 관리 콘솔
// `admin.js` 트리). 한쪽에 primitive 를 두면 다른 쪽은 복제할 수밖에 없고, **그 복제가 바로
// 이 결함을 만든 기전**이다 — 같은 판정 로직이 9곳에 흩어져 있었고 그중 6곳은 `click`,
// 3곳은 `mousedown`/`click` 으로 제각각 굳어 있었다. 양 번들이 이 파일 하나를 import 하게
// 해서 "새 모달이 옛 패턴을 복사하는" 경로 자체를 없앤다. 회귀 잠금은
// `tests/verify_modal_backdrop_dismiss.mjs` 가 `src/static/**/*.js`(vendor 제외)를 **재귀 walk**
// 하며, 리스너 핸들러 본문에서 "수신자 자신을 `target` 과 비교하는" 형태를 식별자·표기 변형에
// 무관하게 검출한다(파일 목록 하드코딩 금지 — 그러면 이미 고친 파일만 보게 된다).
//
// **범위 경계**: 본 primitive 는 *모달 배경(backdrop/overlay) dismiss* 만 담당한다. 드롭다운·
// 컨텍스트 메뉴의 `document` 레벨 outside-click 해제(`admin/products.js`·`admin/datasources.js`·
// `graph/graph-core.js` 등)는 같은 뿌리(click target 승격)를 공유하지만 **다른 UX 범주**라
// 이 통일 대상이 아니다 — "배경 dismiss 잔존 0" 주장은 그 경계 안에서만 참이다.
//
// ─── 계약 ──────────────────────────────────────────────────────────────────
// **누름(pointerdown)과 뗌(pointerup)이 둘 다 backdrop 자신**일 때만 dismiss.
//   - 어느 한쪽이라도 패널(자식) 위면 무시 → 입력 필드 드래그 선택 중 이탈로 닫히지 않는다.
//   - 주 버튼(좌클릭/터치 primary)만 — 우클릭·보조 버튼은 무시.
//   - pointercancel(스크롤 제스처 전환 등) 은 press 상태를 해제해 유령 dismiss 를 막는다.
//
// 원 결함: `click` 리스너 + `e.target === backdrop` 검사. DOM `click` 의 target 은
// mousedown/mouseup 두 지점의 **공통 조상**이라, 패널 안에서 누르고 배경에서 떼거나(텍스트
// 드래그 선택 후 바깥에서 놓기) 그 반대여도 target 이 backdrop 으로 승격돼 모달이 닫혔다 —
// 사용자 관점에선 "down 만 해도 / up 만 해도 닫힌다". `mousedown` 단독 판정은 그보다 더
// 이르게, 뗌을 보지도 않고 닫았다.
//
// ─── 구현 주의 (§18.8 ux·design 패널이 실증한 결함의 봉인) ────────────────
//  (1) **implicit pointer capture 해제** — 터치·펜 같은 direct-manipulation 포인터는
//      `pointerdown` 대상에 브라우저가 자동으로 포인터 캡처를 걸어, 이후 `pointerup` 이 실제로
//      뗀 위치와 **무관하게 그 대상으로 retarget** 된다(마우스는 캡처 없음). 해제하지 않으면
//      터치에서 계약이 "누른 위치가 배경이면 닫힘" 으로 무너져 원 결함이 그대로 남는다.
//      배경에서 시작한 제스처에 대해서만 해제한다 — 패널 안에서 시작한 제스처(터치 텍스트
//      선택 등)의 캡처는 그 동작이 의존하는 것이라 건드리지 않는다.
//  (2) **판정은 pointer 2단, 실행은 `click`** — 판정을 끝낸 뒤 실행을 click 으로 미루면
//      (a) 터치 compat click 의 히트테스트는 click dispatch **전에** 끝나므로, dispatch 중에
//      노드를 제거해도 아래 레이어가 눌리지 않는다(`pointerup` 에서 제거하면 눌린다 — ghost
//      click), (b) 브라우저가 click 을 발행하지 않는 상호작용(스크롤바 드래그 등)이 자연히
//      제외된다. `click` 은 **트리거일 뿐 판정 근거가 아니다** — 결함의 원인이던 target
//      공통-조상 승격은 `armed` 플래그가 이미 걸러낸다.
//  (3) **상태 수명** — 장전(`armed`)은 **제스처 1회분**이다. `pointerup` 이 `downOk` 를 즉시
//      소비하고, `click` 이 `armed` 를 소비한다. 이 소비가 없으면 "배경에서 down+up 했는데
//      브라우저가 click 을 발행하지 않은" 제스처가 장전 상태를 **무기한 남기고**, 그 뒤 도착한
//      click 하나가 사용자가 누른 적 없는 모달을 닫는다. 나아가 물리 제스처는 언제나
//      `pointerdown` 으로 시작해 상태를 리셋하므로, **선행 pointerdown 없이 오는 click 은
//      정의상 합성 이벤트**다 — `e.isTrusted` 로 배제한다. 즉 순수 합성 click(`el.click()`)은
//      어떤 상태에서도 배경 dismiss 를 일으키지 않는다(의도 — 물리 포인터 제스처만 인정).
//
// ESC·`×` 닫기 경로는 각 모달이 따로 배선하며 본 primitive 와 무관하게 항상 살아 있다 —
// 배경 판정이 보수적이어도 사용자가 갇히지 않는다.
export function bindBackdropDismiss(backdrop, onDismiss) {
  let activeId = null;   // 주 포인터 1개만 추적 — 보조 터치가 주 상호작용을 흔들지 않게.
  let downOk = false;    // 누름이 배경 자신이었나 (이어지는 pointerup 이 소비)
  let armed = false;     // 누름·뗌이 둘 다 배경이었나 (이어지는 click 이 소비)
  const reset = () => { activeId = null; downOk = false; armed = false; };

  backdrop.addEventListener("pointerdown", (e) => {
    if (e.isPrimary === false) return;   // 멀티터치 2번째 이후 — 주 포인터 상태 보존
    reset();
    activeId = e.pointerId;
    if (e.target !== backdrop) return;
    // (1) 캡처 해제는 **무조건 시도**한다. `hasPointerCapture` 를 선행 조건으로 두면 그 메서드가
    // 없거나 캡처를 다르게 보고하는 엔진에서 조용히 건너뛰어 터치 계약이 구 결함으로 되돌아간다
    // (fail-open). 캡처가 없을 때의 throw 만 삼킨다.
    try { e.target.releasePointerCapture(e.pointerId); } catch (_) { /* 캡처 없음 — 무해 */ }
    downOk = e.button === 0;
  });
  backdrop.addEventListener("pointercancel", (e) => { if (e.pointerId === activeId) reset(); });
  backdrop.addEventListener("pointerup", (e) => {
    if (e.pointerId !== activeId) return;
    // `button` 재검사 안 함 — 누름 시점에 이미 걸렀고(`downOk`), `pointerup` 의 `button` 을
    // -1 로 보고하는 환경에서 정상 dismiss 가 조용히 죽는 쪽이 더 나쁘다.
    armed = downOk && e.target === backdrop;
    downOk = false;   // 이 뗌으로 누름을 소비 — 다음 제스처로 이월 금지
  });
  backdrop.addEventListener("click", (e) => {   // (2) 실행 단계
    const ok = armed && e.isTrusted && e.target === backdrop;
    reset();
    if (ok) onDismiss(e);
  });
}
