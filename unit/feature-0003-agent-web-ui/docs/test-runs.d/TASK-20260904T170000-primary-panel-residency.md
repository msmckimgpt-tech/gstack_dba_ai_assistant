---
run_at: 2026-09-04T17:10:00+09:00
session: ai/claude/feature-0046-tray-background
scope: static/index.html · static/app/client-bridge.js — 주 표면 연결 패널(상주 안내 + 실행 결함)
verdict: PASS (Windows-browser 미수행 — 사유 명시)
---

# Run — 앱 창이 여는 화면의 연결 패널

## 왜 이 Run 이 생겼나

같은 cycle 의 앞선 Run(`TASK-20260904T150000-tray-parity-panel-copy`)은 상주 안내를
`ai-connect.{html,js}` 에 넣었다. 그런데 **앱 창이 여는 것은 서비스 루트**(`index.html`)이고,
그 화면의 연결 패널은 `app/client-bridge.js` 의 `initClientPanel()` 이 그린다. 저 페이지는
별도 표면이라 앱 창 사용자는 그 안내를 **보지 못했다**.

## 변경

- `index.html` `#connectClientPanel` 에 `#connectClientResidency` 를 **비운 채** 추가.
- `app/client-bridge.js` — `_paintResidency()` 신설, `bridgeCall("status")` 의 `resident`
  로만 채운다. `discover`(수십 초) **앞에** 묻는다.
- `app/client-bridge.js` — `_status()` **지역 정의 추가**(아래 결함 해소).

## 이 Run 이 적발한 결함 — 패널이 애초에 돌지 않았다

모듈을 실제로 구동하자 첫 호출에서 던졌다.

```
ReferenceError: _status is not defined
  → initClientPanel() 이 던지고, 예외가 openConnectModal() 까지 전파 → 연결 창이 안 열린다
```

`client-bridge.js` 가 `_status` 를 8곳에서 부르는데 정의는 `connect-modal.js` 의
**export 되지 않은 지역 함수**이고 import 도 없다. ESM 모듈 스코프는 파일마다 닫혀 있으므로
자유변수다. **소스 검사로는 보이지 않는다** — 이름이 «있어» 보인다.

⚠ 증상이 `CHG-20260904T123000`(패널 초기화 플래그)과 **화면상 같다**. 그 처방은 필요했지만
충분하지 않았다 — 같은 증상에 원인이 둘이었다.

### 처방

`client-bridge.js` 안에 정의한다. import 로 풀면 `connect-modal.js → client-bridge.js` 의
반대 방향이 생겨 **순환**이고, 이 파일의 «의존 0» 성질(파일 상단이 설명하는 분리 이유)이
깨진다. 두 정의가 **같은 요소**(`#connectModalStatus`)를 쓴다는 것이 계약이며 테스트가 잠근다.

## 검증

- **행위 하네스** `unit/feature-0046-native-client/tests/verify_client_panel_dom.mjs` (jsdom):
  모듈을 `data:` URL 로 **바이트 그대로 통째 실행**한다 — 함수를 떼어내지 않으므로
  「추출이 깨져서 vacuous pass」가 성립하지 않는다.
  결과: `PASS — 예외 없음 · status 선행 · 상주/비상주 문구 갈림 · 패널 노출`.
- **음성 대조군 4종** 전부 exit 1 로 적발: `_status` 제거 · 상주 자리 제거 · `status` 미호출 ·
  값 무시. (N2 는 처음에 크래시로 실패해 원인을 말하지 않아, 요소 검사 뒤 **끊도록** 고쳤다.)
- **뮤테이션 7/7 KILL · NOOP 0** — 상세와 이 run 이 스스로에게서 찾은 3건은
  `unit/feature-0046-native-client/docs/test-runs.d/TASK-20260904T170000-primary-panel.md`.
- pytest 6건이 CI 에서 함께 돈다(자유변수 금지 · 두 `_status` 대상 일치 · 상주 자리 ·
  순서 · 인자 사용 · 하네스 실행/gap 기록).

## ⛔ Environment: Windows-browser — **미수행**, 사유

이 패널은 `?client_port=&client_nonce=` 가 붙었을 때만 나타나고, 그 값은 **Windows 에서
도는 네이티브 클라이언트의 브리지**가 만든다. 이 세션에는 유효 연결 토큰이 없고, 바뀐
`static/` 을 라이브에 반영하려면 **병렬 세션이 공유하는 web 컨테이너**를 건드려야 하므로
§13.2.9(배포 단계 격리)가 금지한다.

⚠ jsdom 은 **렌더 결과**를 본다. 실제 브라우저 렌더·실제 브리지 왕복은 아니며
**PB-0008 을 대체하지 않는다**. 라이브 왕복이 가능한 다음 cycle 에서 수행한다.
