/* 공유 화면이 «지금 DQA 앱 안인가» 를 아는 통로.
 *
 * ## 왜 이 파일이 따로 있나 (규약을 베끼지 않기 위해)
 *
 * 브리지 좌표(`?client_port=&client_nonce=` → `sessionStorage["dqa.bridge"]`)의 **정본은
 * `app/client-bridge.js`** 다. 공유 화면(`share.js`)은 그 모듈을 직접 쓸 수 없다 — 저쪽은
 * ES module 이고 이쪽은 classic script 라서다. 그렇다고 같은 규약을 `share.js` 에 한 벌 더
 * 적으면, 좌표 해석이 저장소에 **세 곳**(모듈·`ai-connect.js`·공유 화면)이 된다. 규약이
 * 갈리는 순간 「앱 안인데 앱 밖으로 보이는」 화면이 생기고, 그 화면은 사용자를 앱으로
 * 다시 보내는 무한 왕복을 만든다.
 *
 * 그래서 정본 모듈을 **그대로 import 해** 결과만 전역에 얹는다. 이 파일에는 판정 로직이
 * 없다 — 어댑터다.
 *
 * ⚠ 이 모듈이 `share.js` 보다 **먼저** 실행돼야 한다. `share.html` 은 이 파일을
 *   `type="module"`(암묵 defer)로, `share.js` 를 `defer` 로 싣는다 — 둘은 같은 큐에
 *   문서 순서대로 들어가므로 순서가 보장된다. `share.js` 에서 defer 를 떼면 그것이
 *   먼저 돌아 전역이 비어 있고, 앱 창 안에서도 「앱에서 열기」가 뜬다.
 */
import { clientBridge } from "./app/client-bridge.js?v=dev";

/** 앱 창 좌표(`{port, nonce}`) 또는 `null`. 평범한 브라우저 방문에서는 `null` 이다. */
window.__dqaClientBridge = clientBridge || null;
