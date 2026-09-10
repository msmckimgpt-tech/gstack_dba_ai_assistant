/* DQA 앱 전용 진입 게이트 — 평범한 웹브라우저로 들어온 사람을 설치 안내로 보낸다.
 *
 * 사용자 결정 2026-09-10: 「DQA 클라이언트 외, 일반적인 웹브라우저로 접속할 경우 클라이언트
 * 설치 안내페이지로 연결」. 대상은 **앱 루트(`/`)와 관리 콘솔(`/admin`)** 이고, 탈출구는
 * 두지 않는다(앱 전용 일관 — 2026-09-08 공유 참여·fork 결정과 같은 방향).
 *
 * ## 왜 서버가 아니라 여기인가
 *
 * 「지금 앱 창 안인가」의 신호는 **브리지 좌표 하나**다(feature-0003
 * AC-20260908T125500-share-client-entry-3). 그 좌표는 앱이 창을 열 때 URL 로 오고
 * (`client/appwindow.panel_url`), 곧바로 주소에서 지워져 `sessionStorage` 로 옮겨간다.
 * 즉 **서버는 두 번째 요청부터 그 사실을 볼 수 없다** — 서버에서 막으면 앱 창이 새로고침
 * 한 번에 자기 자신에게 차단당한다. 판정은 그 신호가 있는 자리에서 한다.
 *
 * ## 왜 classic·동기 스크립트인가
 *
 * `<head>` 에서 **파싱을 멈추고** 판정해야 브라우저 방문자가 SPA 를 반쯤 그린 뒤 튕기는
 * 깜빡임이 없다. 그리고 ES module(deferred)로 두면 `app.js` 와 같은 적재 실패 축을 공유해,
 * 모듈 하나가 깨지는 날 **앱 창이 자기를 브라우저로 오인**한다. 이 파일은 의존이 0 이다.
 *
 * ## 열지 못하면 열어 준다 (fail-open)
 *
 * 판정할 수 없으면 **통과시킨다.** 이 저장소가 공유 화면에서 이미 채택한 규칙과 같다 —
 * 「모르는 채 길을 닫는 쪽이 더 나쁘다」(`static/share.js` appPlatformSupported). 잘못
 * 막으면 정당한 사용자가 제품 전체를 잃고, 잘못 통과시키면 그 사람은 앱을 권하는 화면을
 * 못 볼 뿐이다. 두 오류의 크기가 다르다.
 *
 * ⚠ **이것은 표시이지 집행이 아니다.** 자격은 서버의 로그인 세션·RBAC 이 정한다. 여기서
 *   보내는 것은 경로를 하나로 모으는 UX 결정이며, 우회해서 얻는 것은 권한이 아니라
 *   「어느 화면에서 봤는가」뿐이다(share.js 가 같은 사실을 같은 이유로 적어 둔다).
 */
(function () {
  "use strict";

  /* 게이트 대상. **열거한 자리만** 막는다 — 기본값이 「통과」라야 새 페이지가 생겨도
     모르는 사이에 닫히지 않는다(공유 화면 allow-list 극성 사고의 반대 축). */
  var GATED = { "/": 1, "/index.html": 1, "/admin": 1 };

  /* 설치 안내. 이 경로 자체는 게이트 대상이 아니다(이 파일을 싣지 않는다). */
  var GUIDE_PATH = "/install";

  /* ── 외부 AI 인가의 «로그인 순간» 은 브라우저에만 있다 ───────────────────────
   *
   * `GET /api/ai/oauth/authorize` 는 외부 AI 도구(Claude Desktop·Codex CLI 등)가 **시스템
   * 브라우저**로 여는 사람-동의 화면이다. 미로그인이면 서버가 `/?next=<그 인가 URL>` 로
   * 되돌린다(`routers/oauth_as.oauth_authorize`) — 로그인 UI 가 SPA 안에만 있기 때문이다.
   * 그 착지점을 그대로 막으면 `next` 와 인가 요청 정보가 사라지고, **외부 AI 연결을 브라우저
   * 에서 끝낼 방법이 아예 없어진다**(codex 적대 리뷰 2026-09-10 P1-1). DQA 앱의 WebView2 는
   * 로그인 저장소가 브라우저와 별개라 앱에서 로그인해도 그 흐름이 복구되지 않는다.
   *
   * 그래서 **그 착지점 하나만** 통과시킨다. `/ai/connect`(익명·브라우저 전용)와 같은 계열의
   * 예외이며, 사용자 결정의 「탈출구 없음」(= 앱을 못 쓰는 사람에게 주는 우회로)과 다른 축이다
   * — 이것은 사람이 고르는 우회로가 아니라 **기계 흐름이 요구하는 로그인 한 순간**이다.
   *
   * ⚠ **알려진 성질**: 주소에 이 `next` 를 손으로 붙이면 게이트를 지나 SPA 를 볼 수 있다.
   *   이 게이트는 처음부터 **표시이지 집행이 아니며**(자격은 로그인 세션·RBAC 이 집행),
   *   공유 화면이 같은 사실을 같은 이유로 적어 둔 것과 같은 등급이다. 적어 두지 않으면 다음
   *   사람이 이 유도를 통제로 오인하고 그 위에 무언가를 얹는다.
   */
  var LOGIN_RETURN_PREFIX = "/api/ai/oauth/authorize";

  function isLoginReturnForOauth(query) {
    try {
      var next = query.get("next");
      return !!next && String(next).indexOf(LOGIN_RETURN_PREFIX) === 0;
    } catch (_) {
      return false;
    }
  }

  /* ⚠ **규약 정본은 `static/app/client-bridge.js` 다.** 아래 셋은 그 사본이고, 사본이
     갈리면 「앱 안인데 앱 밖으로 보이는」 화면이 생긴다. 그래서 값을 여기에 적되
     `tests/test_client_entry_gate.py` 가 두 파일이 같은 문자열을 쓰는지 단정한다 —
     이 저장소가 명칭 SSOT(`shared/dqa_identity.py` + `test_name_ssot.py`)에서 쓰는
     것과 같은 형태다. import 로 묶지 않는 이유는 위 「왜 classic·동기」에 있다. */
  var PORT_PARAM = "client_port";
  var NONCE_PARAM = "client_nonce";
  var STORAGE_KEY = "dqa.bridge";

  /* 저장소가 **쓸 수 있는 상태인가.** 읽기만 보면 부족하다 — `getItem` 은 멀쩡한데
     `setItem` 이 던지는 창(quota 초과 등)에서는 정본 모듈이 좌표를 **보관하지 못한** 채
     조용히 끝나고, 그 다음 화면에서 읽기는 예외 없이 빈 값을 낸다. 그 빈 값을 「앱이 아니다」로
     읽으면 정상 앱 창을 쫓아낸다(codex 적대 리뷰 2026-09-10 P2-3). 그래서 여기서는 «읽을 수
     있는가» 가 아니라 «이 창에서 신호가 살아남을 수 있는가» 를 묻는다. */
  function storageIsUsable() {
    try {
      var probe = "dqa.gate.probe";
      sessionStorage.setItem(probe, "1");
      sessionStorage.removeItem(probe);
      return true;
    } catch (_) {
      return false;
    }
  }

  /* 지금 이 화면이 DQA 앱 창 안인가.
     신호 둘 다 **앱이 심은 것**이고, 둘을 함께 보는 이유는 수명이 다르기 때문이다:
       1차 — 앱이 방금 연 창의 주소(`?client_port=&client_nonce=`). 첫 적재에만 있다.
       2차 — 그 좌표가 옮겨간 `sessionStorage`. 새로고침·앱 안 화면 이동에서 산다. */
  function inClientApp() {
    var query;
    try {
      query = new URLSearchParams(location.search);
    } catch (_) {
      return true;                       // URLSearchParams 부재 — 판정 불가
    }
    if (query.has(PORT_PARAM) && query.has(NONCE_PARAM)) return true;
    if (isLoginReturnForOauth(query)) return true;

    var raw;
    try {
      raw = sessionStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return true;                       // 저장소가 막힌 환경 — 판정 불가
    }
    if (raw) {
      try {
        var coords = JSON.parse(raw);
        if (coords && coords.port && coords.nonce) return true;
      } catch (_) { /* 깨진 값 = 앱이 심은 것이 아니다 — 아래 «쓸 수 있는가» 로 넘어간다 */ }
    }
    /* 신호가 없다. 그것이 «앱이 아니다» 인지 «신호가 살아남지 못하는 창» 인지 가른다. */
    return !storageIsUsable();
  }

  try {
    if (!GATED[location.pathname]) return;
    if (inClientApp()) return;
    /* `replace` 다 — `assign` 이면 [뒤로]가 이 화면으로 돌아와 왕복이 된다. */
    location.replace(GUIDE_PATH);
  } catch (_) {
    /* 게이트가 실패해도 화면은 뜬다. 위 fail-open 과 같은 방향. */
  }
})();
