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
