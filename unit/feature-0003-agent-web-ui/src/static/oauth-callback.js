/* feature-0041 — 인가 완료 화면.
 *
 * OAuth 흐름은 인가 코드를 `redirect_uri` 로 되돌려준다. 클라이언트가 자체 콜백 서버를
 * 돌리면 그쪽 화면이 뜨지만, 스크립트·수동 연동은 그런 서버가 없어서 **브라우저 오류 화면**
 * 이나 손으로 만든 평문 페이지를 보게 된다. 이 주소를 `redirect_uri` 로 등록하면 우리가
 * 제대로 된 화면을 준다.
 *
 * ⚠ 코드를 화면에 띄우는 것은 그 자체로 위험이 아니다 — PKCE 때문에 `code_verifier` 없이는
 * 교환할 수 없다. 다만 사용자가 **다른 사람에게 넘기는** 경로는 남으므로 그 경고를 띄운다.
 * 서버는 이 페이지에서 아무것도 하지 않는다(코드는 URL 에만 있고, 정적 파일만 서빙된다).
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var params = new URLSearchParams(window.location.search);
  var code = params.get("code");
  var err = params.get("error");
  var errDesc = params.get("error_description");

  var MSG = {
    access_denied: "요청을 거부했습니다.",
    invalid_request: "요청이 올바르지 않습니다.",
    invalid_scope: "요청한 권한을 지원하지 않습니다.",
  };

  function show(id) { $(id).classList.remove("aic-hidden"); }

  if (code) {
    $("cbCode").textContent = code;
    show("cbOk");
    $("cbCopy").addEventListener("click", function () {
      var done = function () { $("cbStatus").textContent = "복사했습니다."; $("cbStatus").setAttribute("data-kind", "ok"); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done).catch(fallback);
      } else { fallback(); }
      function fallback() {
        // clipboard API 는 보안 컨텍스트·권한에 따라 막힌다. 조용히 실패하면 사용자는
        // 붙여넣기가 안 되는 이유를 모른다 — 직접 선택하도록 안내한다.
        var r = document.createRange();
        r.selectNodeContents($("cbCode"));
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        $("cbStatus").textContent = "복사가 차단되었습니다 — 선택된 텍스트를 직접 복사하세요.";
        $("cbStatus").setAttribute("data-kind", "error");
      }
    });
  } else if (err) {
    $("cbErrMsg").textContent = MSG[err] || "연결이 완료되지 않았습니다.";
    $("cbErrRaw").textContent = err + (errDesc ? ": " + errDesc : "");
    show("cbErr");
  } else {
    show("cbNone");
  }
})();
