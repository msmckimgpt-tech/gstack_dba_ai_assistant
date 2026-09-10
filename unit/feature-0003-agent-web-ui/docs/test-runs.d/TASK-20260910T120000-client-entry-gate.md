---
run_at: 2026-09-10T13:40:00+09:00
session: ai/claude/feature-0003-client-entry-gate
scope: client-entry-gate (일반 브라우저 → 설치 안내) · install 안내 화면
verdict: PASS (자동·실브라우저) / NOT-RUN (실제 DQA 클라이언트)
---

# TASK-20260910T120000-client-entry-gate — 검증 기록

## Run 1 — 행위 하네스 (jsdom)

```text
Environment: Node
Result: PASS
Build: worktree ai/claude/feature-0003-client-entry-gate (배포 전)
Scenario: 배포되는 `client-gate.js`·`install.js` 원문을 jsdom 에서 구동 —
  게이트 대상 × 신호 2차원 표 · 비대상 경로 · fail-open · 안내 화면 상태 4종 ·
  복사 인터랙션 · 뮤턴트 4종 · codex 지적 5건 회귀 가드
Evidence: `node unit/feature-0003-agent-web-ui/tests/verify_client_entry_gate.mjs`
  → 총 67건 PASS 67 / FAIL 0
미검증: 실제 내비게이션·저장소 수명은 jsdom 이 모형이다 (아래 Run 2 가 그 축을 잰다)
```

## Run 2 — 실 Windows Chrome (보조 호환 검증)

```text
Environment: Windows-browser
Result: PASS
Build: worktree 소스 원본을 고정 서버로 서빙 (`tests/pb0008_client_entry_gate.py`),
  Chrome/152.0.7977.83 · 전용 프로파일 `win-browser-cdp` (자기 생성 표면 한정, §16.6 (a))
Scenario:
  A1  신호 없는 `/` 방문 → `/install` 로 이동, 실제 버전·용량·지문 렌더
  A2  `?client_port=&client_nonce=` 가 붙은 `/` → 통과 + 정본 모듈이 좌표 보관
  A3  그 상태에서 **새로고침** → 통과 (배포 자동 반영 `ui-refresh.js` 가 타는 경로)
  A4  같은 창에서 `/admin` 이동 → 통과
  A5  새 탭(저장소 없음)에서 `/admin` → `/install`
  A6  `/?next=/api/ai/oauth/authorize?...` → 통과 · `?next=/admin` → `/install`
Evidence: 총 12건 PASS 12 / FAIL 0 · 캡처
  `artifacts/feature-0003-client-entry-gate/install-page-chrome.png`(1280px)
  `artifacts/feature-0003-client-entry-gate/install-page-chrome-narrow.png`(400px)
역검증: `--negative`(게이트 태그 제거) → A1 FAIL — 하네스가 실제로 게이트를 재고 있다
실측 치수(§16.6 (g)·(i), 400px): `document.scrollWidth=385 ≤ innerWidth=400`,
  지문 우측 367 < 콘텐츠 경계 382 — 가로 넘침 0
시각 판독으로 잡은 결함 1건: 한국어가 음절 중간에서 끊김(「실행하세/요.」) →
  `word-break: keep-all` 적용 후 재캡처로 해소. 그 시점에 자동 검증은 전부 초록이었다.
한계: 일반 브라우저는 **공유 HTML/CSS/JS 의 보조 검증**이다 (§15.4.1) —
  DQA 앱의 창·로그인 저장소·로컬 브리지·트레이를 대체하지 않는다.
```

## Run 3 — 실제 DQA 클라이언트

```text
Environment: DQA-client
Result: NOT-RUN
Reason: 이 앱에는 CDP 등 자동화 진입점이 없다(`client/window.py` 에 remote-debugging 인자
  부재). 그리고 사용자의 DQA 앱이 실행 중이었고(`DQAConnect.exe` PID 12344),
  §16.6 「기존 사용자 앱·연결을 검증 편의로 종료하지 않는다」에 따라 종료하지 않았다.
Alternative: Run 2 가 **같은 Chromium 엔진**에서 배포 파일 원본으로 12건을 실측했다.
  특히 A2·A3 는 앱 창이 실제로 타는 두 경로(첫 적재의 주소 좌표 / 새로고침 뒤 저장소 신호)와
  같은 축이다. 다만 WebView2 의 저장소 격리·창 생명주기는 확인하지 않았다.
Next: 배포 후 실행 중인 DQA 앱이 자동 갱신(`ui-refresh.js`)으로 새 자산을 받은 뒤에도
  대화 화면에 머무르는지(설치 안내로 튕기지 않는지) 확인하고 이 파일에 append 한다.
```
