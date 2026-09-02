---
run_at: 2026-09-02T15:20:00+09:00
session: ai/claude-corp/feature-0043-caps-live-sync
scope: caps-live-sync 웹 자산 (app.js · app/connect-modal.js · routers/{oauth_as,system,ai_tools})
verdict: PENDING-POSTDEPLOY
---

# TASK-20260902T140200 — feature-0003 웹 자산 시각검증 기록

이 cycle 의 코드 거주가 feature-0043 이지만 웹 자산(`static/app.js` ·
`static/app/connect-modal.js` · `routers/*`)은 **feature-0003 소유**이므로 시각검증 기록도
여기 둔다(check #13 의 대상 판정 = 파일 소유 feature).

## Run — Environment: Windows-browser

- **상태: 미수행 (배포 후 수행) — 사유는 구조적이다.**

  변경의 핵심이 **ES module JS**(`app.js` 의 `onCapsChange` 소비처 · `connect-modal.js` 의
  `_paintCaps`/폴링 창)이고, 이 저장소에서 JS 는 **배포 전 라이브 QA 가 불가능**하다:
  컨테이너에 파일만 밀어 넣으면 빌드가 주입하는 cache-buster 스탬프(`?v=`)가 없어
  **모듈이 이중 인스턴스화**되고 브라우저 모듈 캐시가 구버전을 실행한다(서버 파일이 신버전
  이어도). 즉 배포 전에 얻는 «초록» 은 신 코드의 초록이 아니다.

  그래서 이 축은 **POST-DEPLOY 실측**으로 수행한다. 브리지 가용성은 이미 확인했다 —
  `python3 bin/win-browser.py doctor` → `{"ok": true, … "cdp_version": "Chrome/151.0.7922.170"}`
  (2026-09-02 15:18). 즉 「환경상 불가」가 아니라 **순서상 배포 이후**다.

- **배포 후 실측할 항목** (AC 대응):
  1. **AC-1** 러너 기동 후 **새로고침 없이** 모델·추론등급 선택기가 나타난다
     (능력 협상 종료 시점부터 ≤10초).
  2. **AC-2** 확인 창의 사유 문구가 「…확인하는 중입니다. 잠시 후에도 비어 있으면 그 AI 의
     로그인·네트워크를 확인해 주세요.」 — 종전 「최신 실행 파일로 다시 실행해 보세요」가
     아니다(구 빌드일 때만 그 문구).
  3. **AC-3** 연결·목록이 모두 성립한 정상 상태에서 `/api/ai/connect/status` 폴링이 **0**
     (Network 패널 실측).
  4. 픽셀-클래스 확인 — 선택기가 나타날 때 컴포저 레이아웃이 밀리지 않는지 확대 캡처.

- **정직 표기**: 위 4항목은 이 기록 시점에 **미검증**이다. 완료 선언은 이 항목들이 실측
  PASS 로 갱신된 뒤에만 한다(§16.6 「인정만으로 검증이 완료되지 않음」).

## Run — Environment: Windows-browser (확인 라운드 2회차 delta, 2026-09-02T16:55+09:00)

- **상태: 미수행 (배포 후 수행)** — 사유는 위와 **같다**(ES module JS 는 스탬프 없이 밀어
  넣으면 이중 인스턴스화되어 배포 전 초록이 신 코드의 초록이 아니다).

- **브리지 재확인 (환경상 불가가 아님의 증거)**: 이 라운드 시점에 브리지가 내려가 있었고
  (`doctor` → `ok:false`, 「동작 중인 CDP 브리지 없음」), 문서된 조치로 복구했다 —
  `python3 bin/win-browser.py launch --url https://localhost/admin` →
  `{"ok": true, "bridge_mode": "relay", "endpoint": "http://172.26.144.1:9223",
  "browser": "Chrome/151.0.7922.170", "navigated": {"status": 200,
  "title": "DQA — Database Query Assistant Admin"}}`. 이후 `doctor` → `ok:true`.
  즉 POST-DEPLOY 수행 경로가 **지금 살아 있음을 실측했다**.

- **이 라운드가 추가로 바꾼 웹 자산** (위 4항목 외 추가 확인 대상):
  1. `connect-modal.js` — 재무장 상한의 **진행 정의**를 「지문 변화(`fire`)」 하나로 좁혔다.
     초판(`fire || !pending`)은 진동 한 사이클마다 셈이 되돌아가 상한이 **도달 불가**였다.
     → POST-DEPLOY 확인: 러너를 **4회 이상** 재기동해도 매번 라이브 갱신이 뜨고
     (상한이 성공을 세지 않음), 러너 없이 확인 창이 진동할 때는 5분 안에 폴링이 멎는다.
  2. `routers/system.py` 문구는 이 라운드에서 **바뀌지 않았다** — 위 AC-2 가 그대로 유효한
     검증 대상이다(문서 표만 코드 verbatim 으로 맞췄다).

- **정직 표기**: 이 delta 항목도 **미검증**이다. 배포 직후 위 1항목을 포함해 실측하고 이
  fragment 를 PASS 로 갱신한다.

## Run — Environment: Windows-browser (3차 제보 delta, 2026-09-02T17:40+09:00)

- **상태: 미수행 (배포 후 수행)** — 사유 동일(ES module JS 는 스탬프 없이 배포 전 QA 불가).

- **이 라운드가 바꾼 웹 자산**: `connect-modal.js`(`watch` 개명 · `caps_pending ∪
  caps_settling` · 지문 지연 소비 · 협상 중 첫 관측 발화) · `app.js`
  (`_refreshModelCatalogSurface` 가 실패를 반환).

- **배포 후 실측할 항목** (위 AC-1~3 에 더해):
  5. **AC-4 플랫폼별 실시간 갱신** — 러너 기동 후 **첫 플랫폼**(claude, 실측 ~23초)이
     화면에 나타나고, 그 뒤 **두 번째 플랫폼**(codex, 실측 ~112초)이 **새로고침 없이**
     추가로 나타난다. ⭐ 이것이 3차 제보의 직접 판정이다.
  6. **AC-5 정착 후 폴링 0** — 마지막 목록 변화 후 150초(`CAPS_SETTLING_SEC`)가 지나면
     `/api/ai/connect/status` 요청이 0으로 돌아간다(Network 패널 실측).
     ⚠ AC-3 의 표현을 이 값으로 **정정**한다: 종전 「정상 상태에서 0」은 이제
     「**마지막 신고 후 150초 경과** 상태에서 0」이다.
  7. **AC-6 카탈로그 실패 재시도** — 재조회를 인위적으로 실패시켰을 때(오프라인 토글) 목록이
     빈 채 고정되지 않고, 복구 후 **같은 지문에서 다시 채워진다**(P1-4 의 라이브 확인).
  8. **AC-7 새로고침한 탭** — 협상 중(첫 플랫폼만 도착한 시점)에 F5 를 눌러도 남은 플랫폼이
     이어서 나타난다(P2-5·`caps_settling` 의 라이브 확인).

- **정직 표기**: AC-4~7 은 **미검증**이다. 단위·node 실행 검증은 통과했으나 그것은 판정
  로직이고, 「실제 두 CLI 가 다른 시각에 끝날 때 화면이 두 번 갱신되는가」는 라이브에서만
  관측된다.
