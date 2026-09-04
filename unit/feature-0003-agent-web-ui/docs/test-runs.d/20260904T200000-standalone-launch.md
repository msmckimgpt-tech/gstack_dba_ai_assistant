---
run_at: 2026-09-04T20:00:00+09:00
session: standalone-launch (ai/claude/feature-0046-standalone-launch)
scope: 인자 없는 실행이 앱 창을 연다 · 연결값을 창의 세션이 발급 · 두 번째 실행은 창을 다시 연다
verdict: PASS (정적·단위) / 라이브 시각검증은 배포+설치본 재빌드 후
---

### Run (2026-09-04) — standalone-launch: 단위·실행 검증 — **Environment: host pytest + node**

- `unit/feature-0046-native-client/tests` **338 passed** (신규 `test_standalone_launch.py` 37 ·
  `test_bridge_connect_credentials.py` 13 · JS 실행 하네스 13).
- JS 는 **가짜 DOM 위에서 모듈을 실제 import 해 클릭 핸들러를 호출**한다. 종전 하네스는
  `addEventListener` 를 삼켜서 클릭 경로가 한 줄도 실행되지 않았다 — 이번에 그 구멍을 메웠고,
  `test_connect_click_is_actually_wired` 가 그 전제를 잠근다.
- 뮤테이션 **30/30 KILL**. 사각지대 탐침 4건 중 **2건이 처음 SURVIVED**(접두 비교로 스킴 판정 ·
  빈 값 기록)했고 그 둘을 잡는 단정을 더해 닫았다. 「전건 KILL」은 표본이 내 테스트를 닮았다는
  뜻일 수 있어 일부러 어긋나는 뮤턴트를 던진 결과다.
- 컨테이너 스위트(`make test`)에서 종전 **2 failed**(`test_name_ssot.py` — 컨테이너에 git 없음)를
  같은 cycle 에서 해소. 그 두 게이트는 **CI 에서 한 번도 돈 적이 없었다.**

### Run (2026-09-04) — 연결 패널·안내 문구 시각검증 — **Environment: Windows-browser (배포 + 설치본 재빌드 후로 이연)**

- 대상 자산: `static/app/client-bridge.js`(연결 직전 토큰 발급 → 브리지 전달),
  `static/index.html`·`static/ai-connect.html`(「시작 메뉴 아이콘만 눌러도」 한 줄).
- **미수행 사유(§15.4.1)**: ① 정적 자산은 이미지에 **baked** 되어 web 재배포 후에만 라이브에
  반영된다(content-hash 스탬프). ② 이번 변경의 본체는 **연결 프로그램 안에서만** 나타나는
  경로다 — 패널은 `?client_port=&client_nonce=` 가 있을 때만 켜지고, 그 좌표는 **이번 cycle 에서
  만든 설치본**이 준다. 즉 현재 설치본(구판)으로는 이 경로를 구동할 수 없다. 배포 + 설치본
  재빌드 전 headless 검증으로 대체 불가.
- **배포 후 라이브 검증 계획(PB-0008)**: web 재배포 → `--service-base https://112.185.196.20` 로
  설치본 재빌드 → 재설치 → **시작 메뉴 아이콘만** 실행(딥링크 없음) → 앱 창이 서비스 루트로
  뜨는지 → 그 창에서 [연결 준비] → 패널이 AI 목록을 그리는지 → [이 서비스에 연결] 이 토큰을
  받아 실제로 연결되는지(`ai:ok`) → 창을 닫고 아이콘을 다시 눌러 창이 돌아오는지.
- 결과: 정적·단위 PASS · **라이브 시각검증 DEFERRED**(배포+재빌드 후, 위 계획).
