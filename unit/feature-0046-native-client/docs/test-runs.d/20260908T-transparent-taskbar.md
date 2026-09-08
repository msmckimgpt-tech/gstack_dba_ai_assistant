---
run_at: 2026-09-08T03:37:54+00:00
session: codex-transparent-taskbar
scope: TASK-20260908T-transparent-taskbar
verdict: IN_PROGRESS
---

# DQA 1.1.3 — 투명 아이콘과 작업 표시줄

- 사용자 제보를 실제 설치된 1.1.2(PID 24840)에서 재현했다. EXE/ICO는 종전 검증본과 같지만 실제 작업 표시줄 버튼은 Python 아이콘이었다. 이전 5표면 검사에는 작업 표시줄 버튼 자체가 빠져 있었다.
- 원인: Windows 앱 식별자와 창의 relaunch 메타데이터가 없었다. UI 생성 전 `Masangsoft.DQA.Connect`, 창 property 2/3/4/5, 설치 바로가기의 같은 ID를 적용한다. 재실행 명령에 연결 인자를 남기지 않는다.
- 디자인: 사용자 승인 SVG 정리. 1024 RGBA PNG와 9크기 ICO 모두 배경 alpha=0. design 리뷰 밝음/어두움 16/20/24/32/48px PASS. 웹 6 HTML의 누락 favicon도 같은 SVG/ICO로 연결.

## 자동 검사

- 네이티브 전체 pytest **529 PASS, 실패/skip 0** (55.410초), JUnit `artifacts/dqa-transparent-icon-tests-final.xml`.
- 웹 HTML cache/static integrity/stamp census **30 PASS**, `artifacts/dqa-transparent-icon-web-tests.log`. 최초 PYTHONPATH 순서 오류를 core→web으로 바로잡았다.
- 변경 Python Ruff PASS. SVG/ICO의 웹·클라이언트 복사본 byte 동일.

## Environment: Windows-native

- Windows Python 3.14.0, PyInstaller/Inno Setup 6 최종 빌드 rc=0. 동결 자가진단·동봉 러너 런타임 임포트 PASS.
- `verify_brand_icon.py` native/webview: EXE/Setup 각각 9프레임 RT_ICON byte 일치, 기본 EXE/Setup/트레이/Tk/WebView2 5표면 pixel 일치, ICO 9크기 alpha min=0/max=255/4모서리=0.
- `verify_taskbar_identity.py`: source Tk/WebView2 process AppUserModelID·창 4속성 일치, 실제 숨김/복귀(Tk 3회/WebView2 1회)와 속성 유지, clear 후 VT_EMPTY. MSAA 실제 작업 표시줄 버튼을 캡처하여 Python→DQA 변경을 시각 확인했다.
- `verify_frozen_taskbar.py`: 최종 EXE를 새 USERPROFILE로 실행, 기존 앱·로그인과 분리. EXE 재실행 경로, 동봉 icon, DQA 이름/ID 대조 PASS. 최초 frozen 캡처는 잠금 화면이 taskbar를 가린 것으로 독립 검토에서 판명되어 시각 PASS를 철회했다. 잠금 해제 후 재캡처가 필요하다. 검사 PID만 자기 트레이 [종료] 명령으로 정상 exit=0. 사용자의 PID 24840 및 기존 설치는 유지했다.
- 검사에서 드러난 두 구현 결함을 수정·재검증했다: InitPropVariantFromString은 DLL export가 아닌 inline이므로 COM 메모리 할당으로 교체. Tk 최초 map에 HWND가 교체되므로 <Map>마다 현재 wrapper에 속성을 바인딩.
- 256px PNG ICO의 .NET Icon.ToBitmap 한계를 검사에서 발견하여 PNG 프레임은 Windows Bitmap 디코더로 확인했다. 배포 자산 결함이 아니며 작은 DIB 8프레임은 Icon으로 검증.
- Evidence: `artifacts/dqa-transparent-icon/{verify-native,verify-webview,identity-tk,identity-webview,verify-frozen-final}`의 result.json 및 PNG.

## Environment: Windows-browser

- Runner: AI, Windows Chrome 152.0.7977.75, 별도 프로필, relay `172.26.144.1:9247` → CDP 9246.
- `scenario.brand-favicon.json`을 Windows 임시 정적 서버 복사본으로 실행: **3/3 PASS**. 6 HTML 모두 SVG/ICO 연결, 2자산 HTTP200·올바른 MIME, 페이지 screenshot.
- Evidence: `artifacts/dqa-transparent-browser-staging.json`, `artifacts/dqa-transparent-browser/01-favicon-page.png`.
- 아이콘은 비로그인 공통 head에 적용되므로 로그인·AI 호출 없이 검사했다. 웹 색상·레이아웃은 변경하지 않았다. 배포 후 같은 시나리오와 브라우저 탭을 다시 확인한다.

## 설치/제거·바로가기 경계

- 설치된 1.1.2의 기본 EXE와 unins000.exe 및 기존 스킴/제거 표시 경로를 읽어 정상 참조를 확인했다. 현재 머신에는 DQA 작업표시줄 고정 바로가기가 없었다.
- 새 설치기의 SetupIconFile은 새 ICO이며 EXE/Setup 리소스를 실측했다. 시작 메뉴·바탕화면·자동 시작 3개 앱 바로가기 모두 같은 AppUserModelID/IconFilename을 지정하도록 계약 검사했다.
- 실행 중인 사용자 앱을 중단하는 실제 재설치/제거는 수행하지 않았다. 새 버전 설치 후 생성되는 .lnk 실물 및 기존 고정 바로가기 캐시 갱신은 이 실측과 구분한다. 고대비 모드도 미실측이다.

## 배포 후보

- DQAConnect-Setup-1.1.3.exe: **25,876,951 bytes**.
- SHA-256: `132d5d715b73673c60c78cb54e1957f9b5c117612c4d1a26e9b9fbc75df903ac`.
- Windows 빌드→Linux 보관본 크기/해시/byte 동일. PR 병합·기존 설치기 채널 반영·웹 rolling 배포 후 라이브 검증을 추가한다.

## 참고 계약

[Microsoft AppUserModelID](https://learn.microsoft.com/en-us/windows/win32/shell/appids), [창 속성 수명](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shgetpropertystoreforwindow), [재실행 아이콘](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchiconresource).

- 후속: Windows 잠금 화면(`LockScreenBackstopFrame`) 가림을 검수 도구가 탐지하도록 보완 중. 최종 frozen/탭 PNG 시각 확인은 잠금 해제 후 수행한다. 로그인·사이드바·빈 대화·관리 사이드바의 기존 로고 이미지 4곳도 같은 SVG로 정합했다.
