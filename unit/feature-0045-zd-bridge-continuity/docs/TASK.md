---
doc_type: TASK
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: shipped — 라이브 배포 `e7d54f70` · 끊김 0 실측
- Owner: AI
- Priority: high
- Last Updated: 2026-08-27

## 2. Implementation Plan

### 2.1 Plan

- **영향받는 파일:**
  - `unit/feature-0003-agent-web-ui/src/bridge_drain.py` (신규) — `waiting` · `tool_call` ·
    `begin_drain` · `end_drain` · `snapshot` · `BridgeInflightMiddleware`
  - `unit/feature-0003-agent-web-ui/src/app.py` — `bridge_drain` import + 미들웨어 등록
  - `unit/feature-0003-agent-web-ui/src/routers/system.py` — `livez`(드레인 시 503) ·
    `readyz`(200 유지) · `internal_bridge_drain` · `internal_bridge_activity` ·
    `internal_bridge_reclaim`
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` — `wait_for_request` 대기 루프에
    `_drain.waiting()` + 드레인 시 정상 종료
  - `bin/deploy-web.sh` — `replica_drain_probe` · `replica_release_drain` · `predrain` 확장 ·
    `PREDRAIN_TIMEOUT` 180 · `reclaim_bridge_claims` · `bridge_continuity_summary` ·
    `clear_stale_drain` · `rollout_mcp_replicas` · `sweep_legacy_ext_tool_mcp` ·
    `WORKERS`/`MCP_REPLICAS` 분리 · `verify_workers_at_sha` 확장
  - `bin/lib/quiesce.sh` — `bridge_active_total` · `server_llm_blocked` · `quiesce_sample`
    4축 · 실행 모드 게이트 브리지 분기
  - `docker-compose.yml` — `x-ext-mcp-common` anchor + `ext-tool-mcp-a/b`
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — MCP 라우트 2 upstream LB
  - `unit/feature-0041-external-ai-tool-surface/src/external_tool_mcp_http.py` —
    `_build_server`(stateless) · `_post` 드레인 재라우팅
  - `unit/feature-0043-external-llm-bridge/src/bridge_agent.py` (+ `static/agent/` 배포본) —
    재연결 백오프 · `draining` 즉시 재호출
- **접근 방법:** 관측(대기·작업 분리) → 드레인(문 닫기, 신규만 거절) → 게이트 확장(작업만
  대기) → MCP 2-replica → 손실 방지(lease 만 만료) → 러너 백오프 → quiesce 4축.
- **완료 판정 기준:** 드레인 중 대기가 200 으로 끝나고 in-flight 는 완주하며, `predrain` 이
  `bridge_inflight` 가 0 이 될 때까지만 기다린다. 예: probe 가 `0 2 1 → 0 1 1 → 0 0 1` 로
  변하면 3회 폴링 후 통과(`FORCED=0`), `0 0 7` 이면 1회에 통과.
- **위험도:** Major (배포 스파인 + 컨테이너 토폴로지 변경. 파괴적 데이터·인증 변경 없음)

## 3. Task Queue

- [x] TASK-20260827T073753-001 현행 게이트가 브리지 축을 못 보는 지점 실측
- [x] TASK-20260827T073753-002 `bridge_drain` 모듈 + 미들웨어 배선
- [x] TASK-20260827T073753-003 `/livez` 503 · `/readyz` 200 유지 · `/internal/*` 3종
- [x] TASK-20260827T073753-004 `wait_for_request` 대기 계상 + 드레인 정상 종료
- [x] TASK-20260827T073753-005 `predrain` 확장 + 드레인 probe/해제 + 상한 180s
- [x] TASK-20260827T073753-006 MCP 2-replica(compose·Caddy·stateless) + 전용 롤링
- [x] TASK-20260827T073753-007 점유 회수(lease 만 만료) + 강행 시에만 실행
- [x] TASK-20260827T073753-008 러너 재연결 백오프 + 배포본 해시 동기화
- [x] TASK-20260827T073753-009 quiesce 4번째 축 + 브리지 운영 분기
- [x] TASK-20260827T073753-010 기존 계약 테스트 정합(서비스명·allowlist·sleep 계약 정밀화)
- [x] TASK-20260827T073753-011 신규 테스트 4종(46건)
- [x] TASK-20260827T073753-012 적대적 검증 패널(3 관점) + 적발 P1 6·P2 9·P3 3 전건 조치
- [x] TASK-20260827T073753-013 테스트 vacuous pass 해소(소스 문자열 → 실행·시그니처 대조)
- [x] TASK-20260827T073753-014 라이브 배포 1차 — web·MCP 전환 성공, `/livez` 가 실제
  `bridge_waiters=1`(개인 AI 대기 중)을 노출해 **종전 게이트의 사각지대를 라이브로 실증**
- [x] TASK-20260827T073753-015 배포 중단 결함 수정(CHG-0003 — 정리 조회가 배포를 죽임)
- [x] TASK-20260827T073753-016 재배포 완료 — 전 서비스 `e7d54f70` · `bridge_continuity_summary`="끊김 0" · 엣지 no-upstreams 0건

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Notes

- **`test_llm_gate.py` 3건은 이 변경과 무관하다.** feature-0041/0043 스위트를 함께 돌릴 때만
  실패하며(`modules` 네임스페이스가 feature-0003/0002 사이에서 갈린다), `main` 에서도 동일하게
  재현된다. 단독 실행은 통과. 정본 판정은 컨테이너 `make test`.
- 러너의 "sleep 금지" 계약은 **약화가 아니라 정밀화**됐다: 허용되는 sleep 은 재연결 백오프
  하나뿐임을 테스트가 값으로 고정한다(`sleeps == ["time.sleep(backoff)"]`).

## 9. Requested Scope (요청 범위 자기-열거)

원 요청: "프로젝트 내 서비스에서, 웹브라우저 간 AI가 연결된 상태에서 요청을 주고받는 중
배포가 진행되어도 작업이 중단되지 않는 무중단 배포 환경을 재구성해주세요."

- [x] `연결된 대기가 배포로 끊기지 않는다` — 산출물: `bridge_drain.waiting()` +
  `ai_tools.wait_for_request` 드레인 분기 · 배선 확인: `test_bridge_drain.py` 10건 —
  드레인 시 대기 요청은 라우터가 200 으로 종료(미들웨어 503 대상 아님)
- [x] `주고받는 중인 요청(도구 호출)이 완주한다` — 산출물: `BridgeInflightMiddleware` +
  `predrain` 확장 · 배선 확인: `test_bridge_deploy_gate.py` — probe `0 2 1 → 0 1 1 → 0 0 1`
  에서 3회 폴링 후 통과(`PROBES=3 FORCED=0`), 핸들러 실행 중 in-flight=1 실측
- [x] `AI 가 붙는 문(MCP)이 배포 중에도 살아 있다` — 산출물: `ext-tool-mcp-a/b` +
  Caddy 2-upstream + `rollout_mcp_replicas` · 배선 확인: `test_mcp_replica_topology.py` —
  compose 두 replica 정의 동일·구 서비스 부재·stop_grace(130s) > 중계 상한(120s)
- [x] `끊긴 작업의 손실 0` — 산출물: `/internal/bridge-reclaim`(lease 만 만료) ·
  배선 확인: `test_internal_endpoints.py` — UPDATE 문이 `ClaimedBy` 를 보존하고
  `SubmittedAt IS NULL` 로 제출본을 건드리지 않음
- [x] `배포가 브리지 작업을 인지한다(게이트 정직성)` — 산출물: quiesce 4번째 축 ·
  배선 확인: `quiesce_sample_is_quiet "0|0|0|unknown"` → NOTQUIET 실행 검증
- [x] `라이브에서 실제로 안 끊긴다` — 산출물: 배포 로그 · 배선 확인: **실측 PASS** — `"대기는 드레인으로 교대했고 진행 중 왕복은 완주했다(끊김 0)"` · MCP 교체 중 엣지 400 유지 · no-upstreams 0건 (TEST.md §3)

**주장 affordance 실측 (G3)**: 이 cycle 은 사용자 대면 UI 를 추가하지 않는다(배포 절차와
서버 내부 창구만 바꾼다). 사용자 화면의 말풍선 상태 전이는 feature-0043 의 기존 배선이
그대로 담당한다. → 해당 없음.

**경계변수 양측 검증 (G4)**:
- `PREDRAIN_TIMEOUT`(180s) → 경계 이하: in-flight 가 상한 안에 0 이 되면 통과·`FORCED=0`
  (`test_predrain_waits_for_bridge_tool_calls`, timeout_s=12) / 경계 초과: 남아 있으면
  강행하되 `FORCED=1` 로 기록하고 회수를 발동(`test_predrain_records_forced_when_it_gives_up`,
  timeout_s=2)
- `stop_grace_period`(130s) vs `EXT_TOOL_TIMEOUT_SEC`(120s) → 부등식을 테스트가 값으로
  비교(`test_mcp_stop_grace_outlives_an_in_flight_relay`) — 종전 15s 는 경계 아래였다
- `reclaim grace_sec`(60s) → 경계 이하(막 점유): 회수 대상 아님 / 경계 초과: lease 만료.
  SQL 술어 `ClaimedAt <= NOW() - INTERVAL %s SECOND` 로 고정, 테스트가 존재를 잠금
