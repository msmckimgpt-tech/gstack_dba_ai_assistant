---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# TASK-20260909-nondisruptive-update

## 로컬 회귀
- Environment: CLI
- Result: PASS
- native617 passed /1 skipped; 마지막 업데이트 문구 수정 후 focused112 passed. 릴리스노트 renderer34개 통과.
- [native](../artifacts/20260909-nondisruptive-update/native.log), [focused](../artifacts/20260909-nondisruptive-update/focused.log), [notes](../artifacts/20260909-nondisruptive-update/release-notes.log).

## 설치된 Windows 앱
- Environment: DQA-client
- Result: PASS
- Mode: 별도 AppId/스킴/설치경로/홈을 사용하는 실제 DQA 설치본. 페이지와 장시간 자식 러너는 제어된 fixture. 공개 설치본과 설치코드·앱payload 동일, 패키지 식별자 및 시험 업데이트 서버만 격리. [파일 해시](../artifacts/20260909-nondisruptive-update/build.json).
- 실제1.2.5 설치본에서 EXE/runtime만 복사. 사용자 토큰·홈·로그인 원본 및 실행 중 앱은 변경하지 않았다.
- 최초 활성화 강제실패: 설치기nonzero, 원래EXE SHA동일 복원, DQALauncher --selftest로 legacy 실행, app/runner PID유지.
- legacy→1.3.0 직접 설치: app29780 /runner53960 유지, 실행 중 root EXE rename 및 런타임 보존.
- 실제1.3.0→시험용1.3.1 앱 내부 업데이트: app17268 /runner3128 유지, runner진행2→274. bridge좌표·page instance·draft 동일, 페이지 reload0회. 결과prepared=true/restarting=false. 같은 버전 재권유 없음.
- 지속pointer잠금:5초 제한 재시도 후nonzero, 이전pointer/app/runner유지. Global설치mutex 점유: 두번째설치거절. 실제 서로 다른Windows 세션 두 개 실험은 아님.
- 일시pointer잠금: Win32 MoveFileEx error5 확인후 오류5/32/33 제한재시도로 수정. 최종설치기에서 잠금해제후성공, 같은버전도 새1.3.1-3 슬롯사용.
- 정상트레이종료후 오래된root EXE경로로실행: 새1.3.1 및 기존fixture브라우저cookie 복귀. 별도 후속 DQA 기동에서1.3.0-2 슬롯EXE도1.3.1-3으로 전달되는 것을 확인했다. 실제 작업표시줄 핀 클릭과실제서비스 로그인·선택은 별도미검증.
- [결과](../artifacts/20260909-nondisruptive-update/windows-result.json), [실행로그](../artifacts/20260909-nondisruptive-update/windows.log), [재시도](../artifacts/20260909-nondisruptive-update/activation-retry.log).

## 실패한 선행 시험
- 첫시도: 테스트 bridge 요청의 Sec-Fetch-Site 누락→403. 두번째: 시험이 생산 bundled origin을 조회→URLError. 테스트격리설정을 수정했으며 둘다PASS로 세지 않는다.
- 세번째: 파일잠금이 Windows error5를 반환하여 허용된32/33 재시도를 비껴감. 제품재시도조건을5까지 수정하고 네번째실제설치시험전체PASS.

## 미검증 경계
- Environment: DQA-client
- Result: NOT-RUN
- Reason: 실제AI제공자를 통한 진행 중유료대화, 실제서비스로그인·AI위치선택복귀, 실제작업표시줄핀 클릭, tkinter/접근성 보조기술, 물리적으로분리된Windows세션2개 동시설치 및 사용자의설치취소 클릭은 이fixture시험에 포함되지 않는다. 단위·설치/윈도/쿠키시험을 해당항목PASS로 승격하지 않는다. 기존사용자앱을 종료하지 않는경계를 유지한다.

## 출하
- 공개대상은1.3.0만. 시험용1.3.1은 배포하지 않는다.
- PR1663병합2c5d6c66. 1.3.0공개(26,138,425bytes)·실제HTTPS다운로드SHA256 `72f7281575daf58afdf011f2e4d56ac11dde8317d820be7b6156594a22ab24d3` 빌드와일치. [채널](../artifacts/20260909-nondisruptive-update/channel.json).
- 웹노트반영:두replica2c5d6c66/ready/90초soakPASS,healthz200,자산stamp aaffca7a36d4. 웹배포를실제AI대화검증으로합산하지않는다.

## 실제 DQA에서 릴리스노트 렌더
- Environment: DQA-client
- Result: PASS
- 실제release-notes 데이터/렌더러와profile CSS를 격리WebView에서 실행하여1.3.0 제목과최초전환 직접설치 안내를 렌더했다. 같은시험에서 이전슬롯EXE→현재슬롯실행 및status1.3.1도확인했다. [결과](../artifacts/20260909-nondisruptive-update/notes-client.json).
- 픽셀/스크린리더 검증은 수행하지 않았으며 DOM통과를시각검토로표현하지 않는다.
