---
run_at: 2026-09-10T18:00:00+09:00
session: codex-01a08a78-ca71-7471-bfa5-29a728af229b
scope: [cli-failure, attachment-write, direct-response]
verdict: pass-with-deploy-pending
---

# TASK-20260910-screenshot-failures

- 설치 DQA1.5.0 로그17:37:48/17:39:13: stdout weekly limit/reset Sep13 3pm Asia/Seoul, stderr permission wildcard warning. core9307/9309에는 경고만 남았다. 기존 코드 신규5사례 중4 FAIL로 재현했다.
- 첨부 원문은 설치 Codex native session01a08a6a의 최종답변에서 확보:13 edit/22530bytes. DB core9305 failure8, 표시 message2719에 저장된5개 SHA256·크기·source 일치. 진단은 DQA metadata 읽기만, SQL 첨부 실행 없음. 원문은 artifacts의0600 비공개 파일이며 Git 미포함.
- 전체 bridge 및 첨부 관련:1889 passed/1 skipped/0 failures/0 errors,159.376초. 최종 secret/시도횟수/중복사유 변경은 집중 재검증으로 추가 기록한다.
- QA 실제 Python 자식 프로세스 plain/Claude JSON/Codex JSON 경로3개, 실패 누적 health/fastfail PASS. direct 응답 tail의 실제 코드+helper+fake 저장소4모드(성공·실패·worker 완료·self-heal) PASS. HTTP 전체/실제 AI와 구분한다.
- security: nonexistent source1000개→DB조회32, 등록 synthetic secret→answer/health/fastfail 원문노출0. source·업로드권한·파일종류·확장자·용량 가드 유지 확인.
- 공식 참고: https://github.com/anthropics/claude-code/issues/90879 (startup warning), https://code.claude.com/docs/en/cli-usage (settings scope). 실제 원인은 설치 로그로 확정했다.

Environment: DQA-client
Result: NOT-RUN
Scenario: 수정 배포 후 AI 오류 안내 및 누락 첨부 복구 화면
Reason: 배포 전. 설치본 로그/원본 대화와 서버 메타데이터를 대조했다.
Alternative: 실제 subprocess·공통 저장 후처리·회귀 테스트.
Next: 배포 후 runner 자동갱신·원래 답변 첨부 및 한도 안내 확인.

- 최종 집중 회귀: 72 tests / failures=0 / errors=0. 후속 message_id0 정상/실패 두 사례 및 첨부 공통 suite PASS. ruff/diff-check PASS.
