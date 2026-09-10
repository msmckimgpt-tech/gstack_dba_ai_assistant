# 투명 아이콘 1.3.1 웹 배포 검증

Environment: DQA-client
Result: NOT-RUN
Scenario: 배포된 DQA 로그인 화면의 새 투명 로고
Reason: 클라이언트 후보와 정적 자산은 준비됐으며 main병합·웹배포 후 실제 DQA 창에서 확인한다.
Alternative: HTML6favicon/4로고배선·웹30회귀·노트34회귀·독립디자인PASS. 실제Windows새작업표시줄및설치는 feature-0046 원장참조.

[클라이언트 통합 원장](../../../feature-0046-native-client/docs/test-runs.d/20260910-transparent-icon-release.md).

## 배포 후 실제 DQA 확인 — 2026-09-10
- Environment: DQA-client
- Result: PASS
- Scenario: 배포된 DQA 로그인 화면의 새 투명 로고
- PR1617 main ebf5e365, 공개채널1.3.1. Windows https://localhost에서 다운로드한25,945,487bytes SHA256 `1e4d7fa471ff7825d67e30f7a127d90b39218d1986e27ab2ded5f4b9121b9a4e`가검증빌드와일치. 웹2replica ebf5e365 ready 및90초soak PASS. rootCA로TLS검증한favicon/로고/릴리스노트바이트가main과일치.
- 실제1.3.1 DQA를새프로필과명시적localhost주소로실행하여배포된로그인화면에서투명심볼·창/작업표시줄아이콘을직접확인했다. 사용자로그인/설치는건드리지않았다. [실제화면](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-dqa-login.png), [실행](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-dqa.json), [서빙자산](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-web.json), [배포](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/deploy-web.log).
- 캡처하네스는Windows빌드Python에Pillow가없어실패한뒤기존.NET Drawing사용으로정합했다. 처음DPI미인식좌표가다른창을가리킨검사는실패로보존하고per-monitor DPI컨텍스트설정후실제캡처PASS를확인했다. 제품앱코드변경이아니다.
- 기본공인주소112.185.196.20은Windows80/443실제listener누락으로접속거부. localhost다운로드/실제앱PASS를공인주소PASS로표현하지않는다. feature-0006의원인수정·관리자적용·공인주소재검증을이어간다. [Windows접근결과](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/channel-windows.json).

## 공인 주소 복구 후 최종 확인 — 2026-09-10 11:39 KST
- Environment: DQA-client
- Result: PASS
- Scenario: 배포된 DQA 로그인 화면의 새 투명 로고
- Windows 사용자 UAC 승인 후 feature-0006의 검토한 스크립트를 적용했다. 누락된 112.185.196.20:80/443 리스너만 복구했고 다른 매핑·6379/28080 리스너를 보존했다. 방화벽 변경/서비스 재시작 없음.
- Windows에서 프로젝트 rootCA로 검증한 공인 HTTPS와 localhost 양쪽의 최신 manifest가 1.3.1이며, 실제 다운로드 SHA256이 검증된 설치기와 일치한다. [다운로드 결과](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/channel-windows-restored.json).
- 기본 주소를 재정의하지 않은 실제 동결 DQA 1.3.1의 새 프로필에서 공인 서비스 로그인 화면을 확인했다. 투명 로고·제목 표시줄·작업 표시줄 심볼을 직접 검수했다. [로그인 화면](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public-login.png), [작업 표시줄](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public-taskbar.png), [실행/정상 종료](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public.json).
- 첫 공인 주소 캡처는 탐색기 창에 가려 실패했다([가림 기록](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public-occluded.json)). 하네스가 자신이 띄운 검증 창만 잠시 최상위에 두고, 캡처 후 원복·정상 종료하도록 수정하여 재검증했다. 사용자 앱은 종료하지 않았다.
- 배포 제품 commit ebf5e365, 설치기25,945,487 bytes, SHA256 `1e4d7fa471ff7825d67e30f7a127d90b39218d1986e27ab2ded5f4b9121b9a4e`. 이후 후속 커밋은 Windows 운영 스크립트·검증 하네스·문서만 변경한다. 웹 제품/게시된 설치기 bytes는 동일하다.
