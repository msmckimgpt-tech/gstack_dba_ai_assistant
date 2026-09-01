---
run_at: 2026-09-01T12:45:00+09:00
session: ai/claude/interrupt-preserve-postdeploy
scope: 중단 보존 2 cycle 의 POST-DEPLOY 실측 — 배포 도달 확인 + 왕복 검증 블로커 확정
verdict: PARTIAL — 도달 4/4 PASS · **중단 왕복 12항목 미수행(개인 AI 미연결로 전송 자체가 차단)**
---

# Run — 중단 보존 POST-DEPLOY 실측 (Environment: **Windows-browser**)

대상 배포: `b793e7ea` (scope=all — web-a/b·워커·MCP 동일 SHA 실측, 엣지 `no upstreams available` **0건**).
선행 배포: `3490cf73` (cycle 1).

## 1. 배포 도달 — 4/4 PASS

「배포했다 ≠ 도달했다」를 먼저 끊는다. 실 Windows Chrome(격리 프로필, `bootstrap_admin`
세션)에서 **서빙되는 자산·응답을 직접 읽어** 확인했다.

| # | 대상 | 확인 | 결과 |
|---|---|---|---|
| D1 | `GET /static/app.js?v=3c9d838b3ed0` (397,067 bytes) | `_reloadForPreservedInterrupt` 존재 | **PASS** |
| D2 | 〃 | `preserve_reasoning: true` (중단 호출의 보존 의도) | **PASS** |
| D3 | 〃 | 토스트 문구 `진행된 내용은 대화에 남습니다` | **PASS** |
| D4 | `GET /api/ai/manifest` · `GET /api/ai/openapi.json` | `preserve_reasoning` 파라미터 + `"default": true` | **PASS** (양쪽) |

D1~D3 은 `?v=` 스탬프가 주입된 **실 서빙 사본**을 fetch 해 문자열로 확인했다(소스 트리가 아니라
브라우저가 실제로 받는 바이트). D4 는 외부 AI 도구가 읽는 표면이다 — 기본값을 서버에 둔 판단이
그 표면까지 도달했는지가 이 cycle 의 요지 중 하나였다.

## 2. 중단 왕복 12항목 — **미수행 (블로커 확정)**

앞선 두 fragment 가 사전 열거한 측정 항목(서버 경로 9건 + 브리지 3건)은 **하나도 수행하지
못했다**. 사유는 추정이 아니라 실측이다:

```
#sendBtn  aria-disabled="true"  class="send-btn is-access-blocked"
title="내 AI 가 연결되어 있지 않습니다. 아래 [연결하기] 를 눌러 연결하세요."
본문: "내 AI가 연결되어 있지 않습니다 — 이 서비스는 답변을 내 컴퓨터의 AI가 만듭니다."
```

Playwright 클릭이 15초 동안 재시도하다 `element is not enabled` 로 실패했다. 즉 **질문 전송
자체가 차단**되어 「진행 중인 run」을 만들 수 없고, 중단 UX 는 진행 중 run 이 실재해야만
관측된다.

**왜 러너를 붙일 수 없었나**: 라이브는 `feature-0043` 전환 모드라 답변을 개인 AI 러너가 만든다.
현재 러너 프로세스는 **0개**(`pgrep -af bridge_runner` 무응답). 재기동에는 **새 `mat_` 토큰**이
필요한데 러너는 토큰을 저장하지 않으므로(feature-0043 `REPORT.md`), 웹 화면에서 사람이 발급해
`bridge_setup.sh` 를 실행해야 한다 — AI 세션이 단독으로 만들 수 없는 자격이다.

**이월 항목은 그대로 유효하다** — 측정 항목 12건은
`TASK-20260901T020746-interrupt-context-preserve.md` §4(9건) ·
`TASK-20260901T031500-interrupt-preserve-bridge.md` §4(3건)에 **사전 열거**돼 있다. 개인 AI 를
연결한 뒤 그 목록대로 수행하면 된다.

## 3. 이 상태에서 무엇이 «검증됐고» 무엇이 «안 됐는가»

혼동을 막기 위해 명시한다.

| 축 | 상태 | 근거 |
|---|---|---|
| 보존 본문 계약(구획·상한·폴백·빈손) | **검증됨** | 실호출 단위 테스트 19건 |
| `/api/cancel` 기본값 방향 | **검증됨** | TestClient 로 엔드포인트 실호출 9건 + 뮤테이션 M1 KILL |
| 브리지 꼬리 조립·배선·degrade | **검증됨** | 실호출 12건 + 뮤테이션 KILL |
| 배포 도달(프런트 자산·외부 스펙) | **검증됨** | 위 D1~D4 실 브라우저 실측 |
| **사용자가 화면에서 겪는 중단 왕복** | **미검증** | 러너 미연결로 관측 대상 생성 불가 |

마지막 줄이 이 fragment 의 존재 이유다. 앞의 네 줄이 통과했다는 사실이 마지막 줄을 대신하지
않는다 — 계약이 옳고 자산이 도달했어도, 사용자가 실제로 그 화면을 보는지는 아직 보지 않았다.
