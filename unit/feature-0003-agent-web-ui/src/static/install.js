/* feature-0003 client-entry-gate — 설치 안내 화면의 동작.
 *
 * 서버가 준 값만 그린다. 버전·크기·지문·게시일·릴리스 노트는 전부
 * `GET /api/ai/client/entry` 에서 오고, 그 응답은 **실물과 대조해 통과한 것만** 담는다
 * (`routers/client_release.current_release`). 여기서 값을 만들거나 추정하지 않는다 —
 * 화면이 조립하면 「받기는 보이는데 파일은 없는」 상태가 생긴다 (feature-0046 §P0-I).
 *
 * ⚠ 딥링크(`dqa-connect://open?…`) 문자열도 서버가 조립한다. 스킴의 정본은
 *   `shared/dqa_identity` 이고, 프런트가 직접 만들면 개명이 도달하지 않는 자리가 하나
 *   더 생긴다 — 그 리터럴이 21곳에 흩어져 있던 것이 그 모듈이 생긴 이유다.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  /* 이 기기에 DQA 앱이 **존재할 수 있는가**. 세 값(true/false/null)이다.
   *
   * ⚠ 「Windows 가 아니다」와 「모르겠다」를 가른다. share.js 의 같은 판정은 2치라서
   *   판정 불가를 «미지원» 으로 떨어뜨리는데, 저기는 그것이 안전한 방향이었다(앱 전용을
   *   강제하지 않음). 여기는 반대다 — 미지원으로 떨어뜨리면 **받기 버튼 자체가 사라진다.**
   *   그래서 확실히 다른 OS 일 때만 «받을 수 없음» 으로 가고, 모르면 받기를 보여 준다.
   *   받기 블록은 지원 OS 를 문자로 함께 말하므로 오판의 대가가 작다.
   */
  function isWindows() {
    try {
      var nav = window.navigator || {};
      var hint = String((nav.userAgentData && nav.userAgentData.platform) ||
                        nav.platform || nav.userAgent || "");
      if (!hint) return null;
      if (/win/i.test(hint)) return true;
      if (/mac|linux|android|iphone|ipad|cros/i.test(hint)) return false;
      return null;
    } catch (_) {
      return null;
    }
  }

  /* 바이트를 사용자가 탐색기에서 보는 단위로. Windows 의 「MB」는 MiB 다. */
  function humanSize(bytes) {
    var n = Number(bytes);
    if (!isFinite(n) || n <= 0) return "";
    var mb = n / 1048576;
    return (mb >= 100 ? Math.round(mb) : Math.round(mb * 10) / 10) + "MB";
  }

  /* ISO8601 → `YYYY-MM-DD` (보는 사람의 시간대). 파싱 실패는 빈 문자열 — 틀린 날짜를
     그리느니 그 조각을 빼는 편이 낫다. */
  function localDate(iso) {
    try {
      var d = new Date(String(iso));
      if (isNaN(d.getTime())) return "";
      var pad = function (v) { return (v < 10 ? "0" : "") + v; };
      return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    } catch (_) {
      return "";
    }
  }

  function show(id) {
    var el = $(id);
    if (el) el.hidden = false;
  }

  function hide(id) {
    var el = $(id);
    if (el) el.hidden = true;
  }

  /* ─── 파일 지문 복사 ─────────────────────────────────────────────────────
   * 눌렸다는 것을 **버튼 안에서** 말한다 — 이 저장소의 다른 복사 버튼과 같은 관례
   * (`복사됨`). 실패를 조용히 넘기지 않는다: 클립보드가 막힌 환경(비보안 컨텍스트 등)
   * 에서는 대신 값을 선택해 주고 그 사실을 라벨로 말한다.
   */
  //: 지금 화면이 말하고 있는 지문. **한 번만** 배선하고 값만 갈아 끼운다 — 매 렌더마다
  //: 리스너를 더하면 「다시 시도」를 두 번 누른 사람의 클립보드 동작이 중복 실행된다.
  var currentHash = "";

  function wireCopy() {
    var btn = $("copyHashBtn");
    if (!btn) return;
    var idle = btn.textContent;
    var timer = null;

    function say(label) {
      btn.textContent = label;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { btn.textContent = idle; }, 1600);
    }

    function selectHash() {
      try {
        var node = $("factHash");
        var range = document.createRange();
        range.selectNodeContents(node);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        return true;
      } catch (_) {
        return false;
      }
    }

    btn.addEventListener("click", function () {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(currentHash).then(
          function () { say("복사됨"); },
          function () { say(selectHash() ? "직접 복사" : "복사 실패"); }
        );
        return;
      }
      say(selectHash() ? "직접 복사" : "복사 실패");
    });
  }

  function renderRelease(release) {
    $("downloadBtn").href = release.download_url;
    /* 파일명을 명시한다 — 저장 대화상자에 뜨는 이름이 안내와 같아야 한다. */
    $("downloadBtn").setAttribute("download", release.filename);

    var bits = [release.version];
    var size = humanSize(release.size);
    if (size) bits.push(size);
    bits.push("Windows 10 · 11");
    var when = localDate(release.published_at);
    if (when) bits.push(when + " 게시");
    $("downloadMeta").textContent = bits.join(" · ");

    if (release.notes) {
      $("releaseNotes").textContent = release.notes;
      show("releaseNotes");
    }

    $("factName").textContent = release.filename;
    $("factSize").textContent = (size ? size + " · " : "") + release.size + " 바이트";
    $("factHash").textContent = release.sha256;
    $("verifyCmd").textContent =
      "Get-FileHash .\\" + release.filename + " -Algorithm SHA256";
    currentHash = release.sha256;

    show("actDownload");
    show("steps");
    show("verify");
  }

  /* 상태는 하나만 보인다. 전환할 때마다 나머지를 확실히 접는다 — 「다시 시도」로 돌아오는
     경로가 생기면서 «앞 상태가 남아 두 개가 보이는» 형태가 가능해졌다. */
  var STATES = ["actLoading", "actDownload", "actOtherOs", "actNoRelease", "actUnavailable"];

  function only(id) {
    for (var i = 0; i < STATES.length; i++) {
      if (STATES[i] !== id) hide(STATES[i]);
    }
    /* 받기 블록에 딸린 것들 — 받을 것이 없는 상태에서 남아 있으면 안 된다.
       `renderRelease` 가 다시 켠다. */
    hide("steps"); hide("verify"); hide("releaseNotes");
    if (id) show(id);
  }

  /* 이미 설치한 사람의 출구. **설치기 배포 여부와 별개 축이다** — 배포본을 철회해도 이미
     설치한 사람은 앱을 열 수 있어야 한다. 링크를 만들지 못했으면 그 줄 자체를 그리지 않는다
     (눌러도 아무 일이 없는 링크는 «안내가 가리키는 것이 실재하지 않는» 형태다). */
  function renderAppLink(link) {
    if (!link) return hide("alreadyInstalled");
    $("openAppLink").href = link;
    show("alreadyInstalled");
  }

  function render(data) {
    var release = data && data.release;
    var windows = isWindows();

    if (windows === false) {
      /* 다른 OS — 받을 수도, 열 수도 없다. 받기 대신 «어디서 열면 되는가» 를 말한다. */
      only("actOtherOs");
      hide("alreadyInstalled");
      return;
    }

    renderAppLink(data && data.app_link);

    if (!release) {
      only("actNoRelease");
      return;
    }
    only("actDownload");
    renderRelease(release);
  }

  /* ⚠ **«못 물어봤다» 를 «없다» 로 말하지 않는다.** 둘은 사용자가 할 일이 다르다 —
     전자는 다시 시도, 후자는 관리자 문의다. 합쳐 놓으면 통신 장애를 겪은 사람이 있지도
     않은 문의로 보내진다(codex 적대 리뷰 2026-09-10 P2-5). */
  function failed() {
    only("actUnavailable");
    hide("alreadyInstalled");
  }

  function load() {
    only("actLoading");
    try {
      fetch("/api/ai/client/entry", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (body) { body ? render(body) : failed(); })
        .catch(failed);
    } catch (_) {
      failed();
    }
  }

  wireCopy();
  var retry = $("retryBtn");
  if (retry) retry.addEventListener("click", load);
  load();
})();
