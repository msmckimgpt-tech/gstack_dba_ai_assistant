---
playbook_id: PB-0009
name: dqa-client-verification
description: 실제 DQA 클라이언트에서 변경된 화면과 사용자 동작을 검증한다
trigger: UI/client change
scope: feature
---

# DQA 클라이언트 검증

사용자 결정(2026-09-08)에 따라 서비스의 주 사용 경로는 DQA 클라이언트다.
권한·완료 판정은 [AGENTS §15.4.1](../AGENTS.md)가 정본이다. 일반 Chrome/Edge를
띄우는 [PB-0008](PB-0008-windows-browser-verification.md)은 보조 호환 검증이다.

## 변경 범위부터 정한다

| 변경 | 필요한 확인 |
|---|---|
| 앱에 표시되는 HTML/CSS/JS | 실제 DQA 창의 변경 영역·표시값·관련 조작; 레이아웃이면 캡처 |
| 로컬 AI 연결·로그인·능력 표시 | DQA 화면→로컬 브리지→결과 표시, 오류·미연결 상태 |
| 창/트레이/종료 | 해당 네이티브 생명주기; `tests/windows/verify_embedded_close.py` 참고 |
| 설치·업데이트 | 설치본/배포본 버전·수신 파일 검증·재실행 후 도달 |
| 정책·테스트 도구만 변경 | 관련 자동검증; 제품 화면 재검증·재설치 불요 |
| 일반 브라우저에만 남은 호환 분기 | 해당 분기 검증 + DQA 내부에서 호출되지 않는 음성 대조; 앱 전체 검증으로 표기하지 않음 |

## 실행

1. [feature-0046 FUNCTION](../unit/feature-0046-native-client/docs/FUNCTION.md)의 변경에 해당하는 절과
   변경 영역의 현재 TASK를 읽고 입력→기대 결과를 정한다. 최신 사용자 위임·테스트 계정 범위를 확인한다.
2. 실제 DQA 프로세스·빌드·서비스 origin을 확인한다. 현재 구현의 주 창은
   `src/client/window.py`의 내장 WebView2다. 별도 브라우저 프로세스나 tkinter 폴백은
   같은 검증 대상이 아니다. 앱의 로컬 브리지 포트와 WebView2 CDP 포트도 구별한다.
3. 이미 지원되는 앱 자동화/CDP 경로가 있으면 그 **DQA 소유 WebView2**에 연결한다.
   포트 번호를 추정하거나 일반 브라우저 `:9222`에 연결해 DQA 검증이라고 보고하지 않는다.
   기존 사용자의 앱·연결 작업을 검증 편의로 종료하거나 재설치하지 않는다.
4. 변경된 사용자 흐름과 관련 실패 경계를 확인한다. 창/트레이 검증은
   [Windows 검증 README](../unit/feature-0046-native-client/tests/windows/README.md)의
   실제 스크립트를 사용한다. 격리 개발본/fixture로 실행했다면 설치본·라이브 검증과 구분한다.
   단순 표시/배선 점검에 유료 AI 질의나 서비스 데이터 변경을 추가하지 않는다.
5. Run에 대상 revision, 환경, 결과, 증거, 미검증 범위를 남긴다. 자동화가 불가하면
   구체적인 관찰 결과와 가능한 하위 검증을 남긴다. `NOT-RUN`은 PASS가 아니다.
   본인 생성 테스트 인스턴스/파일만 정리하고 기존 DQA 사용 세션을 유지한다.

## Run 형식

각 실행은 `unit/<소유 feature>/docs/test-runs.d/<TASK-id>.md`에 기록한다.
아래는 형식 예시이며 실제 실행 결과가 아니다:

```text
Environment: DQA-client
Result: NOT-RUN
Build: <설치/개발본 버전 + 서버 revision>
Scenario: <입력과 기대 사용자 결과>
Evidence: <실행 로그/캡처/요소 상태의 경로>
Reason: <미실행이면 실제 접근 제한>
Alternative: <수행한 Node/CLI/브라우저 검증과 그 한계>
Next: <재검증할 조건과 범위>
```

실측한 경우에만 `Result: PASS` 또는 `FAIL`을 쓴다. 파일에 환경 단어가 있다는 사실,
프로세스가 존재한다는 사실, 서버 200 응답만으로 사용자 흐름 PASS를 선언하지 않는다.
과거 `Windows-browser` Run에 실제 DQA 설치본 증거가 있으면 그 근거를 참조할 수 있으나,
현재 변경의 새 실행으로 재사용하지 않는다.

같은 파일 안에서 재검증하면 각 Run에 동일한 `Environment`와 명시적인 `Scenario` 값을
반복하고, 최신 Run에 실패 원인·해소 내용·재검증 증거를 남긴다. check #13은 같은 DQA
시나리오의 마지막 결과를 현재 상태로 보며 이전 실패 기록은 보존한다. 다른 시나리오,
시나리오 미기재 Run, 별도 파일의 PASS는 해당 실패를 해소하지 않는다.


현재 check #13의 네이티브 UI 자동 탐지는 `client/{window,appwindow,gui,tray,bridge}.py`에
한정한다. 새 UI 파일·설치기 변화는 작업자가 변경 범위에서 별도로 확인해야 하며,
스크립트가 탐지하지 않았다는 이유로 UI 영향이 없다고 판정하지 않는다.
