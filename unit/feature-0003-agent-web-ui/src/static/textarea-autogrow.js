// textarea-autogrow.js
// 우측 하단 resize 핸들(native grabber)을 더블클릭하면 입력된 텍스트의
// 수직 크기만큼 textarea 높이를 자동 확장한다.
//
// 동작 범위: resize 가 vertical 또는 both 인 모든 textarea (동적 생성 포함).
//   - index.html  : `.field textarea` (예: #promptContent)
//   - admin.html  : `.admin-prompt-textarea`
//   - share.html  : 동적 생성 textarea
//
// 좌표 판정: 네이티브 resize 핸들은 별도 DOM 노드가 아니므로, 더블클릭 좌표가
// textarea 우측 하단의 핸들 영역(약 GRAB_PX) 안일 때만 자동 확장을 수행한다.
// 본문 더블클릭(단어 선택)은 그대로 통과시켜 기존 UX 를 해치지 않는다.
(function () {
  "use strict";

  // 우측 하단 핸들로 인정할 영역(px). 네이티브 grabber 가 대략 이 크기다.
  var GRAB_PX = 18;
  // 자동 확장 상한(px). 무한정 늘어나 레이아웃이 깨지는 것을 막는다.
  // 0 이하면 상한 없음.
  var MAX_PX = 600;

  function isAutoGrowTarget(el) {
    if (!el || el.tagName !== "TEXTAREA") return false;
    var resize = getComputedStyle(el).resize;
    return resize === "vertical" || resize === "both";
  }

  // 더블클릭 좌표가 우측 하단 핸들 영역 안인가.
  function isInResizeGrabber(el, evt) {
    var rect = el.getBoundingClientRect();
    var fromRight = rect.right - evt.clientX;
    var fromBottom = rect.bottom - evt.clientY;
    return fromRight >= 0 && fromRight <= GRAB_PX && fromBottom >= 0 && fromBottom <= GRAB_PX;
  }

  // 내용 높이에 맞춰 textarea 를 확장한다.
  function fitToContent(el) {
    // border-box 보정: scrollHeight 는 padding 포함, border 는 별도.
    var cs = getComputedStyle(el);
    var borderY = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
    var extra = cs.boxSizing === "border-box" ? borderY : 0;

    var prev = el.style.height;
    el.style.height = "auto";
    var target = el.scrollHeight + extra;
    el.style.height = prev; // 측정 후 원복(점프 방지)

    if (MAX_PX > 0 && target > MAX_PX) target = MAX_PX;
    el.style.height = target + "px";
  }

  document.addEventListener(
    "dblclick",
    function (evt) {
      var el = evt.target;
      if (!isAutoGrowTarget(el)) return;
      if (!isInResizeGrabber(el, evt)) return; // 본문 더블클릭은 통과
      evt.preventDefault();
      fitToContent(el);
    },
    true // capture: 본문 단어선택 동작보다 먼저 핸들 영역을 가로챈다.
  );
})();
