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
