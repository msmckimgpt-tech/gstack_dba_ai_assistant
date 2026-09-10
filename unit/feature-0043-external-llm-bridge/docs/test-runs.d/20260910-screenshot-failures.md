---
run_at: 2026-09-10T18:00:00+09:00
session: codex-01a08a78-ca71-7471-bfa5-29a728af229b
scope: [cli-failure, attachment-write, direct-response]
verdict: pass-with-live-quota-branch-not-reproduced
---

# TASK-20260910-screenshot-failures

- 설치 DQA1.5.0 로그17:37:48/17:39:13: stdout weekly limit/reset Sep13 3pm Asia/Seoul, stderr permission wildcard warning. core9307/9309에는 경고만 남았다. 기존 코드 신규5사례 중4 FAIL로 재현했다.
- 첨부 원문은 설치 Codex native session01a08a6a의 최종답변에서 확보:13 edit/22530bytes. DB core9305 failure8, 표시 message2719에 저장된5개 SHA256·크기·source 일치. 진단은 DQA metadata 읽기만, SQL 첨부 실행 없음. 원문은 artifacts의0600 비공개 파일이며 Git 미포함.
- 전체 bridge 및 첨부 관련:1889 passed/1 skipped/0 failures/0 errors,159.376초. 최종 secret/시도횟수/중복사유 변경은 집중 재검증으로 추가 기록한다.
- QA 실제 Python 자식 프로세스 plain/Claude JSON/Codex JSON 경로3개, 실패 누적 health/fastfail PASS. direct 응답 tail의 실제 코드+helper+fake 저장소4모드(성공·실패·worker 완료·self-heal) PASS. HTTP 전체/실제 AI와 구분한다.
- security: nonexistent source1000개→DB조회32, 등록 synthetic secret→answer/health/fastfail 원문노출0. source·업로드권한·파일종류·확장자·용량 가드 유지 확인.
- 공식 참고: https://github.com/anthropics/claude-code/issues/90879 (startup warning), https://code.claude.com/docs/en/cli-usage (settings scope). 실제 원인은 설치 로그로 확정했다.

## 출하·원 답변 복구

- 제품 PR #1683:47d62ef2, merge a4da65b5. 병행 문서 main bb1cccbd로 fast-forward 후 `make deploy-web` scope=all exit0. 최초 a4da65b5 배포는 origin/main 선행을 감지해 교체 전 중단했으며 최신 main에서 다시 실행했다.
- 웹2·워커3·MCP2 모두 bb1cccbd/healthy/RestartCount0, 웹90초 soak PASS. ask-worker surge 정리, gateway 드리프트 없음. Caddy18:03–18:11 KST JSON error0,HTTP200 721건/404 1건. 관측 창의 결과이며 전체 요청 무손실을 추정하지 않는다.
- 배포 스모크는 서버 LLM 차단 확인 PASS다. 실제 AI 왕복은 아래 설치 앱 요청으로 별도 확인했다.
- 설치 runner18:05:03 selfupdate→18:05:04 새 PID32032/build bca92fb72419→18:05:05 ready. 설치 bundle와 두 web replica SHA256 `bca92fb72419025533861fae8b65db74d68b2d32b45f7e99c757cd70838a09e3` 일치.
- 복구 전 preview: 원본13개/22530bytes, 기존5개/누락8개, 기존 객체 해시 일치. account10·대화20260910052500-b5d49926·display2719/core9305를 고정하고 원본 source 소유권/삭제 상태를 검증했다.
- 보안 리뷰의 두 보완 반영: 정확한 실패 고지 전문·말미 및 display/core 본문 동일성 확인 후 고정 길이 제거, DB GET_LOCK으로 단일 실행 강제. 권한0600 원문·본문 백업, 기존 가드로 누락분만 저장하고 CAS로 해당 두 메시지의 실패 고지만 제거했다. SQL 파일 본문 실행 없음.
- 복구8개 신규 ID1397–1404, 전체13개 실제 객체 크기·SHA256 일치, 기존1392–1396 불변. 복구 후 read-only preview existing13/missing0. 과거 오류 안내9307/9309 및 이후 사용자 대화는 변경하지 않았다.

Environment: DQA-client
Result: PASS
Scenario: 원래 답변의 누락 첨부 복구 표시
Build: DQA Connect1.5.0-1/PID34472, server bb1cccbd
Evidence: 설치 exe의 HWND PrintWindow 이미지 `artifacts/screenshot-failures-20260910/installed-attachments-restored.png`: 원 답변 첨부13개, 기존 실패 경고 없음. 객체 해시 검증은 별도 `recovery-result.json`.

Environment: DQA-client
Result: PASS
Scenario: 배포 후 Claude 합성 요청 왕복
Build: 동일 설치 앱·서버/runner
Evidence: UIA로 새 대화·빈 draft 확인 후 도구/DB/파일 조회 없이 짧은 표식만 요청. task t_XZfO3h4BfHeNukqv/대화20260910091952-0c4843e3,18:19:57 claude/opus/medium dispatch→18:20:31 delivered=true/33689ms. 실제 앱에 DQA_SCREENSHOT_910_OK 표시,대기 상태 복귀. `installed-live-request-events.json`, `installed-live-quota-response.json`. 검증 뒤 원 대화로 복귀했다.

Environment: installed-bundle-fixture
Result: PASS
Scenario: 당시 주간 한도 stdout와 반복 permission warning stderr 재생
Evidence: 설치된 bundle 파일을 WSL에서 import한 실제 describe_cli_failure로 당시 두 채널을 재생. weekly limit·Sep13 3pm Asia/Seoul·DQA 대안 안내 보존,permission warning 제외. `installed-failure-fixture.json`.
Limit: 새 라이브 요청은 정상 성공하여 한도 오류 화면은 재현되지 않았다. fixture PASS를 라이브 한도 오류 화면 PASS로 간주하지 않는다. Claude 한도/설정 자체를 변경하지 않았다.

- 최종 집중 회귀: 72 tests / failures=0 / errors=0. 후속 message_id0 정상/실패 두 사례 및 첨부 공통 suite PASS. ruff/diff-check PASS.
