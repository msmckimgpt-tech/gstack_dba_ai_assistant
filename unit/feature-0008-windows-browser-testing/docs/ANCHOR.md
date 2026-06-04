---
doc_type: ANCHOR
feature_id: feature-0008-windows-browser-testing
created_at: 2026-06-04T16:10:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0008-windows-browser-testing

## §1. 외부 관점 요약
"테스트인데 왜 WSL headless 가 아니라 굳이 실제 Windows 브라우저를 띄워서 CDP 로
조작하지? 복잡하게." → 이유: 이 프로젝트는 WSL2 위에서 돌지만 **실제 사용자는 Windows
브라우저**로 본다. AI 가 CLI(curl)·WSL headless 로만 "검증함"이라고 선언해 온 결과,
사용자가 Windows 브라우저에서 보는 화면과 자주 어긋났다(렌더링·상호작용 차이). headless
는 "사용자가 보는 것"을 대변하지 못한다. 그래서 검증의 정본 환경을 실제 Windows
브라우저로 옮기고, 그것을 AI 가 자동 구동하도록 만들었다.

## §2. 대안 분기
- **Alt-A: 사람 확인 게이트(human-in-the-loop).** 페르소나: 자동화 인프라를 늘리고 싶지
  않은 1인 운영자. AI 가 Windows 브라우저를 열고 체크리스트를 주면 사람이 눈으로 확인.
  안 고른 이유: 사용자가 "AI 자동 구동 중심"을 명시 요청 — 매 검증마다 사람 개입은 마찰.
- **Alt-B: WSLg headful chromium.** 페르소나: 설정을 최소화하려는 팀. WSL 안 chromium 을
  headful 로 띄워 WSLg 로 Windows 데스크톱에 표시. 안 고른 이유: 그래도 **Linux chromium**
  이라 사용자의 실제 Windows Chrome 렌더링과 다름 — "wsl 내부가 아닌" 요구와 어긋남.
- **Alt-C: gstack /browse·feature-0004 그대로.** 안 고른 이유: 둘 다 WSL 내부 headless —
  바로 이 괴리의 원인. 보조(빠른 탐색)로만 공존시킴.

## §3. 가정된 사용 시나리오
6개월 뒤, 새 동료 개발자가 feature-0003 웹 UI 의 로그인 폼을 수정하고 "완료"하려 한다.
그는 `curl` 로 200 을 확인하고 끝내려 하지만, 완료 체크리스트와 check #13 WARN 이
"웹 변경 → Windows-browser 검증 필요(PB-0008)"를 상기시킨다. 그는 `python3
bin/win-browser.py launch` 로 자기 Windows 브라우저를 띄우고 시나리오를 돌려, 실제로
버튼 정렬이 깨진 것을 스크린샷으로 발견한다 — curl 로는 절대 못 봤을 결함을.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. §18.8 검증 패널 결과는 REVIEW.md 참조.)
