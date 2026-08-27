---
doc_type: MODIFY
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260827-0001
- Date: 2026-08-27
- Related Requirement: REQ-20260827T073753-zd-bridge-continuity
- Summary: 무중단 배포 스파인이 **브리지 축을 보지 못하던 구멍**을 메운다. 대기는 드레인으로
  즉시 비우고(끊지 않고 교대), 진행 중인 개인 AI 왕복은 완주를 기다리며, 개인 AI 가 붙는 MCP
  표면을 2 replica 로 나눠 교체 중에도 후보가 남게 한다. 부득이 강행한 배포는 끊겼을 수 있는
  점유를 대기열로 되돌린다(소유자 보존 — 먼저 끝내는 쪽이 이긴다).
- Files:
  - `unit/feature-0003-agent-web-ui/src/bridge_drain.py` (신규)
  - `unit/feature-0003-agent-web-ui/src/app.py` · `routers/system.py` · `routers/ai_tools.py`
  - `bin/deploy-web.sh` · `bin/lib/quiesce.sh`
  - `docker-compose.yml` · `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`
  - `unit/feature-0041-external-ai-tool-surface/src/external_tool_mcp_http.py`
  - `unit/feature-0043-external-llm-bridge/src/bridge_agent.py` (+ `static/agent/` 배포본)
  - 계약 테스트 정합: feature-0014 recreate allowlist · feature-0020 quiesce 스텁 ·
    feature-0041 서비스명 · feature-0043 러너 sleep 계약(정밀화)
- Impact:
  - 배포 시간: 유휴 시 변화 없음(in-flight 0 이면 즉시 통과). 조사 중이면 최대 180s 대기.
  - 자원: 상시 컨테이너 1개 증가(MCP replica).
  - 계약 변경: `/livez` 가 드레인 중 **503** 을 낸다(Caddy 후보 제외가 그 목적). `/readyz` 는
    200 유지(자기참조 방지). `/api/ai/tools/*` 는 드레인 중 신규 호출에 503 + 재라우팅 헤더.
- Rollback Notes:
  - 앱: `app.py` 의 `BridgeInflightMiddleware` 등록 1줄 제거 → 드레인이 무력화되고 종전 동작.
  - 스파인: `PREDRAIN_TIMEOUT` 은 env 로 되돌릴 수 있고(`DEPLOY_WEB_PREDRAIN_TIMEOUT=90`),
    드레인 probe 실패 시 자동으로 기존 게이트로 대체된다(구버전 이미지와 혼합 안전).
  - MCP: `EXT_TOOL_MCP_STATELESS=0` 으로 세션 모드 복귀 가능. 2-replica → 단일로 되돌리려면
    compose 서비스 하나를 지우고 Caddyfile upstream 을 하나로 줄인다(스파인은 멱등).

## CHG-20260827-0002
- Date: 2026-08-27
- Related Requirement: REQ-20260827T073753-zd-bridge-continuity
- Summary: 적대적 검증 패널(3 관점, REV-20260827-0001)이 적발한 P1 6건 · P2 9건 · P3 3건 전건
  조치. 가장 무거운 것은 **`stateless_http` 가 v2 SDK 생성자 인자가 아니라는 사실**이었다 —
  코드가 `TypeError` 를 WARN 으로 삼켜 조용히 stateful 로 떴고, 그러면 2-replica LB 뒤에서
  **평시에도 요청 절반이 세션 404** 다(단일 컨테이너였던 종전보다 나쁘다). 그다음이 pin
  overlay 누락(모든 배포가 워커 단계에서 실패)과 reclaim 하한 부재(정상 점유까지 만료)다.
- Files:
  - `external_tool_mcp_http.py` — `_server_kwargs()` 로 SDK별 인자 자리 분기, 불일치는 기동 실패
  - `bridge_drain.py` — 대기 경로도 드레인 503(어댑터 재라우팅), `DRAIN_EXEMPT_PATHS`(제출·첨부)
  - `routers/system.py` — `_loopback_only` 단일화(+IPv4-mapped), `conn is None` 가드,
    `cursor()` try 안으로, `_bridge_lease_minutes()` 정본 참조, fresh/stale 분리,
    reclaim `since_epoch` 하한
  - `bin/deploy-web.sh` — pin overlay 에 MCP replica, `rollout_mcp_phase`(엣지 전환 앞),
    sweep 을 rollout 성공 뒤로, `DRAINED_SVC`+`on_exit_cleanup`(EXIT/INT/TERM),
    `clear_stale_drain` 을 web_skip 판정 앞으로, fallback strict + `PREDRAIN_UNVERIFIED`,
    reclaim 을 web 롤링 직후로, MCP 가드 `ps -aq`
  - `bin/lib/quiesce.sh` — `server_llm_blocked` sentinel 방식, `bridge_active_total` fresh 만
  - `docker-compose.yml` — MCP replica `restart: unless-stopped`
  - `Caddyfile` — MCP 라우트 `lb_policy ip_hash`
  - `bridge_agent.py`(+배포본) — draining 재시도 하한 0.5s
  - 테스트 — vacuous pass 3건 해소(소스 문자열 → 실행·시그니처 대조), 회귀 가드 10건 추가
- Impact: 계약 변경 2건 — ① 드레인 중 `wait_for_request` 는 200 이 아니라 **503**(어댑터가
  다음 replica 로 넘어가게), ② `submit_answer`·`read_task_attachment` 는 드레인 중에도 **200**.
- Rollback Notes: CHG-0001 과 동일. 추가로 `EXT_TOOL_MCP_STATELESS=0` 이면 세션 모드로 돌아가되
  그때는 `lb_policy ip_hash` 가 친화성을 유지해 고장이 "느려짐" 수준에 머문다.

## CHG-20260827-0003
- Date: 2026-08-27
- Related Requirement: REQ-20260827T073753-zd-bridge-continuity
- Summary: **첫 라이브 배포가 MCP 롤아웃 직후 중단**됐다. `sweep_legacy_ext_tool_mcp` 의
  `docker compose ps -aq ext-tool-mcp` 가 — 그 서비스를 compose 정의에서 **우리가 지웠으므로** —
  `no such service` + exit 1 을 냈고, `set -euo pipefail` 하에서 그 명령 치환이 스크립트를
  그 자리에서 죽였다. 결과: web·MCP 는 신 코드로 교체됐으나 워커·gateway 가 구 코드로 남았다.
- Files: `bin/deploy-web.sh`(`sweep_legacy_ext_tool_mcp`) ·
  `unit/feature-0045-zd-bridge-continuity/tests/test_bridge_deploy_gate.py`(회귀 가드)
- Impact: 정리는 **best-effort** 로 격하 — 조회 실패를 흡수하고, compose 가 이름을 모르면
  라벨(project+service)로 찾는다. 목적은 조회가 아니라 정리다.
- Rollback Notes: 이 변경 자체는 되돌릴 이유가 없다(실패 흡수만 추가). 구 컨테이너가 남으면
  `docker rm -f repo-ext-tool-mcp-1` 로 수동 정리.

> **왜 적대 리뷰가 못 잡았나**: 리뷰어는 `docker compose -p repo ps -aq ext-tool-mcp` 를
> 직접 실행해 "잔재 컨테이너가 있으면 id 를 반환(rc=0)" 을 확인했다. 그러나 배포 스파인은
> **pin overlay 를 포함한 `DC_PROD`** 로 부르고, 그 조합에서는 `no such service` + exit 1 이다.
> 같은 명령처럼 보여도 **호출 형태가 다르면 다른 사실**이다.
>
> **왜 테스트가 못 잡았나**: `test_mcp_rollout_precedes_the_edge_switch` 는 호출 **순서**만
> 봤고 실행하지 않았다. 새 가드는 `set -euo pipefail` 로 원문을 실행해 "정리 실패가 배포를
> 죽이지 않는가" 를 본다(뮤테이션 KILL 확인).

## CHG-20260827-0004
- Date: 2026-08-27
- Related Requirement: REQ-20260827T073753-zd-bridge-continuity
- Summary: 운영 주의 추가(REPORT §5) — **배포가 중단된 상태에서 구 컨테이너를 먼저 지우면
  안 된다.** 스파인이 `rollout_mcp_phase` 에서 죽으면 `reconcile_caddy` 가 아직 안 돈 상태라
  엣지가 구 upstream 을 가리킨다. 그때 구 컨테이너를 지우면 `/api/ai/mcp` 가 502 가 된다
  (라이브에서 약 2분 발생, 사용자 대화 경로는 무영향).
- Files: `unit/feature-0045-zd-bridge-continuity/docs/REPORT.md`
- Impact: 문서만. 코드 동작 불변.
- Rollback Notes: 해당 없음.
