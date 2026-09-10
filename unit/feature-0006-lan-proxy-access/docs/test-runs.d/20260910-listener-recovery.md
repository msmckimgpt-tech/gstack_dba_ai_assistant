# 공인 주소 portproxy 리스너 복구 — 2026-09-10

Related TASK: TASK-20260910-listener-recovery

## 원인과 코드 검증
Environment: CLI
Result: PASS
Scenario: Windows portproxy 설정과 실제 TCP 리스너 drift

기존 매핑은 112.185.196.20:80/443 → 172.26.154.233:80/443으로 맞았지만 Windows 실제 public 리스너가 없었다. localhost와 Windows→WSL 직접 연결은 정상이었다. 기존 스크립트는 매핑 일치만으로 unchanged로 보고, 최종 연결 검사 실패도 rc0으로 끝내 실제 누락을 복구하지 못했다.

매핑과 리스너를 함께 검사하고 활성 연결0인 누락 대상만 delete/add로 복구한다. postcheck 실패는 nonzero. RepairOnly는 조회 실패/대상 불일치/방화벽 및 legacy 변경을 무변경 거절한다. 기본 정기 WSL IP 변경 동기화 계약은 유지한다.

[Windows 비승격 mock](../artifacts/20260910-listener-recovery/mock-result.json): 6/6 PASS, 실제 네트워크 mutation0. 독립 QA/backend/security 최종 P1/P2 0. mock은 실제 운영 적용 증거와 구분한다.

## UAC 승인 적용
Environment: Windows-admin
Result: PASS
Scenario: 기존 공개 80/443만 복구하고 다른 서비스 유지

사용자가 Windows UAC 승인을 완료했다. [검토한 적용 스크립트](../artifacts/20260910-listener-recovery/apply-reviewed-portproxy.ps1)는 기존/신규 소스 SHA를 고정 검사하고 ProgramData 백업 후 새 sync를 배포했다. 기존 대상 매핑·WSL backend 정상 여부를 확인한 뒤 RepairOnly/SkipFirewall/SkipVerify와 빈 LegacyListenPorts로 실행했다. SkipVerify는 추가 HTTP 진단을 생략하지만 새 리스너 postcheck는 유지한다.

[실제 적용 결과](../artifacts/20260910-listener-recovery/apply-result.json): 80/443 각각 recovered. 다른 매핑과 6379/28080 리스너 동일. 방화벽 변경0, 서비스 재시작0. 정본/배포본 SHA256 `7b629d37f3f221f6f6864ff69be212295e4d785af48ec60add2cbafb6f945f86`. 기존 백업은 ProgramData의 `.backup-20260910-113237`.

## 실제 다운로드와 DQA 화면
Environment: DQA-client
Result: PASS
Scenario: 공인 주소의 실제 배포 클라이언트 진입

Windows에서 rootCA TLS 검증한 public/localhost 다운로드 모두1.3.1,25,945,487bytes, SHA256 `1e4d7fa471ff7825d67e30f7a127d90b39218d1986e27ab2ded5f4b9121b9a4e` 일치. 기본 공인 주소 실제 DQA 로그인 로고·작업 표시줄과 정상 종료까지 확인했다. [다운로드](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/channel-windows-restored.json), [화면](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public-login.png), [실행](../../../feature-0046-native-client/docs/artifacts/20260910-transparent-icon/live-public.json).

예약 작업의 다음 실행 결과를 별도 재조회한 것은 아니다. 기존 10:01 rc0/매핑 종결 기록은 리스너 건강성을 입증하지 못하며 이번 실제 접근 검증으로 보완한다. 실제 사용자 계정 로그인/유료 AI 대화는 실행하지 않았다.
