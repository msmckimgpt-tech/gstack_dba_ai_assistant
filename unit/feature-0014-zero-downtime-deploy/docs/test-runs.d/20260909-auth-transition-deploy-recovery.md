# TASK-20260909-auth-transition-deploy-recovery

첫 `deploy-web --web-only`는 Caddy exec의 `procReady not received`로 web 교체 전 exit 1 중단했다. 두 web은 기존 048c844a healthy를 유지했다.

- Caddy PID 3619937, threads 24 + zombie ssl_client 99, pids.current 123/max 128, pids.events max 180. 독립 reviewer도 같은 값을 확인했다.
- `docker update --pids-limit 256 repo-caddy-1` 후 `docker exec ... true` 정상. PID/네트워크/공개 포트는 유지했다.
- 원인 제거: Caddy 내부 BusyBox HTTPS wget 대신 host nsenter/dig/curl. DNS·공유 IP·실제 CA·Host/SNI·정확한 200을 요구하고 오류는 실패로 처리한다.
- 참고: Docker init은 PID1 자식 회수를 담당한다([공식 문서](https://docs.docker.com/reference/compose-file/services/#init)). Compose init:true는 이후 재생성에 적용되는 방어이며 현재 PID1은 계속 Caddy다. 남은 기존 zombie 99개를 제거했다고 주장하지 않는다.
- 로컬 관련 pytest 49 passed in 47.34s. 최초 2건은 새 curl 옵션에 대한 timeout 정규식 오탐 및 지속 ps 실패의 안전 중단 기대값으로 수정했다.
- 실제 생산 함수 정상 HTTPS probe 5회 PASS, 잘못된 SNI 1회 거부. 전후 zombie 99 유지, Caddy PID 유지. 로그 `artifacts/auth-transition/live-edge-probe.log`.
- security 정적 재검토 PASS. backend/qa는 관련 15건을 독립 실행하고 전체 49 PASS 로그·실제 probe와 PID/zombie를 확인하여 최종 PASS. 셸 구문·diff 검사 PASS.

배포 재개와 설치 DQA 수용 결과는 feature-0003의 `20260909-auth-transition.md`를 정본으로 기록한다.

## 배포 복구 완료

PR #1656/cf55c659 main 반영 후 canonical web-only 배포 exit 0, 두 replica ready·엣지 복귀·90초 soak PASS, UI 완료 신호 게시. Caddy PID 3619937·zombie 99 유지 및 PID 한도 256 확인. init은 실행 중 미적용 상태로 명시한다. 설치 DQA 3회 왕복의 70개 관측 중 로그인 노출 0으로 원래 사용자 요청도 수용했다.
