---
run_at: 2026-08-28T20:00:00+09:00
session: ai/claude/feature-0043-check-probe
scope: `--check` 연결 확인 (TASK-20260828T200000) — 러너 단일 파일, 화면 변경 없음
verdict: **라이브 실측 PASS** — 결함 재현 → 수정 → 같은 서버에서 정상 확인
---

# Run — `--check` 연결 확인

Environment: **Windows-browser 미수행(대상 화면 없음)** + **라이브 CLI 실측 수행**

## 왜 브라우저 검증이 아닌가

이 cycle 이 바꾼 것은 `bridge_agent.py` 의 확인용 호출 **한 줄**이다. 브라우저가 파싱하거나
실행하는 자산이 아니다(`static/` 아래이지만 `curl` 로 내려받는 파이썬 파일). 게이트는 경로가
`static/` 인 것만 보고 이 구분을 하지 못한다.

**대신 이 결함은 라이브에서 직접 재현하고 고친 뒤 다시 확인했다** — 아래가 그 기록이다.

## 실측 (라이브 `https://localhost`, 배포 `976bd069`)

| # | 확인 | 결과 |
|---|---|---|
| 1 | `list_open_requests` (limit 1) | **0.0초 · 200** — 연결·인증 정상 |
| 2 | `--check` 가 쓰던 호출(`wait_for_request`, timeout 10s) | **10.0초 read timeout** |
| 3 | 같은 호출을 timeout 90s 로 | **55.3초** 뒤 `timed_out: true` (서버 설계대로) |
| 4 | 수정 **전** `bridge_agent.py --check` | `연결 실패: The read operation timed out` |
| 5 | 수정 **후** `bridge_agent.py --check` (같은 서버·같은 토큰) | **`연결 정상.`** |

2·3 이 결함의 실체다 — `wait_for_request` 는 질문이 없으면 **55초를 보류하도록 설계**된
도구인데 10초 timeout 으로 불렀다. 대기 질문이 없는 상태에서는 반드시 실패하고,
**온보딩 시점이 정확히 그 상태**다(지시문 ③단계가 `--check`).

## 회귀 방어

`test_check_probe_uses_a_tool_that_answers_immediately` ·
`test_check_probe_timeout_exceeds_a_normal_round_trip`.
되돌리는 뮤턴트(확인용 호출을 `wait_for_request` 로) 적용 → **둘 다 KILL** 확인.
