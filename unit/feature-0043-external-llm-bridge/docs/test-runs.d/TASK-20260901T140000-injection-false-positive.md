---
run_at: 2026-09-01T14:40:00+09:00
session: ai/claude/feature-0043-bridge-injection-falsepositive
scope: 인젝션 오판 자가중단 해소 (REQ-20260901-injection-false-positive)
verdict: PASS
---

# Run — TASK-20260901T140000 인젝션 오판 해소

## Environment

- 컨테이너 `repo-unittest-agent:latest`, worktree 마운트(`/work`),
  `PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0003-agent-web-ui/src:/work`,
  `PYTHONDONTWRITEBYTECODE=1` (Makefile `test` 타깃과 같은 배선)

## 결과

| 대상 | 결과 |
|---|---|
| `unit/feature-0003-agent-web-ui/tests` + `feature-0041/tests` + `feature-0043/tests` 전량 | **PASS** (rc=0) |
| 신규 `feature-0043/tests/test_injection_false_positive.py` 19건 | PASS |
| `feature-0041/tests/test_session_guard.py` (기존 32 + 신규 12 = 44건) | PASS |
| ruff (`session_guard.py`·`ai_tools.py`·`bridge_agent.py`·신규 테스트) | All checks passed |

## 뮤테이션 역검증 (3종 전건 KILL)

| # | 주입한 결손 | 죽은 테스트 |
|---|---|---|
| M1 | 토큰 값을 프롬프트 본문에 되돌림 | `test_token_value_is_absent_from_the_prompt` |
| M2 | `_recent_conversation_context` 의 거부턴 필터 제거 | `test_history_excludes_prior_injection_refusals` |
| M3 | 자식 프로세스 중립 cwd 제거 | `test_child_runs_in_a_neutral_workdir` |

## 기준선 대조 (귀책 판별)

`tests/test_llm_gate.py` 3건은 **로컬 py3.12 전량 실행 시에만** 실패하며,
`origin/main` 에서도 동일하게 실패한다(단독 실행은 PASS · 컨테이너 py3.11 은 PASS).
→ 본 cycle 무관, pre-existing 테스트 순서 상호작용.

## 갱신한 기존 계약 테스트 2건 (사유)

- `test_handoff_trust.py::test_runner_contract_is_accurate_…` — 토큰 노출면이 프롬프트 본문에서
  환경변수로 옮겼다. 계약(「노출면을 정직하게 적는다」)은 그대로이고 **사실이 바뀌었으므로**
  옛 문장이 남으면 그것이 거짓이 된다. 새 검사는 옛 문장의 **부재**까지 함께 단정한다.
- `test_ux_parity.py::test_runner_puts_system_prompt_first` — 「운영자 지침이 이긴다」 계약은
  유지하되, 판정 대상을 문구에서 **순서 + 채널 분기 존재**로 바꿨다. 옛 검사는 이번에 제거한
  인젝션 서명 문구(「시스템 프롬프트로 삼아」)를 요구해, 그대로 두면 결함을 되돌리라고
  요구하는 게이트가 된다.

## 잔여

- 배포 후 라이브 왕복 검증(같은 대화에서 재요청 → 거부문이 아닌 실제 답변) — POST-DEPLOY.
