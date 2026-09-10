---
run_at: 2026-09-10T13:40:00+09:00
session: codex-effort-contract-20260910
scope: [runtime-options, capability-cache, degraded-answer]
verdict: pass-with-live-limit
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

## 배포 및 설치 DQA 자동 복구 — 2026-09-10 13:49 KST

- PR #1675 main merge `9ecd324eaae89f094f0b4939c9668be74f3cf13d`, 구현 commit `50947e26`. 기존 배포 잠금 해제 후 `make deploy-web-only` exit0. web-a/web-b 9ecd324e healthy, Caddy 후보 복귀 및90초 soak PASS, KEK 존재 확인(값 비노출). 기존 snap-docker metadata-file race는 스파인이 이미지 commit 정합을 검증해 처리. 워커/MCP 미변경·대화 스모크 NOT-RUN.
- 공개 /healthz HTTP200 git_commit=9ecd324e. 공개 runner /static/agent/bridge_agent.py HTTP200, SHA-256 `371cac83d087e308588d420ca52f156c8cc484c30c1697f267cf9c83b609c42d`. 빌드 산출물 및 설치 DQA의 bundle SHA-256과 전체 일치.

Environment: DQA-client
Result: PASS
Scenario: 실행 중 설치 DQA의 러너 자동 갱신·오염 캐시 보정·연결 복귀
Build: DQAConnect 1.4.0-1 / server 9ecd324e / runner 371cac83d087
Evidence: 원 개별 runner가 13:48:01 run.selfupdate(old 68340862901e → new 371cac83d087), PID44656 종료 후 PID26088 시작, 13:48:03 run.ready(runtime=claude), 13:49:18 bridge_heartbeat api.ok. 같은 개별 config.json의 effort가 --reasoning-effort에서 --effort로 자동 보정됨. 앱/캐시를 작업자가 재시작·삭제·편집하지 않았다.

Environment: DQA-client
Result: NOT-RUN
Scenario: 설치 DQA에서 동일 오류 입력 재요청 후 답변 도달
Reason: 원 사용자 대화는 감사 읽기 전용으로 유지했다. CLI 실응답과 설치 자동복구까지 검증했고 원 쿼리는 자동 재전송하지 않았다.
Alternative: 같은 PC의 설치 CLI에 원 오염 캐시로 생성한 명령을 실행하여 exit0/DQA_EFFORT_OK, 오류 없는 응답 확인.
- 회귀 시계열: 갱신 이후 assistant 0건/동일 signature 0건으로 모집단이 없어 마찰 소멸 통계 판정은 inconclusive. 원장 상태 fixed:deployed:unverified-live 유지.
