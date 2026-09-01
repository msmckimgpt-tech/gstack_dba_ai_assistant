---
run_at: 2026-09-01T15:10:00+09:00
session: ai/claude/feature-0043-bridge-injection-falsepositive
scope: 인젝션 오판 자가중단 해소 — feature-0003 소유 파일(session_guard·ai_tools·러너 배포 사본)의 시각검증 축
verdict: PENDING — POST-DEPLOY 로 이월 (사유 명시)
---

# Run — 인젝션 오판 해소 (Environment: **Windows-browser** — PRE-DEPLOY 미수행, 사유 아래)

정본 cycle 문서는 `unit/feature-0043-external-llm-bridge/docs/TASK-20260901T140000-injection-false-positive.md`.
코드가 feature-0003 에 거주하므로(§10.5 · check #13 은 **파일 소유 feature** 에 기록) 여기 남긴다.

## 이번 변경의 UI 표면 — 정확히 한 곳

| 변경 | UI 표면 |
|---|---|
| `session_guard.wrap_principal_request` / `wrap_conversation_history` | **없음** — 나가는 프롬프트 구획(화면 미노출) |
| `ai_tools.claim_request` · `_bridge_origin_preamble` · `_recent_conversation_context` | **없음** — 서버가 러너에게 주는 페이로드 |
| `static/agent/bridge_agent.py` | **없음** — 사용자가 내려받는 러너 파이썬 파일(브라우저 렌더 대상 아님) |
| `session_guard.INJECTION_REFUSAL_NOTE` 부가 | **있음** — 대화 말풍선 말미에 markdown 인용문(`> 참고: …`) 1줄 |

HTML·CSS·JS **무변경**(`git diff --cached --stat` 기준 `static/**` 변경은 러너 파이썬 사본
1개뿐). 즉 레이아웃·스타일·스크립트 회귀면이 없다.

## 왜 PRE-DEPLOY 로 못 찍는가

유일한 UI 표면(안내 1줄)은 **연결된 개인 AI 가 오판 거부 답변을 실제로 제출해야** 화면에
나타난다. 그 경로는 러너 → 서버 `submit_answer` → 대화 렌더의 전 구간을 타므로, 배포되지 않은
서버에서는 재현할 수 없다(웹 UI 를 직접 조작해 만들어낼 수 있는 상태가 아니다).

## POST-DEPLOY 에 확인할 것 (이월)

1. 실 Windows 브라우저에서 해당 대화(`20260901030637-95dc8844`)를 열어 **기존 거부 말풍선 2건이
   그대로 보존**되는지(우리는 지우지 않는다).
2. 같은 대화에서 재요청 → 답변이 거부문이 **아닌지**(핵심 완료 판정).
3. 오판이 재현되면 그 말풍선 말미에 `> 참고: 연결된 AI 가 …` 1줄이 **markdown 인용문으로 렌더**
   되는지(원문 그대로 노출되지 않는지).

결과는 같은 파일명 + `-postdeploy` 접미 fragment 로 추가한다.
