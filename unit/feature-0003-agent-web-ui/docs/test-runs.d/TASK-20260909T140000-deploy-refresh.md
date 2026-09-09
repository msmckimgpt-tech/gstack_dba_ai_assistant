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
