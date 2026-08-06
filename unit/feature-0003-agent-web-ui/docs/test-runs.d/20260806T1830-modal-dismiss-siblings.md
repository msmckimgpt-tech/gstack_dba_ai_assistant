### 20260806T1830-modal-dismiss-siblings 배경 dismiss 전 표면 통일 (Minor §12.3, 2026-08-06, feature-0003 web/UI) — **Environment: Windows-browser — PASS**

- **무엇**: `bindBackdropDismiss` 를 공용 모듈 `static/modal-dismiss.js` 로 옮기고, 앱의 **모든**
  배경 dismiss 표면(11곳)을 그 정본에 배선한다. 계약은 선행 cycle 그대로.
- **기대**: (1) 선행 6종 무회귀 (2) 신규 전환 5종도 같은 계약 (3) 전 트리에 옛 패턴 잔존 0
  (4) 재렌더 모달의 리스너 누수 0 (5) 파괴적 purge 모달 중복 인스턴스 가드.

#### Run 1 — **Environment: Windows-browser** (2026-08-06, 실 Windows Chrome 150.0.7871.128 via `bin/win-browser.py` relay, CDP trusted input) — **PASS 10/10**

실행: `python3 unit/feature-0003-agent-web-ui/tests/pb0008_modal_backdrop_dismiss.py`
(정본 경로를 `static/app.js` → `static/modal-dismiss.js` 로 갱신)

마우스 7항목 + 터치 3항목 전건 PASS — AC1(배경 누름+뗌 → 닫힘) · AC2(패널→배경 드래그 →
안 닫힘) · AC3(배경→패널 드래그 → 안 닫힘) · AC7(ghost click 부재) · 우클릭 무시 ·
지침 textarea 드래그 이탈 시 모달 유지 · 터치 implicit pointer capture 해제.
`--negative`(수정 전 구현)에서 **사용자 보고 현상 3건 재현**(FAIL 3/10) — 하네스 유효성 확인.

#### Run 2 — 정적·수명 하네스 (`verify_modal_backdrop_dismiss.mjs`) — **76 pass / 0 fail**

세 축: (A) 동작 18 — 실제 primitive 본문을 DOM 이벤트 shim 위에서 실행 (B) 배선 52 — 11 표면 +
전-트리 census + detector 자기검증 (C) 리스너 수명 6 — 재렌더 모달의 document keydown 리스너 수를
시뮬레이션으로 **실측**(정규식 단언 금지).

#### Run 3 — **뮤테이션 역검증 6종** — 전부 의도한 단언만 red

| 뮤테이션 | 결과 |
|---|---|
| `downOk = e.button === 0` → `true` (button 가드 제거) | 1 fail ✔ (**교정 전에는 생존** — vacuous 였다) |
| `if (e.isPrimary === false) return;` 삭제 | 2 fail ✔ (**교정 전에는 생존**) |
| `app/profile.js` 재렌더 누수 복원(`prev.remove()`) | 3 fail ✔ (수명 실측이 검출) |
| `admin/usage.js` `close()` 가 ESC 미해제 | 3 fail ✔ |
| **census 범위 밖 신규 파일**(`admin/newpane.js`)에 옛 패턴 모달 신설 | 1 fail ✔ (**교정 전에는 무검출**) |
| `admin/audit.js` 를 부정형 `if (e.target !== overlay) return;` 로 되돌림 | 2 fail ✔ |

마지막 두 행이 이 cycle 의 핵심이다 — 잠금이 **미래의 새 파일**과 **표기 변형**에도 작동함을
보인다(§18.8 design 패널이 교정 전 상태에서 무검출을 실증했다).

#### 부수 검증

- ESM `node --check` — `modal-dismiss.js`·`app.js`·`app/profile.js`·`admin/usage.js`·
  `admin/audit.js`·`graph/graph-core.js` 전건 PASS.
- `verify_*.mjs` 전수 — red 21건, **main baseline 과 동일 집합**(본 변경 기인 신규 red 0).
- `make test` (pytest) — **3784 passed · 3 skipped · 0 failed**(exit 0), ruff clean.

#### 잔여 (배포 후)

배포 후 라이브에서 신규 전환 5종(프로필 사용 내역 · 관리 콘솔 사용 기록 · 감사 purge ·
그래프 도움말 · 대화 검색)을 실제 UI 경로로 열어 3제스처를 재확인하고 Run 4 를 append 한다.

- Pass/Fail: **PASS**. Runner: AI.

#### Run 4 — **POST-DEPLOY 라이브 실측** (Environment: Windows-browser, 2026-08-06, 실 Windows Chrome via `bin/win-browser.py` relay, 배포본 `2ab2b27e`, 로그인 세션 `bootstrap_admin`) — **PASS 16/16**

Run 1 은 **계약**을, 본 Run 은 **배포된 실제 화면**을 실측한다. 진입은 사용자와 동일한 UI 경로
(탭·버튼 클릭, 차트 요소는 실제 좌표 마우스 클릭 — SVG 는 `.click()` 이 없어 CDP trusted 좌표
입력을 썼다). 이번 cycle 이 **새로 전환한 5종 전부** 실측했다.

| # | 표면 | 화면 | 패널→배경 | 배경→패널 | 배경 클릭 |
|---|---|---|---|---|---|
| 1 | 대화 검색 모달 | 작업 화면 | 안 닫힘 (AC2) | 안 닫힘 (AC3) | 닫힘 (AC1) |
| 2 | 그래프 뷰 도움말 | 관리 콘솔 | 안 닫힘 | 안 닫힘 | 닫힘 |
| 3 | 감사 › purge | 관리 콘솔 | 안 닫힘 | 안 닫힘 | 닫힘 |
| 4 | 사용 기록 | 관리 콘솔 | 안 닫힘 | 안 닫힘 | 닫힘 |
| 5 | 프로필 › 사용 내역 | 작업 화면 | 안 닫힘 | 안 닫힘 | 닫힘 |

**+ 중복 인스턴스 가드 실측** — 감사 purge 진입 버튼을 **연속 2회** 눌러도 오버레이가 **1개**임을
확인(§18.8 ux 패널 P2-1 로 추가한 가드가 라이브에서 작동). 가드가 없으면 겹친 오버레이의 중복
id 때문에 위쪽 모달 버튼에 핸들러가 하나도 안 붙어 파괴적 플로우가 조작 불능이 된다.

- **라이브 데이터 변경 0**: purge 모달에서 **미리보기·삭제 실행 버튼을 누르지 않았고**, 사용 기록·
  사용 내역 모달은 읽기 전용 조회다. 저장·전송·이동·보관 어느 것도 실행하지 않았다.
- 배포 반영 확인: 서빙 `modal-dismiss.js?v=cf34bab66daa` 200(7,002 B)에 `bindBackdropDismiss`
  존재, `app/profile.js`·`admin/usage.js`·`admin/audit.js`·`graph/graph-core.js` 4파일 전부 서빙본에
  primitive 호출 존재. web-a/web-b/ask-worker/insight-worker 4서비스 전부 `2ab2b27e` 이미지.
- 증적: `evidence/modal-dismiss-siblings-live.png`.

**선행 6종은 Run 3(PR #1165 fragment Run 3)에서 이미 라이브 실측**했고 본 cycle 은 계약을 바꾸지
않았다(primitive 본문 무수정 — 모듈 위치만 이동). 전수 mjs·PB-0008·`make test` 로 무회귀 확인.

- Pass/Fail: **PASS** (신규 전환 5종 15항목 + 중복 인스턴스 가드 1항목). Runner: AI.
