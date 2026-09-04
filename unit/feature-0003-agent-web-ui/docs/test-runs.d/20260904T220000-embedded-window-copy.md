---
run_at: 2026-09-04T22:10:00+09:00
session: embedded-window (ai/claude/feature-0046-embedded-window)
scope: 앱 창 안의 문구에서 「연결 프로그램」 제거 · DQA 하나로
verdict: PASS (정적·실행) / 라이브 시각검증은 배포 후
---

### Run (2026-09-04) — 직전 주기의 이연 항목 해소 — **Environment: Windows-browser**

`20260904T200000-standalone-launch.md` 가 이연했던 「인자 없는 실행 → 앱 창」을 배포 `4c4dc8a5`
에서 실측했다. 브리지가 뜨고 창 목록에 **「DQA — Database Query Assistant」** 실재.
서빙되는 `client-bridge.js` 에 `_connectLaunch` 가 있음을 확인(배포 도달) · 엣지 무중단 0건.

### Run (2026-09-04) — 문구 변경 — **Environment: host node + pytest**

- `client-bridge.js` 는 가짜 DOM 위에서 **실제 import 해 클릭 핸들러를 호출**한다(13건).
  문구를 바꾸면서 봉투 전달·순서·실패 삼킴 계약이 깨지지 않았음을 그 하네스가 확인한다.
- 「연결 프로그램」이 **화면 문구에서** 사라졌는지는 주석을 걷어 낸 뒤 검사한다
  (`test_panel_says_when_the_bridge_is_gone`) — 설계를 설명하는 주석은 남는 것이 옳다.
- ⚠ **브라우저로 방문한 사람용 안내는 그대로 둔다.** 그쪽에는 「받아서 설치할 것이 있다」가
  여전히 사실이다. 바꾼 것은 앱 창 안에서 보이는 문구뿐이다.

### Run (2026-09-04) — 앱 창에서 연결 완주 — **Environment: Windows-browser (배포 후로 이연)**

- 정적 자산은 이미지에 **baked** 되어 web 재배포 후에만 라이브에 반영된다.
- 계획: 배포 → 설치본 재빌드·재설치 → 아이콘 실행 → 내장 창 로그인 → [연결 준비] → 목록 →
  [이 서비스에 연결] → `ai:ok` → 창 닫고 아이콘 재실행 시 창 복귀.
