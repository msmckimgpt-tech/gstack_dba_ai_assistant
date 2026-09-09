---
run_at: 2026-09-09T12:34:00+09:00
session: codex:root:01a0841c-0298-7511-9088-828b547cd542
scope: TASK-20260909-session-continuity
verdict: PASS-installed-codex
---

# 대화별 AI 세션과 그룹 문맥 검증

## 최종 결과 — 설치 DQA 세션 재개 PASS

PR #1649·#1650 main 반영 및 보완 서버 **9cd10571** web-only 배포 완료(exit 0). web-a/b healthy, 재시작 0, 90초 soak PASS. 소스/두 서버 ai_tools SHA와 서버/설치 Windows 러너 SHA가 일치한다.

실행 중이던 설치 DQA 앱을 종료하지 않고 자동 갱신된 러너로 검증했다. 같은 합성 대화에서 첫 정상 결속 요청은 `resumed=false`, 후속 요청은 `resumed=true`; 둘 다 생성·제출 완료. **동일 상태 파일·동일 네이티브 ID, history_count 4→6**이다. 실제 UIAutomation 텍스트는 `DQA_SESSION_739_READY2` 뒤 `DQA_SESSION_739:HARBOR_914`와 정확히 일치한다. 후속 질문에는 문자열 값을 다시 주지 않았다.

첫 결속: 12:55:42~12:56:14(`t_RPL09xC1SMeqYQeH`), 재개: 12:57:25~12:58:01(`t_a2FCrBRBY2TVWMWQ`). 앱 PID29732/WebView2 PID38028/러너 PID49080. 상세는 [추적 가능한 합성 증거](evidence/20260909-session-continuity.json), wrapper `artifacts/session-continuity/{dqa-session-result,dqa-final-ui,deployed-hashes}.json`, `deploy-fix.log`를 따른다.

최종 관련 회귀 **87 passed**. 실제 Claude CLI 재개도 별도 2회 PASS다. **여러 계정이 실제 그룹 DQA에서 주고받는 왕복은 NOT-RUN**이며, 그룹 서버 함수·러너 프롬프트 회귀 PASS와 구분한다. 설치 앱에서 발견한 초기 누락 및 수정 전 RED는 아래에 보존한다.

## 최초 구현 직후 검증 기록(배포 전)

- worktree: `.worktrees/feature-0043-session-continuity`; branch: `ai/codex/feature-0043-session-continuity`; base `00981307`.
- 사용자 요청: DQA에서 시작한 대화의 AI 세션 재사용, 그룹의 여러 참여자가 호출한 assistant 기록 유지.
- 원문/자격증명 없이 합성 질문과 표식으로 실제 CLI를 검증했다. 실행 로그는 wrapper `artifacts/session-continuity/`에 있다.

| 검증 축 | 결과 | 증거 |
|---|---|---|
| 브리지 전체 + web bridge glossary/duration 회귀 | 1815 passed, 1 skipped, 37 warnings, 223.60초, exit 0 | `final-tests.log` |
| 마지막 빈 stdout 가드·선택 위치 소실 예외 처리 포함 집중 회귀 | 43 passed, 1.46초 | `focused-tests.log`, `tests/test_conversation_sessions.py` |
| 실제 Codex 2회 | 같은 native ID로 재개, 첫 요청 합성표식 회상 PASS | `live-cli.log` |
| 실제 Claude 2회 | 같은 native ID로 재개, 첫 요청 합성표식 회상 PASS | `live-claude.log` |
| 실제 없는 UUID 오류 | Claude/Codex exit 1, 빈 stdout, 요청 UUID의 세션 없음 stderr | `claude-missing.err`, `codex-missing.err` |
| 그룹 이력 | A/B 질문·assistant·반복 질문·생성 중 추가 메시지의 실제 다음 프롬프트 포함 PASS | 집중 회귀 |
| 결속 및 실패 | 계정/대화/서비스/위치/지침 격리, 프로세스 잠금, 취소/실패 폐기, 최종 assistant 편집/삭제, 제출 영수증 배선 PASS | 집중 회귀 |
| 패널 | backend/security/qa 확인된 차단 결함 없음 | REVIEW.md 및 reviews/20260909T123400-session-continuity-* |
| 설치 Windows DQA | NOT-RUN (배포 후 검증 예정) | 기존 실행 앱 PID 29732/path 확인, 앱 종료하지 않음 |
| 실제 두 계정 그룹 DQA 왕복 | NOT-RUN | 위 그룹 검증은 실제 서버 함수/러너 프롬프트를 실행한 회귀이며 설치 앱 왕복과 구분 |
| 배포 | 아직 미실행 | 최종 SHA·health·러너 산출물은 배포 후 별도 기록 |

브리지 전체 회귀 이후 마지막 두 보완은 집중 43건으로 재검증했다. 넓은 회귀 수치를 최종 두 보완까지 재실행한 결과로 표기하지 않는다. 생략 없는 무제한 대화 보존을 보장하지 않으며 서버 snapshot은 최근 80개/48,000자이다.

완료 게이트: `bash bin/verify-completion.sh --pre-commit feature-0043-external-llm-bridge` PASS. 최초 기록 형식 실패(CHG 접두·feature-0003의 DQA-client NOT-RUN/Reason)를 수정한 뒤 통과했다. `ruff`(신규 모듈·테스트), `node --check`(릴리즈 노트), `git diff --check`, ROUTEMAP 재생성·codenav-lint PASS. 설치 DQA NOT-RUN 기록을 코드 PASS와 구분한다.

최신 main `62afb45b` 통합 후 세션43 + 첨부 diff48 회귀: **91 passed, 19 warnings, 7.71초**, exit 0 (`integration-tests.log`). 양측 순증분 대조·codenav-lint·diff-check PASS.

## 최초 배포 및 설치 DQA에서 발견한 전달 누락

- PR #1649 main `834369bb` web-a/b ready·90초 soak PASS, 배포 exit 0. 서버/Windows 러너 SHA-256 `68340862901e6ac6779e609d5757e149707a8ba6897a69a435f9cf5aca7d7cc9` 일치. 기존 DQA 앱을 종료하지 않고 러너가 PID 50000→49080, 12:45:41 run.ready로 자동 복귀했다.
- 설치 DQA의 새 합성 대화에서 12:46:17 `t_Utejwb7GvekozkyH` Codex 실행→12:46:47 delivered=true. UIAutomation으로 `DQA_SESSION_739_READY` 실제 응답 확인. 데이터베이스/도구 호출 없는 합성 요청이다.
- **세션 저장은 FAIL**: 상태 디렉터리가 없었다. 실제 claim 응답에 `conversation_id`가 누락돼 러너의 결속 guard에서 건너뛰었다. 단위 테스트/CLI 성공으로 설치 앱의 세션 연속성을 주장할 수 없는 실제 반례다.
- `test_actual_claim_payload_reaches_runner_session_binding`을 추가해 실제 전체 응답을 실제 handler에 전달: 수정 전 binding=None RED(`claim-seam-red.log`). 인가된 conversation_id 필드 1줄 추가 후 신규44+기존배선43 = **87 passed, 2.69초**(`claim-seam-green.log`).
- 보완 서버 배포 후 상태 생성·두 번째 동일 native ID 재개를 다시 확인한다.
