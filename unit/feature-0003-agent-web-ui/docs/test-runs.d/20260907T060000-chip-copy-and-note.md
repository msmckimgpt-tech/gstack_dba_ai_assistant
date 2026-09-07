---
run_at: 2026-09-07T06:00:00+09:00
session: ai/claude/feature-0003-model-list-visible
scope: 칩 툴팁 2문단 축약 · 컴포저 안내 문단 제거 후 하단 정합
verdict: PASS
---

### Run (2026-09-07) — 칩 툴팁 · 안내 제거 — **Environment: Windows-browser (PB-0008)**

- Environment: **Windows-browser** (PB-0008) + **격리 컨테이너** `https://172.26.154.233:18099`
  (라이브 web 이미지 `mysql-ai-web:ab70380c` + 본 branch `src/static`·`src/routers`·`shared` 마운트,
  `docker compose run --no-deps`). 라이브 `web-a`/`web-b` 및 공유 트리는 **무접촉** (§13.2.9).
- Runner: AI · Bridge: relay @ `http://172.26.144.1:9223` (Chrome/152.0.7977.75)
- 세션: `win-browser.py session-login`(격리 프로필, `already: false` → `bootstrap_admin`/admin)
- Scenario: `src/scenario.chip-copy-and-note.json`
- Evidence: `/tmp/win-browser-shots/step_09_20260907_153413.png`(안내 없는 하단) ·
  `step_13_20260907_153413.png`(`+` 메뉴 열림)

| 확인 | 값 |
|---|---|
| 안내 문단 요소 | `#composerActionsSelectorNote` → **없음** (`note: false`) |
| 안내 문단 CSS | 파싱된 `.composer-actions-note` 규칙 → **0건** (`cssRule: false`) |
| 칩 툴팁 | `내 AI 가 대기 중입니다.` + 개행 + `질문을 보내면 바로 가져갑니다.` = **2문단 · 33자** |
| 하단 정합 | `.sidebar-profile` bottom **889** ↔ `.composer-wrap` bottom **889** — **일치** |
| 컴포저 박스 | top 831 / bottom 881 / height 50 (안내가 켜져도 바뀔 요소가 없다) |
| `+` 메뉴 | 파일 첨부 · 첨부파일 목록 · 모델: Opus 4.6 · 추론 강도: 낮음 — 정상 렌더 |

- **툴팁은 «값» 이라 element 상태로 판정한다** (§16.6 evidence 분기). 네이티브 `title` 은 OS 가
  페이지 밖에 그리므로 스크린샷에 담기지 않는다 — hover 캡처(`step_09`)는 그 사실의 기록이고,
  문안 자체는 `el.title` 실측으로 확인했다. 반대로 **레이아웃(높이 정합)은 픽셀-클래스**라
  캡처가 필수이며, 위 두 스크린샷이 그것이다.
- **비교 기준**: 사용자 제보 스크린샷에서는 같은 자리에 「연… 했습니다 — 최신 실행 파일로 다시
  실행해 보세요. 실행 파일 받기」 한 줄이 입력창 위에 서 있었고 그만큼 컴포저가 올라가 있었다.
- Pass/Fail: **PASS**

### 정리

`repo-web-verify` 컨테이너는 검증 종료 후 제거한다(아래 REPORT 참조). 라이브 스택의 이미지·
컨테이너·공유 트리에는 손대지 않았다.
