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

## Run 4 — 라이브 배포 후 도달성 (2026-09-10 13:47 KST, append)

```text
Environment: Windows-browser (라이브 서비스)
Result: PASS
Build: 서버 release=4b2dd68c · asset_stamp=485a9a2696e0 (두 replica 일치) ·
  `bin/deploy-web.sh --web-only` soak PASS · Chrome/152.0.7977.83 전용 프로파일
Scenario / Evidence (총 6건 PASS 6 / FAIL 0):
  L1  `https://localhost/` → `/install` 로 이동
  L2  안내 화면이 **라이브 릴리스 값**을 렌더 — `1.4.0 · 24.7MB · Windows 10 · 11 · 2026-09-10 게시`
  L3  안내 화면은 게이트를 싣지 않는다(자기 자신으로 되보내는 왕복 없음)
  L4  `?client_port=&client_nonce=` 가 붙은 라이브 `/` → 통과
  L5  그 상태의 **새로고침** → 통과 (배포 자동 반영 `ui-refresh.js` 가 타는 경로)
  L6  같은 창의 `/admin` → 통과
서버 표면: `/healthz` git_commit=4b2dd68c · `/install` 200 text/html ·
  `/api/ai/client/entry` 가 실 매니페스트(1.4.0 · sha256 41b53275…) 반환
```

## Run 5 — 실행 중인 사용자 DQA 앱 (수동 관측)

```text
Environment: DQA-client
Result: PASS (관측 범위 한정 — 아래 «확인하지 않은 것» 참조)
Build: 서버 4b2dd68c 배포 직후 · `DQAConnect.exe` PID 12344 (사용자 실행 세션, 미종료)
Scenario: 배포로 새 자산이 나간 뒤 **실행 중인 앱이 설치 안내로 튕기지 않는가**
Evidence: 창 캡처 2회(배포 직후·수 분 뒤) — 두 번 모두 사이드바·대화·작성창이 있는
  **정상 대화 화면**. 설치 안내 화면 아님.
  `artifacts/feature-0003-client-entry-gate/dqa-app-after-deploy{,-2}.png`
방법: `PrintWindow` 로 **수동 관측만** 했다 — 앱을 종료·조작·재설치하지 않았고
  입력을 넣지 않았다(§16.6 「기존 사용자 앱·연결을 검증 편의로 종료하지 않는다」).

확인하지 않은 것 (정직 표기):
  - **이 앱이 이미 새 빌드로 재적재됐는지는 미확인.** 자동 반영은 «안전한 시점»에
    적용되므로 아직 옛 자산일 수 있다. web/caddy 컨테이너에 접근 로그가 없어
    (`docker compose logs` 0건) 자산 요청으로 가릴 수도 없었다.
  - 그 재적재 경로 자체는 Run 4 의 **L5** 가 같은 Chromium 엔진 + 라이브 배포본으로
    실측했다. 즉 「앱이 지금 정상」 + 「재적재 경로가 통과」 두 사실을 각각 얻었고,
    「이 앱이 재적재를 거쳐 정상」이라는 합산 관측은 아니다.
  - WebView2 고유 축(창 생명주기·로컬 브리지·트레이)은 이번 변경 범위가 아니라 미확인.
```
