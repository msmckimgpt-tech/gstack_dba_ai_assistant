---
run_at: 2026-09-04T17:10:00+09:00
session: ai/claude/feature-0046-tray-background
scope: 주 표면(앱 창 연결 패널) — 상주 안내 이관 + 실행 결함 적발·해소
verdict: PASS (CI 미배선 gap 1건 명시)
---

# Run — 주 표면 패널: 상주 안내가 «닿는가» 와, 그 패널이 애초에 도는가

## 0. 이 run 이 시작된 이유

앞선 재구성에서 상주 안내를 `ai-connect.html`/`ai-connect.js` 에 넣었다. 그런데 사용자가
실제로 보는 화면은 **앱 창이 여는 서비스 루트**(`index.html`)이고, 그 화면의 연결 패널은
`app/client-bridge.js` 의 `initClientPanel()` 이 그린다. 즉 **저장은 됐는데 읽히지 않는
자리**에 넣었다 — 「내 작업을 주 경로와 정합하게」라는 요구가 한 층 아래에서 그대로 반복됐다.

## 1. 실행이 적발한 결함 — 소스 검사로는 안 보였다

주 표면을 실제로 구동하자 첫 호출에서 던졌다.

```
ReferenceError: _status is not defined
  → initClientPanel() 이 던지고, 예외가 호출부 openConnectModal() 까지 전파
```

`client-bridge.js` 가 `_status(...)` 를 8곳에서 부르는데, 그 함수의 정의는
`connect-modal.js` 의 **export 되지 않은 지역 함수**이고 import 도 없다. ESM 모듈 스코프는
파일마다 닫혀 있으므로 이것은 자유변수다.

- **소스 검사로는 안 잡힌다.** 이름이 «있어» 보인다(정의가 저장소 안에 존재한다).
- **증상이 상위 결함과 같다.** 직전 cycle 이 고친 「패널이 끝내 안 켜졌다」와 화면상 구분되지
  않는다. 그쪽 처방(플래그를 결과로)은 필요했지만 **충분하지 않았다**.

### 처방

`client-bridge.js` 안에 `_status` 를 정의한다. import 로 풀지 않는다 —
`connect-modal.js` 가 이 파일을 import 하므로 반대 방향을 더하면 순환이고, 이 파일이
**아무것도 import 하지 않는다**는 성질은 파일 상단이 설명하는 분리 이유의 일부다.
두 정의가 같은 요소를 쓴다는 것이 계약이며, `test_status_writers_in_both_modules_target_the_same_element`
가 그것을 잠근다.

## 2. 상주 안내를 주 표면으로

- `index.html` `#connectClientPanel` 에 `#connectClientResidency` 를 **비운 채** 둔다.
- `initClientPanel()` 이 `bridgeCall("status")` 로 물어 그 값으로만 칠한다.
- `status` 는 `discover` **앞에** 묻는다. `discover` 는 실제 응답을 확인하느라 수십 초
  걸리는데, 「이 창을 닫아도 되는가」는 그 전에 알아야 하는 안내다.

## 3. 행위 하네스 — `verify_client_panel_dom.mjs`

`ai-connect.js` 쪽 하네스와 달리 **함수를 떼어내지 않는다.** 이 모듈은 ESM export 라
`data:` URL 로 **바이트 그대로** 통째 import 해 실행한다 — 「추출이 깨져서 vacuous pass」
라는 실패 모드 자체가 없다.

실행: `DQA_JSDOM=<jsdom>/lib/api.js node verify_client_panel_dom.mjs <repo>`

```
PASS: 주 표면 패널 — 예외 없음 · status 선행 · 상주/비상주 문구 갈림 · 패널 노출
```

### 음성 대조군 — 하네스가 **무엇을 잡는지** 증명

| # | 주입한 결함 | 결과 |
|---|---|---|
| N1 | `_status` 정의 제거(원 결함 재현) | exit 1 — `ReferenceError: _status is not defined` |
| N2 | `#connectClientResidency` 를 index.html 에서 제거 | exit 1 — 「index.html 에 #… 가 없다」 |
| N3 | `status` 를 묻지 않음 | exit 1 — 「상주 여부를 알 길이 없다」 + 문구 빈 채 |
| N4 | 상주 여부와 무관하게 같은 문구 | exit 1 — 「비상주인데 «닫아도 유지»」 |

⚠ **N2 는 처음에 크래시로 실패했다** — `null.textContent` 스택 추적이 나왔고, 종료 코드만
맞을 뿐 원인을 말해 주지 않았다. 요소 검사 뒤에 **끊도록** 고쳤다. 진단이 안 나오는 실패는
다음 사람에게 아무것도 알려 주지 않는다.

## 4. 단위 — 6건 추가

`test_bridge_module_has_no_free_identifiers_for_its_helpers` 는 이번 결함의 **형태**를
잠근다(부르면서 정의도 import 도 하지 않는 헬퍼). 나머지는 상주 자리·순서·두 `_status`
의 대상 일치.

⚠ `test_primary_panel_declares_residency_element` 는 처음에 「마크업에 «닫아도» 가
없는가」로 썼다가 **자기 옆 주석에 걸렸다.** 설명을 지워야 통과하는 테스트가 됐을 것이다 —
요소의 **내용**을 보도록 고쳤다.

## 5. 뮤테이션 — 7/7 KILL · NOOP 0

| # | 뮤턴트 | 결과 |
|---|---|---|
| M30 | `_status` 정의 제거(원 결함 재현) | KILL (2 FAILED) |
| M31 | `status` 를 `discover` 뒤로 | KILL |
| M32 | 주 표면에서 상주 자리 제거 | KILL |
| M33 | 문구를 마크업에 박음 | KILL |
| M34 | 두 `_status` 가 다른 요소를 가리킴 | KILL (보강 후) |
| M35 | `client-bridge` 쪽 `_status` 가 다른 요소를 가리킴 | KILL |
| M36 | `_paintResidency` 가 인자를 무시 | KILL (보강 후) |

### 이 run 이 스스로에게서 찾은 것 3건

1. **NOOP 검사가 먼저 고장 났다.** 첫 실행은 M30–M34 가 전부 NOOP 로 나왔다. 뮤턴트가
   적용되지 않은 것이 아니라 **변경 감지**가 고장이었다 — `diff -q` 출력이 한글 로케일이라
   `grep differ` 가 0을 셌다. NOOP 판정이 없었다면 「5건 전부 적용됐고 전부 KILL」로 읽었을
   것이다. `cmp -s` 로 바꿨다.
2. **M34 가 살아남았다 — 부분 문자열 구멍.** 단정이 `'"connectModalStatus"' in modal` 이라
   `connectModalStatusX` 도 통과했다. `_status` 가 **실제로 집는 id 를 뽑아** 등호로 비교하도록
   고쳤다.
3. **M36 이 pytest 층을 통과했다.** 「인자를 무시하고 항상 «유지됩니다»」는 행위 하네스가
   잡지만 그 하네스는 CI 에 없다. 행위 층에만 두면 **CI 에서는 통과한다** — 소스 층에도
   잠갔다(`test_residency_painter_actually_reads_its_argument`).

## 6. 미수행 · gap

- **CI-GAP: verify_client_panel_dom.mjs** — `make test` 의 agent 이미지에 node 가 없어
  이 행위 하네스는 CI 에 배선되지 않는다. `test_panel_behaviour_harness_runs_or_ci_gap_is_documented`
  가 「돌리거나, 못 돌리면 이 기록이 있거나」를 강제해 **조용한 skip 이 되지 않게** 한다.
  (같은 형태를 feature-0003 의 `test_side_panel_exclusive.py` S6 이 이미 쓴다.)
- ⛔ **PB-0008 실 Windows 시각검증 미수행** — 이 패널은 브리지의 `client_port/nonce` 로만
  나타나고, 라이브 반영은 병렬 세션이 공유하는 web 컨테이너를 건드려야 해 §13.2.9 가 막는다.
  jsdom 은 **렌더 결과**를 보지만 실제 브라우저·실제 브리지 왕복은 아니다.
