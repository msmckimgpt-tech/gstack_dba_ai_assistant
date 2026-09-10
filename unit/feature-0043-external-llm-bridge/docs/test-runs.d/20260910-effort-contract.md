---
run_at: 2026-09-10T13:40:00+09:00
session: codex-effort-contract-20260910
scope: [runtime-options, capability-cache, degraded-answer]
verdict: partial
---

# TASK-20260910-effort-contract 검증

- 라이브 진단: 지정 대화 `20260910042529-bdc424bf`, 사용자 9282 → assistant 9283 옵션 오류. PostgreSQL core_messages가 현재 정본임을 live env와 loader 코드로 확인. 최근 14일 256 메시지/61 대화, 동일 signature 1건/1대화. 내용·계정 원문은 전재하지 않았다.
- 최소권한: agent_kb_ro 사용. PgBouncer RO 접속은 config error로 실패하여 같은 읽기전용 계정으로 postgres 직접 접속 성공. 진단 SELECT만 사용했으며 쓰기 없음.
- 설치 증거: DQAConnect 1.4.0-1 실행, Windows Claude 2.1.70 도움말의 `--effort <level>` 및 low/medium/high 실측. 해당 runner 캐시는 verified `--reasoning-effort`; task.dispatch runtime=claude/effort=high 이후 exit=1 unknown option.
- RED: 이전 main b7aa2ac0의 모듈을 /tmp 격리 번들로 빌드해 초기 신규 11 테스트 적용: 9 failed, 2 passed. 캐시/실행/협상/실패 고지/구버전 추정이 모두 실패했다.
- GREEN: 신규15 + model selector + CLI failure + caps live sync 226 passed (3.00s). 처음 직접 실행은 oauth_store import 경로 4건 오류; Makefile과 동일한 PYTHONPATH로 해결했다. 신규 mock의 api.call 계약 오류도 수정했다.
- ruff 및 diff-check PASS. 넓은 기능 회귀와 실제 Windows CLI 호출은 별도 결과 추가.

Environment: DQA-client
Result: NOT-RUN
Scenario: 설치 DQA에서 동일 오류 입력 재요청 후 답변 도달
Reason: 배포 전. 원래 사용자 대화는 진단 읽기 전용으로 유지하며 자동 재전송하지 않았다.
Alternative: 실제 선택된 Windows CLI 도움말·설치 캐시·로그와 정본 호출 코드를 대조했다.
Next: 배포 후 설치 runner 갱신과 가능한 실제 경로 실측.

## 실제 Windows CLI 검증

Environment: Windows-CLI
Result: PASS
Scenario: 설치 DQA의 오염 캐시를 읽어 정본 build_cmd로 실제 Claude 실행
Evidence: Windows Claude 2.1.70, 원 캐시 --reasoning-effort/high → argv --effort high; 모델 opus. 도구·스킬·세션 저장을 끄고 무해한 확인 프롬프트를 실행하여 exit 0 / DQA_EFFORT_OK / stderr empty 확인. 원 캐시 수정 0회, DB 질의 0회. 설치 앱 UI 재요청 E2E와는 구분한다.

## 넓은 회귀

- feature 전체 1795 passed/1 skipped/1 failed. 실패 1건은 기존 구조 테스트가 예전 if문 문자열을 고정한 것이며 새 행위 테스트의 실패/빈답 제출은 PASS. 검사 진입점을 새 조건명에 맞추고 해당 모듈 재검증한다.

- 구조 검사 정합 후 해당 모듈+신규 테스트 **36 PASS**(2.63s). 전체 실행의 유일 실패 해소, 나머지 1795 PASS/1 skipped 결과 유지. `verify-completion --pre-commit feature-0043-external-llm-bridge` PASS.
- 공식 CLI 계약 대조: https://code.claude.com/docs/en/cli-usage (`--effort`); 설치 Windows 도움말을 최종 실행 근거로 사용했다.
