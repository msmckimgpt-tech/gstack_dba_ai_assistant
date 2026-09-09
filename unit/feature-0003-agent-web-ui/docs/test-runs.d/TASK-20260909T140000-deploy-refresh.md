---
run_at: 2026-09-09T14:00:00+09:00
session: codex:root:01a08411-5b5d-7691-890c-509a2b60ed6d
scope: TASK-20260909T140000-deploy-refresh
verdict: PARTIAL
---

# 배포 완료 자동 반영 검증

Environment: CLI
Result: PASS
Scenario: 완료 API·실제 배포 셸 failure/rollback/mixed/idempotency·상태 보호·복원
Evidence: wrapper `artifacts/dqa-deploy-refresh-20260909/logs/`. 독립85 PASS, route golden/UI wrapper 포함 집중87 PASS. 기존 diff/static-cache Python104 PASS, Node diff128 PASS, watcher9 시나리오 PASS. Python ruff·ES module syntax·bash -n PASS.

Environment: DQA-client
Result: PASS
Build: 격리 제품 Shell/WebView2 152.0.4191.66, 제품21파일 SHA256 일치
Scenario: 실제 자동 재로드7회, draft/new-file/타대화busy/IME/pointer 보류 해소 후 자동 적용, 선택·diff 위치 복원, offline/중복/구generation
Evidence: `/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-deploy-refresh-20260909/native/final/result.json` — 34/34. 같은 폴더 before-reload.png/after-reload.png/draft-deferred.png/final.png/fingerprints.json.
Boundary: watcher/adapter/diff는 제품 모듈이며 composer 선택 복원은 제품 함수다. 서비스/API·전체 app.js 초기화·알림 함수는 fixture다. 설치 사용자 앱/물리 IME PASS로 확장하지 않는다.

Environment: DQA-client
Result: NOT-RUN
Scenario: 설치본 최초 bootstrap 및 후속 배포 자동 적용
Reason: 서버 배포 전. 기존 앱은 읽기 전용 UIA 확인만 수행했으며 종료/재설치/사용자 메시지 전송 없음.

## 전체 회귀/서버 배포
전체 pytest: **8,513 passed / 13 failed / 40 skipped**, 508.47초. 실패는 호스트 psycopg 부재6건과 컨테이너 전용 web.app import7건으로, 최신 소스293파일 지문을 확인하고 네트워크 차단·읽기 전용 root·임시 /shared의 격리 제품 컨테이너에서 해당 파일 **45 PASS**로 재검증했다. 근거: wrapper `artifacts/deploy-refresh-20260909/qa-container/{tests.log,result.xml,source-manifest.json,command.json,exit-code.txt}`. 첫 배포는 아래에 기록한다. 전체 PASS로 표기하지 않는다.


## 배포 1 — 최초 도입

- PR #1653 main `7fa75a51`, `bin/deploy-web.sh --web-only` exit0. 두 web replica ready·edge 복귀·90초soak PASS. 대화 smoke/worker/MCP 롤아웃은 scope=web 계약으로 미수행이다.
- 두 replica와 CA 검증 edge의 `/api/ui-release`가 동일 `complete` revision7fa75a51/stamp311b2ded3afc/generation1788930763270 및 no-store를 반환했다.
- 현재 제품7파일의 SHA256이 배포본과 일치(빌드 stamp 문자열만 정규화). manifest는 배포 중 pending을 유지했고 검증 종료 뒤 complete로 바뀌었다.
- 근거: wrapper `artifacts/dqa-deploy-refresh-20260909/{deployed-7fa75a51.json,release-events.jsonl,logs/dqa-refresh-deploy1.log}`.
- 설치 DQA는 PID29732/정확한 설치경로로 고정했다. 읽기 전용 UIA에서 기본 '대화를 선택하세요', 활성 대화0, 빈 prompt, 진행/업로드/열린 modal 신호0을 확인했다. 구페이지는 감지 코드가 없어 최초 한 번 지원 IPC로 동일 제품페이지를 로드하는 bootstrap이 필요하다. 실제 조작과 후속 자동갱신 결과는 이어 기록한다.


## 감지기 수명주기 후속

설치 검증 준비 중 구 watcher stop 뒤 지연 응답 재로드를 별도 probe로 재현했다. 사용자 데이터 손실은 재현0이지만 폐기한 감지기는 동작하지 않아야 하므로 isActive 경계를 추가했다. Node **10 시나리오 PASS**(기존9에 stop/재설치 회귀 추가), pytest wrapper1 PASS. 수정 전2b5a49f7에서는 동일 회귀가 FAIL, 수정 후 실제 initializeWorkspace 연결5 probe 모두 구응답 reload0/resume저장0이다. 기존 전체8513/집중87/native34 결과는 이 후속 전 버전이며 후속의 집중 검증을 구분한다.


Environment: DQA-client
Result: NOT-RUN
Scenario: 수명주기 보완 후 최신 제품 Shell 재실행 및 설치 DQA 자동 갱신
Reason: 보완 전 격리34 PASS와 구분하여 최신 모듈로 재실행 중이다. 설치본 최초 IPC 시도는 exit2이며 URL/문서 RuntimeId 변화가 없어 최초 코드 로드를 확인하지 못했다. 다른 창이 전면일 때 키를 보내지 않았다. 코드 회귀10 PASS를 실제 설치본 PASS로 합산하지 않는다.

수명주기 커밋의 최초 완료 게이트는 이번 diff의 DQA-client 실행/미수행 블록 누락으로 FAIL했다. 실행 결과를 확인하기 전에 커밋한 절차 오류를 기록하고, 위 실행 경계를 추가하여 머지 전 다시 검증한다.


## 최종 클라이언트 검증 경계

Environment: DQA-client
Result: PASS
Build: 수명주기 보완을 포함한 현재 제품21파일 지문 일치, 실제 격리 Shell/WebView2 152.0.4191.66
Scenario: 자동 재로드7회·초안/첨부/IME/드래그/타대화 작업 보호·선택/diff/메시지 위치 복원
Evidence: wrapper `artifacts/dqa-deploy-refresh-20260909/native/final-current/result.json` **34/34 PASS**, 같은 경로 before-reload.png/after-reload.png/fingerprints.json. 격리 fixture PID49812 종료 확인.
Boundary: fixture API·전체 계정 초기화·알림 함수 및 물리 IME 한계는 앞선 native 검증과 같다.

Environment: DQA-client
Result: NOT-RUN
Build: 실제 설치 DQA PID29732 / HWND4988646 / WebView PID38028
Scenario: 최초 감지 코드 로드와 실제 후속 배포 자동 적용
Reason: 설치 실행 파일의 --path /static/index.html 호출 exit2·문서 RuntimeId/URL 변화0. 이는 실행 실패 사실이며 도움말의 옵션 비노출만으로 미지원 원인을 확정하지 않는다. UIA SetFocus도 실패했고, 마지막 SetForegroundWindow는 false/다른 PID가 foreground여서 F5를 보내지 않았다(실제 키전송0). 서버 측 browser /api/ui-release 요청도 관측0이라 실제 감지 코드 로드/자동 적용 PASS로 판정할 수 없다.
Evidence: wrapper `artifacts/dqa-deploy-refresh-20260909/installed/{bootstrap-attempt-summary.json,bootstrap-f5-final.json,safety-summary.json}` 및 문서 RuntimeId 읽기 기록. 설치 앱 종료·재설치·AI 메시지 전송 없음. 검증용 읽기 모니터 종료 확인.
Next: 최초 한 번 새 코드로 대화 화면이 로드된 이후에는 설치된 watcher가 후속 배포 완료를 자동 감지한다. 이번 세션에서는 설치본의 최초 로드를 확인하지 못했다.


## 배포 2의 완료 신호 보류와 원인 복구

보완본048c844a의 두 web은 ready였지만 Caddyfile 조회 exec가 exit128을 반환하여 배포가중단됐다. soak/complete는실행되지않아manifest는pending을유지했다. 빌드의snap-Docker metadata-file 오류는이미지revision검증을통과한기존복구분기로진행됐으며이중단의원인은아니다.

Caddy의 ssl_client 좀비99개 + live threads24 = pids.current123/max128, kernel fork rejected와OOM0을확인했다. 개별과거wget과의인과는소급확정하지않되생성패턴과배포TLSprobe가일치한다. bin/lib/caddy-probe.sh로자식실행을별도init컨테이너에격리하고파일조회는Dockerarchive로대체했다. 조회실패를미기동으로오인하는reconcile분기와name충돌시기존컨테이너를지울수있던초안cleanup도독립회귀로적발·수정했다.

동시작업중현재Caddy의PID한도가256으로바뀐것을관측했다. 이세션은아직runtimeupdate를실행하지않았고중복변경하지않았다. PID3619937/시작시각2026-09-07T08:58:22.130694633Z/좀비99는그대로다. 한도확대는기존잔류분의여유이며근본재발방지는probe격리와다음생성init계약이다. 현재Caddy재시작/재생성은하지않았다.


Environment: CLI
Result: PASS
Scenario: Caddy 점검 격리와 재생성/cleanup 실패 경계
Evidence: 신규18 + 기존edge39 = **57 PASS**, `artifacts/dqa-deploy-refresh-20260909/logs/dqa-caddy-final-tests.log`.

Environment: Server
Result: PASS
Scenario: 현재 프록시 무재시작·실제 Docker archive/admin GET/TLS /livez 반복
Evidence: `artifacts/dqa-deploy-refresh-20260909/caddy-probe-live.json`. TLS GET9회 성공, Caddy PID/시작시각 동일, 좀비99→99, 잔류 probe0. 최종 CID 기반 cleanup도 실제 실행했다. 기존좀비가제거됐다는뜻은아니며 추가누적이없음을확인했다.


## 동시 작업 통합

PR #1652/#1656의 인증 초기화와 Caddy 복구를 통합했다. PID 한도256 변경은 해당 작업의 `20260909-auth-transition-deploy-recovery.md`에 실행 사실이 기록돼 있어 주체가 확인됐다. 이 세션에서는 중복 runtime 변경을 하지 않았다.

최종 replica TLS probe는 먼저 착륙한 PR #1656의 host nsenter/dig/curl DNS·CA·SNI 검증을 보존한다. 본 작업은 Docker archive 파일 읽기, admin HTTP의 격리 init probe, 조회 실패 시 무재생성과 자기 CID cleanup을 더한다. 앞선 TLS sidecar9회 실측은 진단/초안 증거이며 최종 TLS probe의 증거로 대체하지 않는다.


통합 회귀: 배포/edge67 PASS, watcher Node10 PASS, 인증 Node44 PASS. 기존 전체 실행을 반복한 것은 아니며 변경 접합부만 재검증했다. 로그는 artifacts/dqa-deploy-refresh-20260909/logs/dqa-caddy-merged-tests.log 및 dqa-refresh-integrated-{watcher,auth}.log.

동시 세션이 PR #1656/cf55c659 배포와 실제 설치 DQA 관리 화면 왕복3회를 완료했다. `artifacts/auth-transition/installed-fixed.json`은 Installed=true/AppPid29732/Ready3회를 기록한다. 서버에서도 browser /api/ui-release 요청이 관측되어 최초 코드 로드 경계가 바뀌었다. 이는 해당 세션의 기여이며, 본 세션은 추가 설치 앱 조작 없이 후속 배포의 자동 적용을 읽기 전용으로 관측한다.
