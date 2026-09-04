---
run_at: 2026-09-04T18:00:00+09:00
session: ai/claude/feature-0046-tray-background
scope: static/app/client-bridge.js · connect-modal.js — `_status` 처방을 main 의 주입 방식으로 수렴
verdict: PASS (Windows-browser 미수행 — 사유 명시)
---

# Run — 같은 결함, 두 처방 → 하나로

## 무엇이 있었나

같은 `ReferenceError: _status is not defined` 를 **두 세션이 독립으로** 찾았다.

| | 처방 |
|---|---|
| 본 cycle(먼저) | `client-bridge.js` 안에 `_status` **지역 정의** |
| 병렬 PR #1572 | `initClientPanel(setStatus)` — **호출부 주입** |

**주입을 채택했다.** 중복이 없고, 순환도 없고, 「이 모듈은 모달의 내부 헬퍼를 모른다」는 것이
시그니처에 드러난다. 「누가 먼저인가」가 아니라 구조가 말하는 것으로 골랐다.

상주 안내(`_paintResidency` + `bridgeCall("status")`)는 그 위에 다시 얹었다. 이것은
**주입받지 않는다** — 이 패널에만 있는 요소이고 다른 호출부가 달리 그릴 이유가 없다.

## 내 테스트가 그들의 옳은 수정을 거짓 양성으로 잡았다

`_free_identifiers_called` 가 「`function` 선언이 있는가」로만 «정의» 를 판정했다. 주입으로
바뀌자 `_status` 는 `const` 바인딩이 되었고, 그 판정은 **멀쩡한 코드를 결함이라고** 했다.
판정해야 하는 것은 선언 **형태**가 아니라 **바인딩 유무**다(`function`/`const`/`let`/`var`/
매개변수/`import`). 좁게 쓴 판정은 자기 시점의 코드 모양을 계약으로 굳힌다.

## 폐기한 테스트를 «지우지 않고 대체» 했다

`test_status_writers_in_both_modules_target_the_same_element` 는 내 중복 정의를 전제하므로
성립하지 않는다. 그러나 그것이 지키려던 성질(**상태 표시가 허공에 쓰이지 않는다**)은 주입
계약에서도 살아 있고, 한 층 위로 옮겨 갔다 — **주입하는 이름이 그 모듈에 실재하는가**.
없으면 예외가 호출부로 옮겨 갈 뿐이다. 계약이 바뀌었다고 축을 비우면 게이트에 구멍이 남는다.

## 검증

- 회귀 **275 passed**(그들의 `test_client_bridge_runtime.py` 7건 포함).
- 행위 하네스를 주입 계약으로 갱신 — 콜백을 넣어 부르고 **그 콜백으로 실제로 말하는지** +
  콜백 없이도 죽지 않는지. 결과 PASS.
- **음성 대조군 4종 전건 적발**: 자유변수 복귀(원 결함) · 주입만 받고 무시 · 기본값 제거 ·
  상주값 무시.
- **뮤테이션 5/5 KILL · NOOP 0**: 주입 바인딩 제거 · 없는 이름 주입 · 무인자 회귀 ·
  상주 자리 제거 · 상주값 무시.

## ⛔ Environment: Windows-browser — **미수행**, 사유

브리지 `client_port/nonce` + 유효 연결 토큰이 필요하고, 라이브 반영은 병렬 세션이 공유하는
web 컨테이너를 건드려야 해 §13.2.9 가 금지한다.

⚠ **CI-GAP**: 그들의 런타임 테스트는 node 부재 시 `pytest.skip` 한다 — CI 이미지에 node 가
없으므로 **거기서는 구동 축이 통째로 빈다**. 내 소스 층 단정이 부분적으로 메우지만 대체는
아니다. (내 하네스도 같은 이유로 CI 밖이며, 그 gap 은
`CI-GAP: verify_client_panel_dom.mjs` 로 별도 기록돼 있고 테스트가 기록을 강제한다.)
