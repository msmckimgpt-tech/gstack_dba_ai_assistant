---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# TASK-20260910-transparent-icon-release

## 최신 버전 통합
- main 7420526a와 아이콘 branch 9a889843을 양 부모로 통합했다. Windows 슬롯 설치/고정 런처, Ctrl+F/텍스트 선택, 최신 웹 기능은 보존했다. source .py와 6 HTML의 main 대비 diff가 아이콘/버전 의도만 포함하는지 대조했다.
- 1.1.3 후보는 폐기하고 공개1.3.0보다 새 1.3.1을 Windows Python/PyInstaller/Inno Setup으로 빌드했다. 런처 C# 기능은 main과 동일하며 PE 아이콘만 변경했다.
- [설치기 지문](../artifacts/20260910-transparent-icon/candidate.json). 현재 게시 전 후보이며 배포 결과는 후속 Run에 기록한다.

## 회귀
- Environment: CLI
- Result: PASS
- native **624 passed**, skip0. 웹 HTML cache/static integrity/stamp census **30 passed**, 릴리스노트 DOM **34 passed**.
- 처음에는 jsdom이 없어 1건 skip이었다. 의존성을 갖추자 main 테스트가 유효한 32자 nonce를 넣고 옛 `secret`을 기대하는 오류를 발견했다. fixture nonce를 공유 상수로 정합한 후 전체624건 통과. 제품 인증 동작 변경은 없다.
- [native](../artifacts/20260910-transparent-icon/native-all.log), [web](../artifacts/20260910-transparent-icon/web.log), [notes](../artifacts/20260910-transparent-icon/notes.log).

## 실제 동결본 및 설치본 아이콘
- Environment: DQA-client
- Result: PASS
- Scenario: 1.3.1 동결 실행본과 1.3.0→1.3.1 격리 설치본의 Windows 작업 표시줄.
- 잠금/가림 검사 통과한 실제 taskbar PNG에서 배경 없는 DQA Q/두 데이터 획을 직접 확인했다. Python 기본 아이콘이 아니다. 앱 식별자 Masangsoft.DQA.Connect, 설치본의 root DQALauncher.exe 및 root dqa.ico 재실행 속성, 정상 트레이 종료를 확인했다.
- [동결본](../artifacts/20260910-transparent-icon/frozen.json), [동결 taskbar](../artifacts/20260910-transparent-icon/frozen-taskbar.png), [설치 taskbar](../artifacts/20260910-transparent-icon/installed-taskbar.png).
- EXE/Setup/launcher/compatibility EXE/Uninstall 리소스의 ICO9프레임, Tk/WebView2/트레이 실제 픽셀, 9크기 실제 알파와 투명 모서리를 확인했다. [native](../artifacts/20260910-transparent-icon/resources-native.json), [WebView2](../artifacts/20260910-transparent-icon/resources-webview.json).

## 실제 설치·실패·제거
- Environment: DQA-client
- Result: PASS
- Scenario: 별도 AppId/표시이름/스킴/설치경로/홈의 1.3.0 실제 앱과 제어된 페이지·장시간 fixture runner를 유지하며 1.3.1 업데이트.
- 앱/러너 PID, draft, page instance, 로컬 bridge 연결 유지. 정상 종료 뒤 이전 root 실행 경로로 새1.3.1과 fixture cookie 복귀. 두 실행기 PE 아이콘과 안정 ICO 갱신 확인.
- 잘못된 install-complete 마커와 잠긴 launcher 각각 설치 nonzero·기존 active-slot·앱/러너 생존을 확인. pointer 지속잠금 실패/일시잠금 재시도, global설치mutex 배제, 같은버전 새슬롯 재설치도 통과.
- **검사 중 발견·수정:** Inno가 AfterInstall의 RaiseException을 억제하고 계속 설치하여 launcher 교체 실패 뒤에도 활성화하던 결함을 재현했다. SlotVerified/LauncherReady의 성공값을 ssPostInstall에서 확인하고, 실패 시 pointer를 쓰지 않고 exit10으로 반환한다. payload 실패 시 launcher/compatibility 교체도 건너뛴다. 수동 완료 페이지에는 실패 안내를 지정했다. 공식 근거: https://jrsoftware.org/ishelp/topic_scriptevents.htm .
- 기존 앱을 종료하지 않는 교체이며, 성공한 동일 기능 런처는 이후 활성화 실패 시에도 새 bytes로 남을 수 있다. 전체 파일 롤백을 보장하는 설계가 아니다.
- 새 설치와 업그레이드 각각 시작메뉴·바탕화면·자동시작 3바로가기의 target/AppID/ICO, 스킴 DefaultIcon, 제거 DisplayIcon을 실제 Shell/registry로 확인. 제거exit0 후 launcher/pending/ICO 잔존0.
- [업데이트 결과](../artifacts/20260910-transparent-icon/upgrade.json), [실행 로그](../artifacts/20260910-transparent-icon/upgrade-final.log), [새 설치](../artifacts/20260910-transparent-icon/fresh-shell.json), [업그레이드 바로가기](../artifacts/20260910-transparent-icon/upgrade-shell.json), [제거](../artifacts/20260910-transparent-icon/install-cleanup.json).

## 검증 한계
- 제어된 fixture runner/페이지 검증이며 실제 유료AI 대화·사용자 계정 로그인 상태를 대신 검증하지 않는다. 기존 사용자 앱/설치를 변경하거나 종료하지 않았다.
- 수동 설치의 실패 완료 화면 픽셀과 실제 작업표시줄 핀 메뉴 클릭은 미검증이다. 정상/실패 설치 종료코드·실제 창 속성·설치 바로가기/실제 재실행·작업표시줄 표시 검증과 구별한다.
- 웹4로고는 배포 후 실제 DQA 로그인 화면에서 확인할 예정이다.

## 배포 후 실제 DQA 확인 — 2026-09-10
- Environment: DQA-client
- Result: PASS
- Scenario: 배포된 DQA 로그인 화면의 새 투명 로고
- PR1617 main ebf5e365, 공개채널1.3.1. Windows https://localhost에서 다운로드한25,945,487bytes SHA256 `1e4d7fa471ff7825d67e30f7a127d90b39218d1986e27ab2ded5f4b9121b9a4e`가검증빌드와일치. 웹2replica ebf5e365 ready 및90초soak PASS. rootCA로TLS검증한favicon/로고/릴리스노트바이트가main과일치.
- 실제1.3.1 DQA를새프로필과명시적localhost주소로실행하여배포된로그인화면에서투명심볼·창/작업표시줄아이콘을직접확인했다. 사용자로그인/설치는건드리지않았다. [실제화면](../artifacts/20260910-transparent-icon/live-dqa-login.png), [실행](../artifacts/20260910-transparent-icon/live-dqa.json), [서빙자산](../artifacts/20260910-transparent-icon/live-web.json), [배포](../artifacts/20260910-transparent-icon/deploy-web.log).
- 캡처하네스는Windows빌드Python에Pillow가없어실패한뒤기존.NET Drawing사용으로정합했다. 처음DPI미인식좌표가다른창을가리킨검사는실패로보존하고per-monitor DPI컨텍스트설정후실제캡처PASS를확인했다. 제품앱코드변경이아니다.
- 기본공인주소112.185.196.20은Windows80/443실제listener누락으로접속거부. localhost다운로드/실제앱PASS를공인주소PASS로표현하지않는다. feature-0006의원인수정·관리자적용·공인주소재검증을이어간다. [Windows접근결과](../artifacts/20260910-transparent-icon/channel-windows.json).

## 공인 주소 복구 후 최종 확인 — 2026-09-10 11:39 KST
- Environment: DQA-client
- Result: PASS
- Scenario: 배포된 DQA 로그인 화면의 새 투명 로고
- Windows 사용자 UAC 승인 후 feature-0006의 검토한 스크립트를 적용했다. 누락된 112.185.196.20:80/443 리스너만 복구했고 다른 매핑·6379/28080 리스너를 보존했다. 방화벽 변경/서비스 재시작 없음.
- Windows에서 프로젝트 rootCA로 검증한 공인 HTTPS와 localhost 양쪽의 최신 manifest가 1.3.1이며, 실제 다운로드 SHA256이 검증된 설치기와 일치한다. [다운로드 결과](../artifacts/20260910-transparent-icon/channel-windows-restored.json).
- 기본 주소를 재정의하지 않은 실제 동결 DQA 1.3.1의 새 프로필에서 공인 서비스 로그인 화면을 확인했다. 투명 로고·제목 표시줄·작업 표시줄 심볼을 직접 검수했다. [로그인 화면](../artifacts/20260910-transparent-icon/live-public-login.png), [작업 표시줄](../artifacts/20260910-transparent-icon/live-public-taskbar.png), [실행/정상 종료](../artifacts/20260910-transparent-icon/live-public.json).
- 첫 공인 주소 캡처는 탐색기 창에 가려 실패했다([가림 기록](../artifacts/20260910-transparent-icon/live-public-occluded.json)). 하네스가 자신이 띄운 검증 창만 잠시 최상위에 두고, 캡처 후 원복·정상 종료하도록 수정하여 재검증했다. 사용자 앱은 종료하지 않았다.
- 배포 제품 commit ebf5e365, 설치기25,945,487 bytes, SHA256 `1e4d7fa471ff7825d67e30f7a127d90b39218d1986e27ab2ded5f4b9121b9a4e`. 이후 후속 커밋은 Windows 운영 스크립트·검증 하네스·문서만 변경한다. 웹 제품/게시된 설치기 bytes는 동일하다.
