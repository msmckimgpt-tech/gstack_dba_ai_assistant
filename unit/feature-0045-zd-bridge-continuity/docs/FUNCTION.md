---
doc_type: FUNCTION
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

무중단 배포 스파인(feature-0014/0020)이 **브리지 축을 보지 못하던 구멍**을 메운다.

feature-0043 전환 이후 사용자 질문은 서버 LLM 이 아니라 **개인 머신 AI** 가 처리한다. 그
AI 는 `wait_for_request` 로 서버에 붙어 대기하고, 질문을 가져가면(`claim_request`) 도구를
여러 번 호출하며 조사한다. 그런데 배포 게이트가 보는 신호(`active_streams` · `ask_jobs`)는
**그 둘 중 어느 것도 세지 않는다.** 즉 "웹브라우저와 AI 가 연결되어 요청을 주고받는 중" 이
정확히 게이트의 사각지대였고, 배포는 그것을 "조용함(0)" 으로 읽고 replica 를 내렸다.

이 기능은 그 축을 관측 가능하게 만들고, **대기는 즉시 비우고 작업은 끝날 때까지 기다리는**
비대칭 드레인을 도입하며, 개인 AI 가 붙는 MCP 표면을 2 replica 로 나눠 교체 중에도 후보가
남게 한다.

## 2. Goal

- REQ-20260827T073753-zd-bridge-continuity: 웹브라우저–개인 AI 브리지로 요청을 주고받는
  중에 배포가 진행되어도 그 작업이 중단되지 않는다. 대기 연결은 끊기지 않고 교대하며,
  진행 중인 조사는 완주하고, 부득이 끊긴 작업은 손실 없이 대기열로 되돌아간다.

## 3. In Scope

### P0-A. 브리지 in-flight 관측 (`bridge_drain.py`)

두 종류를 **따로** 센다. 합치면 배포가 판단할 수 없다.

| | 대기(`bridge_waiters`) | 작업(`bridge_inflight`) |
|---|---|---|
| 무엇 | `wait_for_request` 블로킹 대기 | 개인 AI 가 조사 중인 도구 호출 |
| 끊기면 | 잃는 것이 없다(다시 부르면 된다) | **그 왕복이 버려진다** |
| 배포 시 | 드레인 신호로 **즉시 비운다** | **끝날 때까지 기다린다** |

계상은 미들웨어(`BridgeInflightMiddleware`)가 `/api/ai/tools/*` 경로에서 한다 — 각 핸들러에
흩뿌리면 새로 추가된 도구가 조용히 게이트 밖에 남는다.

### P0-B. lame-duck 드레인

`POST /internal/bridge-drain`(loopback 전용)이 켜지면 그 replica 는:

1. `/livez` 가 503 → Caddy active health(2s)가 LB 후보에서 제외 → **신규 유입 정지**
2. 대기 중인 롱폴이 **정상 200**(`draining: true`)으로 반환 → 클라이언트가 곧바로 다시
   부르면 남은 replica 가 받는다 (오류가 아니므로 러너의 백오프 경로를 타지 않는다)
3. 신규 도구 호출은 **503 + `X-Bridge-Draining: 1`** — MCP 어댑터는 엣지를 거치지 않고
   직결하므로 이 신호가 없으면 드레인된 replica 를 계속 붙잡는다
4. 진행 중인 호출은 그대로 완주 — 문을 닫는 것이지 손님을 내쫓는 것이 아니다

상태는 **프로세스 로컬**이다(recreate 되면 사라진다). `?release=1` 로 되돌린다 — 배포가
replica 를 못 내리고 중단했을 때 문이 닫힌 채 남는 것을 막는다.

### P0-C. pre-drain 게이트 확장 (`bin/deploy-web.sh`)

`active_streams + bridge_inflight` 가 0 이 될 때까지 기다린다(대기는 드레인으로 즉시 빈다).
상한 90s → **180s**(중계 왕복 상한 120s 를 덮는다 — 짧으면 가장 오래 걸리는 조사가 항상 잘린다).
probe 는 `/livez` 가 아니라 전용 창구를 쓴다(드레인 중 `/livez` 는 503 이라 자기 조회가 깨진다).

### P0-D. MCP 표면 2-replica (`ext-tool-mcp-a/b`)

개인 AI 가 붙는 `/api/ai/mcp` 의 upstream 이 단일 컨테이너였다 — surge 도 드레인도 없이
배포마다 통째로 recreate 되어 연결이 끊겼다(stop_grace 15s). web-a/web-b 와 같은 구조로
나누고 스파인의 **전용 one-at-a-time 롤링**(`rollout_mcp_replicas`)을 받는다.

- `stateless_http=True` — replica 가 둘이면 세션이 프로세스에 묶여선 안 된다
- `stop_grace_period` 15s → **130s** (중계 상한 120s + 여유)
- WORKERS 일괄 recreate 에서 분리, 완결 판정(`verify_workers_at_sha`)에는 포함

### P0-E. 점유 손실 0

배포가 **강행했을 때만**(`PREDRAIN_FORCED > 0`) 끊겼을 수 있는 점유를 되돌린다.
`ClaimedBy` 는 **지우지 않고** lease 만 만료시킨다:

| 누가 | 무슨 일이 되나 |
|---|---|
| 원래 가져간 AI 가 살아 있었다 | `submit_answer` 는 `ClaimedBy` 만 보므로 **그대로 제출된다** |
| 원래 가져간 AI 가 죽었다 | lease 가 만료됐으므로 다음 연결이 **다시 가져간다** |

먼저 끝내는 쪽이 이긴다. `grace_sec=60` — 배포 직후 막 시작된 정상 작업은 건드리지 않는다.

### P0-F. 러너 재연결 백오프

`bridge_agent.py` 의 대기 루프는 연결 실패(`_http == 0`) 시 곧바로 `continue` 했다 — 서버가
교체되는 몇 초 동안 **초당 수천 번 재시도**하며 사용자 머신의 CPU 를 태웠다. 대기에는 여전히
sleep 이 없다(그것이 '폴링 아님' 의 실체다); 쉬는 것은 **연결 복구**뿐이다(1s → 15s).
`draining: true` 응답은 오류가 아니므로 백오프 없이 즉시 재호출한다.

### P0-G. quiesce 게이트의 네 번째 축

gateway·워커 교체 게이트는 `ask_jobs` + `active_streams` 만 봤다. 브리지 전환 이후 그 둘은
사용자 작업을 대변하지 않으므로 게이트는 **항상 조용함으로 통과**했다(vacuous pass).
`bridge_active_total`(점유되어 처리 중인 작업)을 표본에 더하고, 서버 LLM 차단 운영에서는
`ask_jobs` 대신 이 축을 정본으로 본다 — 종전 판정("worker 모드가 아니면 무조건 중단")은
브리지 전환 이전 세계를 전제로 쓰였고 그대로 두면 배포를 영구 차단한다.

## 4. Out of Scope

- **브라우저↔서버 축의 재설계** — 그쪽은 Caddy LB + 폴링이라 이미 배포를 견딘다.
- **개인 AI 런타임의 가용성** — AI 가 꺼져 있으면 답이 오지 않는다(feature-0043 §9 수용된 한계).
- **claim heartbeat** — 러너가 살아 있는지 주기 신호로 확인하는 설계. 지금은 lease(30분) +
  강행 시 회수로 충분하고, heartbeat 는 "폴링 금지" 요구와 정면으로 부딪힌다.
- **MCP 세션 재개(resume)** — stateless 로 만들어 세션 자체를 없앴으므로 필요가 사라졌다.

## 5. Inputs

- `POST /internal/bridge-drain[?release=1]` — 드레인 제어(loopback)
- `GET /internal/bridge-activity` — 전역 브리지 점유 수(loopback)
- `POST /internal/bridge-reclaim?grace_sec=<n>` — 점유 회수(loopback)
- env: `DEPLOY_WEB_PREDRAIN_TIMEOUT`(기본 180) · `EXT_TOOL_MCP_STATELESS`(기본 1)

## 6. Outputs

- `/livez` · `/readyz` 의 `bridge_waiters` · `bridge_inflight` · `draining`
- 드레인 중 도구 호출: `503` + `X-Bridge-Draining: 1`
- 드레인 중 대기 종료: `200` + `draining: true`(오류 아님)
- 배포 보고: `bridge_continuity_summary` — 강행 횟수와 그 의미

## 7. Main Flow

1. 개인 AI 가 `wait_for_request` 로 붙어 있고, 어떤 질문은 이미 조사 중이다.
2. 배포가 `web-a` 를 내리기 직전 `predrain` 이 그 replica 에 드레인을 건다.
3. Caddy 가 2초 안에 `web-a` 를 후보에서 뺀다. 대기 중이던 롱폴은 정상 종료되고, 러너는
   곧바로 다시 부른다 — 그 호출은 `web-b` 가 받는다.
4. 조사 중이던 도구 호출은 계속 돈다. `predrain` 은 그것이 0 이 될 때까지 기다린다.
5. 조용해지면 `web-a` 를 교체한다. 새 프로세스는 드레인이 꺼진 상태로 뜬다.
6. `web-b` 도 같은 절차. 이어서 MCP replica 도 하나씩 교체한다.
7. 상한을 넘겨 강행했다면 배포 말미에 끊겼을 수 있는 점유를 대기열로 되돌리고, 그 사실을
   보고에 남긴다.

## 8. Acceptance Criteria

- AC-20260827T073753-zd-bridge-continuity-1: `/livez` · `/readyz` 가 `bridge_waiters` ·
  `bridge_inflight` 를 노출하고, 셋(`/internal/bridge-drain` 포함)이 **같은 snapshot 함수**를 쓴다.
- AC-20260827T073753-zd-bridge-continuity-2: 드레인 중 `wait_for_request` 는 **200 +
  `draining: true`** 로 끝난다(오류가 아니다). 진행 중 도구 호출은 완주한다.
- AC-20260827T073753-zd-bridge-continuity-3: 드레인 중 **신규** 도구 호출은 503 +
  `X-Bridge-Draining: 1` 이고, MCP 어댑터는 그 신호에서 다음 replica 로 넘어간다.
- AC-20260827T073753-zd-bridge-continuity-4: `predrain` 은 `bridge_inflight` 가 0 이 될
  때까지 기다리고, `bridge_waiters` 는 기다리지 않는다.
- AC-20260827T073753-zd-bridge-continuity-5: probe 실패를 "조용함" 으로 읽지 않는다(기존
  게이트로 대체 판정하고 그 사실을 로그로 남긴다).
- AC-20260827T073753-zd-bridge-continuity-6: recreate 실패 경로가 드레인을 되돌리고,
  롤링 시작 전 잔존 드레인을 청소한다.
- AC-20260827T073753-zd-bridge-continuity-7: MCP 표면이 `ext-tool-mcp-a/b` 2 replica 이고
  정의가 동일하며, 구 단일 서비스가 compose 에 남아 있지 않다.
- AC-20260827T073753-zd-bridge-continuity-8: MCP 롤링은 상대가 healthy 일 때만 이쪽을
  내린다(fail-closed). web replica 를 만지지 않는다.
- AC-20260827T073753-zd-bridge-continuity-9: 점유 회수는 `ClaimedBy` 를 보존하고 lease 만
  만료시키며, **강행이 있었던 배포에서만** 실행된다.
- AC-20260827T073753-zd-bridge-continuity-10: 러너의 sleep 은 **재연결 백오프 하나뿐**이고,
  성공 시 초기화되며 상한이 있다. 대기 간격 인자는 없다.
- AC-20260827T073753-zd-bridge-continuity-11: quiesce 표본에 브리지 축이 포함되고,
  `unknown` 은 조용함으로 읽지 않는다. 서버 LLM 차단 운영에서 게이트가 영구 차단되지 않는다.
- AC-20260827T073753-zd-bridge-continuity-12: `/internal/*` 은 loopback 전용이다.

## 9. Constraints / Risks

- **드레인은 프로세스 로컬**이다. 배포가 비정상 종료하면 그 replica 가 문이 닫힌 채 남을 수
  있어, 롤링 시작 시 `clear_stale_drain` 이 청소한다. 그래도 남으면 `?release=1` 로 수동 복구.
- **강행은 여전히 가능하다**(상한 초과). 그때 끊긴 왕복은 되돌릴 수 없고, 점유 회수로 **작업
  자체**만 보존된다 — 이미 쓴 토큰·조사는 버려진다. 그 사실을 배포 보고에 정직하게 남긴다.
- **상시 컨테이너 1개 증가**(MCP replica). 실측 web ~96MB 수준.
- **MCP 라우트에 active health 가 없다** — 이 전송은 GET 에 4xx 로 답하는 것이 정상이고 그
  코드가 SDK 버전마다 달라, 단일 `health_status` 고정은 버전 변경 시 양 replica 동시 down 을
  만든다. passive 격리 + 재시도로 대체했다.

## Pre-approved Changes

- deploy_scope: included  <!-- 전역 선언(FIRST_REQUEST.md) 준용 -->
- reachability_scope: included  <!-- 완료 판정에 사용자 진입 경로 도달성 포함 -->
