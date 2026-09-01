---
run_at: 2026-09-01T16:05:00+09:00
session: ai/claude/feature-0043-cli-failure-reason
scope: 자식 AI CLI 실패 사유 소실 해소 (REQ-20260901-cli-failure-reason)
verdict: PASS
---

# Run — TASK-20260901T160000 자식 AI 실패 사유가 사용자에게 도달하는가

## Environment

- 컨테이너 `repo-unittest-agent:latest`, worktree 마운트(`/work`),
  `PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0003-agent-web-ui/src:/work`,
  `PYTHONDONTWRITEBYTECODE=1` (Makefile `test` 타깃과 같은 배선)
- **Environment: Windows-browser — 미수행(사유 명시)**: 이번 cycle 의 `static/**` 변경은
  **러너 파이썬 사본 1개**(`static/agent/bridge_agent.py`, 브라우저가 실행하지 않고 사용자가
  내려받는 파일)뿐이다. HTML·CSS·JS **변경 0** — 렌더·레이아웃·상호작용 표면이 없다.
  변경된 문자열이 나타나는 유일한 화면은 «연결된 AI 가 실제로 실패했을 때의 답변 말풍선» 이며,
  그 표면은 **말풍선 본문(마크다운 텍스트)** 이라 별도 시각 회귀면이 없다.
  (직전 cycle `TASK-20260901T140000` 과 동일한 판단·동일한 파일군.)

## 1. 라이브 근본원인 재현 (결정적)

동일 러너 계정(`root`)·동일 자식 cwd(`~/.mysql-ai-bridge/work`)에서 러너가 조립하는 것과 같은
명령을 실행:

| 관측 | 값 |
|---|---|
| 종료코드 | **1** |
| **stdout** | `You've hit your session limit · resets 5:30pm (Asia/Seoul)` ← **사유가 여기 있다** |
| stderr | `Warning: no stdin data received in 3s, proceeding without it. …` (종료코드와 무관) |

종전 코드는 stderr 만 실었으므로 사용자 문장은 `AI 가 오류로 끝났습니다(exit 1):` — 콜론 뒤가
비었다. 라이브 대화 `…d7010dcf` 의 두 실패(15:38:16 · 15:39:07)와 정확히 같은 표면.

## 2. 단위 검증

| 대상 | 결과 |
|---|---|
| 신규 `tests/test_cli_failure_reason.py` **11건** | **PASS** |
| `tests/test_bridge_agent_sync.py`(배포 사본 해시·러너 계약) | PASS |
| `tests/test_win_ai_detection.py`(`_run_cli_cancelable` 실구동) | PASS |
| `unit/feature-0043-external-llm-bridge/tests` 전량 | PASS — 잔여 3건은 **main 기준선과 동일**한 pre-existing(`test_llm_gate`, 테스트 순서 의존 `ModuleNotFoundError`) |
| `unit/feature-0003-agent-web-ui/tests` + `feature-0041/tests` 전량 | **PASS** |
| ruff (`bridge_agent.py` · 신규 테스트) | All checks passed |

기준선 귀책 판별: 같은 명령을 **main 체크아웃에서** 실행해 동일한 3건이 동일하게 실패함을 확인.
이번 변경의 귀책 실패 **0**.

## 3. 뮤테이션 역검증 (3종 전건 KILL)

| # | 주입 | KILL |
|---|---|---|
| M1 | `detail = _meaningful_lines(err) or _meaningful_lines(out)` → `err` 만 (**원 결함 재주입**) | **3건** |
| M2 | `_STDERR_NOISE` 필터 제거(잡음이 사유 자리를 차지) | **2건** |
| M3 | `_redact_secrets` 호출 제거 | **1건** |

M1 이 이 파일의 존재 이유다 — 원 결함을 그대로 되돌리면 테스트가 즉시 잡는다.

## 4. 배포본 사본 동기화

`unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py` = 정본과 **바이트 동일**
(`test_served_runner_is_identical_to_canonical` PASS).

## 5. 배포 후 실측 필요분 (정직 분리)

- 위 전부는 「사유가 전달된다」를 증명한다. **그 사용자의 다음 실패에서 실제로 사유가 보이는지**는
  러너가 최신 사본으로 갱신된 뒤에만 관측된다 — 러너는 사용자 머신 파일이라 우리 배포가
  갱신하지 못한다(서버가 `runner_update.stale_build` 로 알리고, 사용자가 「연결 준비」를 다시
  누르면 갱신된다).
- 원장 corroboration 재측정 축: `WebAiTasks` 중 `Answer LIKE '%오류로 끝났습니다%'` 이면서
  **사유 자리가 빈** 건수. 배포 시점 기준선 = 전 기간 **5건**(전건 사유 없음).
