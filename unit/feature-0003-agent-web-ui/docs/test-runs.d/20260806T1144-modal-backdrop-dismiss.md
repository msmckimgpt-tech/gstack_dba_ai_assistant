### 20260806T1144-modal-backdrop-dismiss 사이드바 항목(대화/폴더) 모달 배경 dismiss (Minor §12.3, 2026-08-06, feature-0003 web/UI) — **Environment: Windows-browser — PASS**

- **무엇**: 좌측 사이드바 항목(대화·폴더)에서 열리는 backdrop 모달 6종의 "바깥 어두운 배경을 눌러
  닫기"를, 누름(`pointerdown`)과 뗌(`pointerup`)이 **둘 다 배경 위**일 때로 한정한다. 판정은 그
  2단이 하고 실행은 이어지는 `click` 이 트리거한다. 터치·펜의 implicit pointer capture 는 배경에서
  시작한 제스처에 한해 해제한다.
- **기대(실측 항목)**
  1. 배경에서 누르고 배경에서 떼면 닫힌다.
  2. 패널 안에서 누르고 배경에서 떼면 **안 닫힌다** (폴더 지침 textarea 드래그 선택 중 손이 밖으로
     나가도 작성분이 살아 있다) — 사용자가 보고한 "up 됐을 때 종료" 현상.
  3. 배경에서 누르고 패널 안에서 떼면 **안 닫힌다** — "down 됐을 때 종료" 현상.
  4. 닫힌 직후 그 좌표 아래 레이어가 눌리지 않는다(ghost click 부재).
  5. 배경 우클릭으로는 닫히지 않는다.
  6. 터치에서도 2·3이 성립한다.

#### Run 1 — **Environment: Windows-browser** (2026-08-06, 실 Windows Chrome 150.0.7871.128 via `bin/win-browser.py` relay, CDP trusted input) — **PASS 10/10**

실행: `python3 unit/feature-0003-agent-web-ui/tests/pb0008_modal_backdrop_dismiss.py`

이 Run 은 **합성 JS 이벤트가 아니라** CDP `Input.dispatchMouseEvent` / `Input.dispatchTouchEvent`
로 브라우저 입력 파이프라인에 trusted 입력을 넣는다 — 그래야 원 결함의 기전인 **`click` target
공통-조상 승격**과 터치의 **implicit pointer capture** 가 *모델이 아니라 실제로* 적용된다.
페이지는 배포본이 아니라, **`static/app.js` 에서 `bindBackdropDismiss` 본문을 그대로 떼어낸**
최소 페이지다(같은 `.share-mgr-backdrop` CSS · 같은 backdrop>panel 구조 · 지침 textarea 포함).

| # | 시나리오 | 관측 | 판정 |
|---|---|---|---|
| 1 | [마우스] 배경 누름+뗌 | `dismissed=1 open=false` | PASS (AC1) |
| 2 | [마우스] dismiss 직후 아래 레이어 클릭 여부 | `ghost=0` | PASS (AC7) |
| 3 | [마우스] 패널에서 누르고 배경에서 뗌 | `dismissed=0 open=true` | PASS (AC2) |
| 4 | [마우스] 배경에서 누르고 패널에서 뗌 | `dismissed=0 open=true` | PASS (AC3) |
| 5 | [마우스] 패널 안에서 누르고 뗌 | `dismissed=0 open=true` | PASS |
| 6 | [마우스] 지침 textarea 드래그 선택 중 배경에서 놓기 | `dismissed=0 open=true` | PASS (원 결함 시나리오) |
| 7 | [마우스] 배경 우클릭 | `dismissed=0 open=true` | PASS |
| 8 | [터치] 배경 탭 | `dismissed=1 open=false` | PASS |
| 9 | [터치] 배경에서 누르고 패널에서 뗌 | `dismissed=0 open=true` | PASS (AC6) |
| 10 | [터치] 패널에서 누르고 배경에서 뗌 | `dismissed=0 open=true` | PASS (AC2) |

증적: `evidence/modal-backdrop-dismiss-harness-live.png` (실 Windows Chrome 렌더 — 모달 + 좌하단
상태 표시 `dismissed=0 ghost=0 open=1`).

#### Run 2 — **역검증 (negative control, 같은 실 Windows 브라우저)** — 의도대로 **FAIL 3/10**

실행: `python3 unit/feature-0003-agent-web-ui/tests/pb0008_modal_backdrop_dismiss.py --negative`
(헬퍼만 **수정 전 구현**(`click` + `e.target === backdrop`)으로 갈아끼움 — 나머지 동일)

| # | 시나리오 | 관측 | 의미 |
|---|---|---|---|
| 3 | [마우스] 패널에서 누르고 배경에서 뗌 | `dismissed=1 open=false` | **사용자 보고 현상 재현** — "up 됐을 때 종료" |
| 4 | [마우스] 배경에서 누르고 패널에서 뗌 | `dismissed=1 open=false` | **사용자 보고 현상 재현** — "down 됐을 때 종료" |
| 6 | [마우스] 지침 textarea 드래그 선택 중 배경에서 놓기 | `dismissed=1 open=false` | **작성 중 지침 소실 재현** |

즉 Run 1 의 PASS 는 vacuous 하지 않다 — 같은 하네스가 수정 전 코드에서는 결함을 정확히
검출하며, 그 검출 내용이 사용자가 보고한 현상과 일치한다.
(터치 9·10 은 negative 에서도 PASS 인데, 터치 드래그는 Chrome 이 slop 초과로 `click` 을 아예
발행하지 않아 옛 구현이 우연히 통과하기 때문이다 — 터치 캡처 축의 판별력은 `--negative` 가 아니라
`verify_modal_backdrop_dismiss.mjs` 의 "캡처 해제 1줄 삭제" 변형 역검증이 담당한다.)

#### 부수 검증 (같은 cycle)

- `node unit/feature-0003-agent-web-ui/tests/verify_modal_backdrop_dismiss.mjs` — **48 passed / 0 failed**
  (동작 18 + 배선 30). 역검증 **5종** 전부 의도한 단언만 red: 옛 `click` 단독(11) · 캡처 해제
  삭제(1) · 실행을 `pointerup` 으로 되돌림(3) · `pointerup` 이 `downOk` 미소비 = 장전 잔류(1) ·
  `click` 에서 `isTrusted` 미검사(1). **장전 잔류 축은 실 브라우저로는 안정 재현이 어려워**
  (브라우저가 click 을 안 쏘는 제스처를 CDP 로 결정론적으로 만들기 어렵다) mjs 역검증이 담당한다.
- ESM `node --check` — `app.js` · `app/sidebar.js` PASS.
- `verify_*.mjs` 전수 — red 21건, **main baseline 과 동일 집합**(본 변경 기인 신규 red 0).
- `make test` (pytest) — **3782 passed · 3 skipped · 0 failed**(exit 0), ruff clean.

#### 잔여 (배포 후)

본 Run 은 **계약** 을 실 브라우저에서 실측했다. 배포 후 라이브 `https://localhost/` 작업 화면에서
실제 6개 모달(대화 설정 · 공유 · 공유 링크 설정 · 참여 허용 확인 · 폴더 설정 · 폴더로 이동)을
직접 열어 같은 제스처를 재확인하고 본 fragment 에 Run 3 을 append 한다 — 정적 자산이 web 이미지에
baked 되는 구조라 미머지 상태에서는 라이브 무접촉으로 그 6개 화면을 띄울 수 없다.

- Pass/Fail: **PASS** (실 Windows 브라우저 10항목 + 역검증 3항목 재현). Runner: AI.
