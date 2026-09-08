---
run_at: 2026-09-08T15:12:00+09:00
session: codex-text-interaction
scope: feature-0046-native-client
verdict: PARTIAL
---

# TASK-20260908-text-interaction

Environment: DQA-client
Result: PASS
Build: 49f7fa41 + window.py text_select/loaded patch; Windows CPython 3.14, pywebview, WebView2 152; source Shell, isolated document fixture with production base.css/chat.css.
Scenario: 답변·Markdown 첨부·원문 코드 드래그→Ctrl+C→입력창 Ctrl+V, 읽기 전용 본문 유지.
Evidence: ../artifacts/20260908-text-interaction/fixed.json 및 text.png. 3표면 selection == expected, Windows Clipboard == expected, textarea == expected. 읽기 전용 본문 불변 true.

이전 설정(text_select=False/accelerators=False) 대조군은 3표면 모두 selection 빈 문자열로 실패했다(control.json). 이전 동작의 원인을 재현하는 의도된 음성 대조이며 수정본의 실패가 아니다. 테스트 마우스 이동은 실제 드래그처럼 각 이동 사이 30ms를 두어 합성 입력 합쳐짐을 피한다. 초기 빠른 입력에서 Markdown 선택이 한 번 누락되어 이 시간 간격을 추가한 뒤 세 표면 모두 통과했다.

Environment: DQA-client
Result: NOT-RUN
Build: same Shell patch
Scenario: Ctrl+F 검색창 열기→needle 일치→F3/Shift+F3 이동→Escape 닫기.
Reason: 이 호스트에서 SendKeys/대상 HWND 메시지는 브라우저 accelerator로 전달되지 않았다. CDP 키는 문서 편집에만 도달했다. 브라우저 기본 검색 UI 실측을 확보하지 못했다.
Alternative: 실제 CoreWebView2 Settings.AreBrowserAcceleratorKeysEnabled=True, AreDevToolsEnabled=False, 재로드 후 accelerator=True 및 last_error=null. 이는 설정 실측이고 검색 UI PASS가 아니다. 초기 UIA 트리 변화 기반 판정은 무효로 철회하고 내구 검증기에서 제거했다.
Next: 실제 앱 소유 창에 전달된 native 키 입력과 검색어·일치번호·닫힘을 함께 확인할 수 있는 환경에서 재검증.

전체 요청 실측은 PARTIAL. 4개 텍스트/읽기전용 검사 PASS, 검색 UI 시나리오 1개 NOT-RUN(1/5). PDF·스프레드시트·OCR 뷰어, 실제 사용자 계정 대화, 설치본 교체는 검증하지 않았다. 텍스트 선택 옵션과 순수 핸들러 설정은 문서 기하를 바꾸지 않아 요소 상태 검증으로 판정하며 참고 캡처를 함께 보존한다.

Environment: CLI
Result: PASS
Scenario: native suite 530 passed / 1 skipped (기존 플랫폼 적용대상 skip); window 50 passed. 버전 변경 후 updater/window 재검증 137 passed (1.98s).

Environment: Windows-build
Result: PASS
Scenario: DQA 1.2.3 PyInstaller/Inno Setup 빌드 exit0, 동결본 창 self-test와 동봉 runtime 검증은 build_client.py에서 실행.
Evidence: ../artifacts/20260908-text-interaction/build.json — 26,048,286 bytes, SHA-256 85b69a01da88019031c7cead689d6c7c4359d750b58f7ed32a22958424c5d672. 사용자 설치본 실행·업데이트 설치 검증은 하지 않았다.

## Source evidence

- https://pywebview.flowrl.com/api/ — text_select default False.
- Windows 설치 pywebview/platforms/edgechromium.py:287 — AreBrowserAcceleratorKeysEnabled = debug.
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2settings.arebrowseracceleratorkeysenabled — Ctrl+F/F3 범위 및 Ctrl+C/V 기본 편집과 구분.

Environment: Published-client
Result: PASS
Scenario: 최신 릴리스 조회 및 실제 설치기 다운로드.
Evidence: ../artifacts/20260908-text-interaction/published.json. 프로젝트 CA 검증한 HTTPS로 두 경로 200; 버전1.2.3, 26,048,286bytes, Windows 빌드와 SHA-256 일치. 기존 사용자 설치본은 변경하지 않았다.
