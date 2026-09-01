---
run_at: 2026-09-01T16:40:00+09:00
session: ai/claude/feature-0043-connect-os-default
scope: 연결 화면 1단계 기본 OS 탭 — 계약 테스트 + 회귀
verdict: PASS
---

# Run — TASK-20260901T160000-connect-os-default (PRE-DEPLOY)

## 1. 단위·계약 테스트

- Environment: container (`mysql-ai-agent:afcd1a42`, worktree bind-mount,
  `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH` 는 `Makefile test` 와 동일 3경로)
- 명령:
  `python -m pytest -q -p no:warnings unit/feature-0041-external-ai-tool-surface/tests
   unit/feature-0043-external-llm-bridge/tests unit/feature-0003-agent-web-ui/tests`
- 결과: **ALL PASS** (실패·에러 0). 신규 `test_connect_os_default.py` **39건** 포함,
  러너 배포본 동기 검사(`test_bridge_agent_sync.py`) 포함.
- `ruff check unit/feature-0003-agent-web-ui/src unit/feature-0043-external-llm-bridge/{src,tests}`
  → `All checks passed!`

무엇을 실제로 가르는가 (vacuous pass 아님):

- 「모른다」로는 UPDATE 가 **한 건도 나가지 않는다**를 실행으로 확인한다(`_Cur.executed == []`).
  구 러너의 하트비트가 기존 값을 지우는 회귀는 이 단언이 잡는다.
- 읽기 SQL 에 `LastHeartbeatAt` 이 **없음**을 단언한다 — 신선도 술어를 얹는 회귀(=연결이 끊긴
  뒤 항상 빈 값)를 문자열이 아니라 질의 본문으로 잡는다.
- 정규화 표의 이름을 `compose_launch_commands` 본문과 대조한다 — 두 어휘가 갈리면 화면이 빈
  명령을 그리는데, 각 파일만 보는 테스트는 그 접합부를 놓친다.

## 2. Windows 브라우저 시각검증

- Environment: Windows-browser
- 별 fragment: `TASK-20260901T160000-connect-os-default-pb0008.md`
