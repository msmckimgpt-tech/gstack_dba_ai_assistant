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
