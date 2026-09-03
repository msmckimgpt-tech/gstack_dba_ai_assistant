---
type: feature-card
feature_id: feature-0046-native-client
status: in-progress
---

# feature-0046-native-client — Windows 네이티브 클라이언트

## 1. 한 줄

사용자가 **터미널을 열지 않고** 자기 AI 를 이 서비스에 연결한다. `bridge_setup.ps1`(669행)이
하던 일을 **같은 계약으로** 하되 껍데기를 GUI 로 바꾼 것.

## 2. 왜

`docs/improvements/onboarding-accessibility/RESEARCH.md` §9.1 — 연결을 우리가 만든 배포물로
구현하고 런타임·설치 UX·설정 UI·업데이트 채널을 전부 자체 구현해 **넷 모두가 마찰**이 됐다.

## 3. 핵심 제약

- **로그인은 「위임」이 아니라 「대행 실행」** — 벤더 공식 명령을 subprocess 로 띄우고 종료코드만
  본다. 토큰 미접촉. 2026년에 3사가 구독 OAuth 제3자 사용을 차단했고 Google 은 유료 구독자
  계정을 정지했다.
- **러너를 동봉하지 않는다** — 서버에서 받아 체크섬 대조. 동봉하면 배포가 갈린다.
- **Windows 우선 · 미서명** (사용자 결정 2026-09-03). SmartScreen 경고 2클릭 감수.

## 4. 실측 (2026-09-03, 실 Windows)

claude 를 PATH 밖 `.local\bin` 에서 감지 · JSON 로그인 판정 · tkinter 구성 ·
PyInstaller 단일 exe 9.17MB 빌드·실행. 실측이 결함 1건 적발(windowed 빌드의 `print()` 멈춤).

## 5. 정본

`unit/feature-0046-native-client/docs/{FUNCTION,TASK,ANCHOR}.md`
