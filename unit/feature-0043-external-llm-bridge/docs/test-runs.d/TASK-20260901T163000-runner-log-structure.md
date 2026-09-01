---
doc_type: TEST_RUN
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260901T163000-runner-log-structure
status: recorded
edit_policy: append-only
---

# Run — 러너 로그 구조화 (PRE-DEPLOY)

## Run 2026-09-01 16:1x KST — 단위·계약

- Environment: WSL Ubuntu · python3.12 · worktree `ai/claude/feature-0043-runner-log-structure`
- 명령: `python3 -m pytest unit/feature-0043-external-llm-bridge/tests/`
- 결과: **1045 passed, 1 skipped** · `ruff check` clean · `bash -n bridge_setup.sh` ok
  - 제외 2건과 사유(둘 다 **이 변경과 무관**하며 stash 한 baseline 에서도 같음):
    - `test_console_job_scope.py` — `ModuleNotFoundError: oauth_store` (로컬 실행 환경의
      PYTHONPATH 문제. 컨테이너 `make test` 경로에서만 수집된다)
    - `test_llm_gate.py` 3건 — **전체 스위트 동시 실행에서만** 실패한다. `git stash` 로
      내 변경을 걷어낸 baseline 에서 동일 재현 확인(= pre-existing, 테스트 간 상태 오염)
- 신규 계약 18건 (`test_bridge_log_structure.py`) 전건 PASS — 두 sink · 상관관계 키 ·
  UTC 오프셋 · 순번 단조 · 예외 형/스택 · 종료 요약 · 요약 빗장 · 토큰 마스킹 2종 ·
  본문 미기록 · 하위호환 · **이중기록 방지(실 서브프로세스)** · Windows 경로 · 끄기 ·
  회전 · 권한 0600 · 사건 코드 상수 · task 키 공유
- 기존 3건 정합 수정(변경 사유는 각 테스트 주석에 기록):
  `test_bridge_agent_sync`(stdlib 허용목록 `traceback`) ·
  `test_wsl_scheme_handler::test_l16_logs_carry_a_timestamp`(정규식 오려-exec → 모듈 실행) ·
  `test_bridge_interrupt_stream`(`"WARN"` 글자 → 심각도 성질 + 사건 코드)

## Run 2026-09-01 16:1x KST — 실동작 (수동 구동)

두 sink 를 실제로 만들어 눈으로 확인했다(테스트가 단정하는 것과 사람이 읽는 모양은 다른 축).

```
[bridge 2026-09-01 16:02:05+0900] INFO  task.dispatch task=t-1 runtime=claude model=opus dur_ms=12 | 내 AI 에게 전달
[bridge 2026-09-01 16:02:05+0900] WARN  api.fail http=401 | 토큰이 *** 로 들어간 본문
[bridge 2026-09-01 16:02:05+0900] ERROR ai.fail task=t-1 exit=2 err=division by zero err_type=ZeroDivisionError | AI 가 오류로 끝났다
[bridge 2026-09-01 16:02:05+0900] INFO  run.stop errors=1 failed=1 reason=test submitted=0 uptime_sec=0 | 브리지 러너 종료
```
원장(`bridge.events.jsonl`) 같은 사건:
`{"ts":"2026-09-01T16:02:05.181+0900","lvl":"ERROR","ev":"ai.fail","seq":4,"run":"deadbeef1234","pid":…,"task":"t-1","exit":2,"err_type":"ZeroDivisionError","err":"division by zero","tb":"…","msg":"AI 가 오류로 끝났다"}`

- 등록 토큰(`mat_supersecrettoken123`)이 **두 sink 어디에도** 남지 않음 — 확인.
- 종료 요약이 사건별 집계표를 그대로 실음 — 확인.

## Run 2026-09-01 16:1x KST — 시각검증 (Environment: Windows-browser, PB-0008)

`visual_verification_scope: always` 대상이다 — 변경 파일 중
`unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py` 가 `*/src/static/*` 에
거주하기 때문. 다만 **이 파일은 렌더되는 자산이 아니라 사용자가 내려받아 자기 머신에서
실행하는 파이썬 스크립트**다. 그래서 「화면이 어떻게 보이나」 대신 **그 파일이 실제로
배달되는가**를 실 Windows 브라우저에서 확인했다(그것이 이 변경의 사용자 도달 경로다).

- 도구: `bin/win-browser.py eval` (Chrome, `https://localhost` — 실 Windows)
- 프로브: `fetch('/static/agent/bridge_agent.py')` → SHA-256 앞 12자 + 바이트 수
- **PRE-DEPLOY 실측**: `served_build = 0a4ba732366c` · 214,898 bytes (배포 중인 구 러너)
- 이번 변경의 새 지문: `e955730dcc26` (main 병합 시 재계산)
- **화면 렌더 변경 0** — 대화창·연결 모달·선택기 어느 것도 건드리지 않았다(변경 파일 목록에
  `.html`·`.css`·렌더용 `.js` 없음). 그래서 시각 회귀 캡처 비교는 수행하지 않았고,
  수행하지 않은 사실을 여기 남긴다(카고컬트 방지 — AGENTS.md §15.4.1).

### POST-DEPLOY 로 이월한 것 (이 cycle 안에서 닫는다)

1. 배포 후 `served_build` 가 새 지문으로 바뀌는가 — 바뀌지 않으면 모든 러너가 「내 AI
   업데이트 필요」로 굳는다(2026-08-31 에 실제로 겪은 형태의 결함).
2. 새 러너를 실제로 띄워 `run.start` → `run.ready` → `hb.*` 가 원장에 남는가.
   ⚠ 이건 **러너를 띄운 본인만** 할 수 있는 확인이 아니라 AI 가 직접 수행한다(라이브 검증은
   AI 책임 — 사용자 정정 2026-08-26).
