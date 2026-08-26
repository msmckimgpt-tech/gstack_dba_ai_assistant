---
run_at: 2026-08-27T09:45:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: feature-0043 브리지 대기/폴링 UI (static/app/composer.js)
verdict: DEFERRED — POST-DEPLOY 로 수행
---

# Run — feature-0043 브리지 UI 시각검증

Environment: Windows-browser — **미수행(POST-DEPLOY 로 이월)**

## 미수행 사유 (AGENTS.md §15.4.1 · PB-0008 — 사유 명시 조항)

검증 대상 화면이 **아직 어디에도 존재하지 않는다.** 이번 cycle 이 추가한 UI 는
`bridge_pending` 응답을 받았을 때만 나타나는 대기 말풍선 → 폴링 → 답변 렌더 흐름인데,
그 응답은 **서버 LLM 게이트가 잠긴 배포본**에서만 나온다. 현재 라이브는 전환 이전 코드라
브라우저로 열어도 이 경로가 재현되지 않는다.

브리지 setup 자체는 가능하다(`bin/win-browser.py doctor` → Chrome + userspace relay 기동 가능
확인). 막힌 것은 **검증 대상의 부재**다.

## POST-DEPLOY 검증 계획 (배포 직후 수행)

`deploy_scope: included` 로 cycle-final 후 배포가 이어지므로, 배포 완료 시점에 아래를 실측한다.

1. `bin/win-browser.py launch --url https://<host>/` → 로그인
2. 새 대화에서 질문 전송 → **대기 말풍선**(“회원님의 AI(MCP 연결)가 처리합니다”) 렌더 확인
3. `llm_usage` 행 증가 **0건** 확인 (서버 계정이 쓰이지 않았다는 판정 — FUNCTION.md §8 AC-3)
4. 다른 경로에서 `claim_request` → `submit_answer` (REST 또는 `bridge_runner.py --claim/--submit`)
5. 웹 화면이 **폴링으로 자동 갱신**되어 답변이 같은 대화에 렌더되는지 확인 (AC-6)
6. 스크린샷을 이 fragment 에 첨부하고 `verdict` 를 PASS/FAIL 로 갱신

## 왜 배포 전 검증을 강행하지 않았나

bind-mount 컨테이너로 미머지 브랜치를 띄워 검증하는 경로가 있으나, 이 cycle 의 변경은
**서버 LLM 차단이 전제**라 그 컨테이너에서도 게이트를 열면 재현되지 않고 닫으면 라이브와
같은 상태가 된다 — 즉 배포본과 동일한 조건을 만들어야 의미가 있다. 배포 직후 실측이
가장 적은 가정으로 같은 것을 확인한다.
