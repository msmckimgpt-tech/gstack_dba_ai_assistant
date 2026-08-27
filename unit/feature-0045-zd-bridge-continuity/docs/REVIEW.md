---
doc_type: REVIEW
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## 사전 승인 근거 (§12.2)

- `deploy_scope: included` — `FIRST_REQUEST.md` 전역 선언 준용. 이 cycle 의 배포는 사전 승인
  범위 안이며, 첫 배포 직전 1줄 표면화한다.
- `reachability_scope: included` — 완료 판정에 사용자 진입 경로 도달성을 포함한다.

## 판단 근거

- 위험도 **Major**: 배포 스파인 + 컨테이너 토폴로지 변경. 인증·인가 변경 없음, 파괴적 데이터
  변경 없음, 되돌리기는 env/설정 수준(MODIFY.md Rollback Notes).
- 사용자 결정 3건(2026-08-27): MCP 는 2-replica 상시 · 진행 중 작업은 **손실 없이** ·
  형제 세션과의 파일 경합은 병합 시점에 자율 처리.

## REV-20260827-0001 [AGENT-TEAM:bridge-deploy-continuity]
- Related TASK: feature-0045-zd-bridge-continuity
- Source: agent-team:bridge-deploy-continuity:3
- Trigger: §18.8 검증 패널. codex 경로는 계정 사용량 한도로 불가(21:04 이후 회복) — 세션의
  "요청 없이 Agent 도구 금지" 지시와 상충해 사용자에게 1회 확인 후 승인받아 실행(2026-08-27).
- Timestamp: 2026-08-27T08:20:00Z

### 1. Initial positions (per teammate)

- **A1 (배포 스파인·드레인 상태기계)**: P1 2 · P2 5 · P3 1. 핵심 = pin overlay 누락으로 **모든
  배포가 워커 단계에서 실패**(그 전에 구 MCP 컨테이너는 이미 삭제됨), `server_llm_blocked` 가
  라이브에서 항상 `unknown` 이라 새 브리지 분기가 죽은 코드.
- **A2 (앱 계약·SQL 의미)**: P1 2 · P2 5 · P3 1. 핵심 = reclaim UPDATE 에 **하한이 없어**
  60초보다 오래된 정상 점유까지 전부 만료(재점유되면 원 소유자 제출이 409), `wait_for_request`
  가 드레인 200 이라 어댑터가 첫 replica 에 고착.
- **A3 (토폴로지·러너, 라이브 컨테이너 실측)**: P1 2 · P2 4 · P3 1. 핵심 = **`stateless_http`
  가 v2 SDK 생성자 인자가 아니다**(`run_streamable_http_async` 의 kwarg). `TypeError` 를 WARN
  으로 삼켜 stateful 로 떴고, 2-replica LB 뒤에서 **평시에도 요청 절반이 세션 404** — 단일
  컨테이너였던 종전보다 나쁘다. 소스 문자열 검사(`"stateless_http=True" in src`)가 그 상태를
  green 으로 통과시켰다(vacuous pass).

### 2. Discussion / contradictions

- **독립 중복 지적 6건**이 신뢰도를 갈랐다: `wait_for_request` 드레인 재라우팅(A2·A3),
  `server_llm_blocked` 항상 unknown(A1·A2), `ps -q` 가드가 죽은 상대에 미적용(A1·A3),
  predrain fallback 의 fail-open(A1·A2), 드레인 누수(trap 부재)(A1·A2), lease 상수 중복(A1·A2).
- **오탐 없음으로 갈린 축**: A3 가 compose anchor 중첩 병합·`/internal/*` handle 순서·
  `ps -aq` 의미론·러너 백오프 계산식을 실제 명령(`docker compose config` 대조, `caddy adapt`,
  SDK introspection)으로 검증해 결함 아님을 확정했다. A1 도 `WAIT_PATH` 정확 일치·bash 미시
  결함·타이머 상호작용을 훑고 문제없음으로 남겼다.
- **A2 의 "submit_answer 가 드레인 503 에 걸린다"** 와 **A3 의 "대기 경로를 503 으로 통일하라"**
  는 겉보기에 반대 방향이었다. 실제로는 층이 다르다 — 들어오는 신규(대기·조사)는 돌려보내고,
  **나가는 마지막 걸음(제출·첨부 읽기)은 받는다**. 그렇게 정리했다.

### 3. Consensus — 전건 조치 (P1 6 · P2 9)

| # | 결함 | 조치 |
|---|---|---|
| P1 | stateless 인자가 v2 생성자에 없음 → 조용히 stateful | `_server_kwargs()` 로 SDK별 자리 분기(v2=run kwarg), `TypeError` 는 **기동 실패**로 격상 |
| P1 | `wait_for_request` 200 → 어댑터가 드레인 replica 고착 | 대기 경로도 503+`X-Bridge-Draining`. 계상 제외와 드레인 응답을 **분리** |
| P1 | pin overlay 에 MCP replica 없음 → 전 배포 실패 | `write_pin_overlay` 를 `WORKERS + MCP_REPLICAS` 로 |
| P1 | 엣지 전환이 MCP replica 생성보다 먼저 | `rollout_mcp_phase` 를 `reconcile_caddy` **앞**으로, sweep 은 rollout **성공 뒤**로 |
| P1 | `server_llm_blocked` 항상 unknown(`printenv` exit 1) | `${VAR-__UNSET__}` sentinel — exec 성공을 관측 성공으로 |
| P1 | reclaim 하한 부재 → 정상 점유까지 만료 | `since_epoch`(배포 창) 하한, 미지정 시 `window_sec` 로 제한 |
| P2 | `submit_answer`·`read_task_attachment` 가 503 에 걸려 답변 소실 | `DRAIN_EXEMPT_PATHS` 면제 |
| P2 | `conn is None` 미확인 + `cursor()` try 밖 → generic 500 | 가드 + try 안으로 (이 저장소 반복 결함 유형) |
| P2 | predrain fallback 이 fail-open 헬퍼 사용 | `replica_active_streams_strict` + 못 읽으면 대기 + `PREDRAIN_UNVERIFIED` 기록 |
| P2 | 드레인 누수(INT/TERM·크래시) | `DRAINED_SVC` 전역 + `on_exit_cleanup` EXIT/INT/TERM trap |
| P2 | `clear_stale_drain` 이 롤링 분기 안에만 → 같은 sha 재배포가 lame-duck 방치 | `web_skip` 판정 **앞**으로 이동 |
| P2 | reclaim 이 배포 꼬리에만 → 실패 배포에서 미실행 | web 롤링 직후로 앞당김 |
| P2 | MCP 가드가 `ps -q`(running만) | `ps -aq` + healthy 판정 |
| P2 | MCP replica 에 restart 정책 없음 | `restart: unless-stopped` |
| P2 | 유령 점유가 배포를 lease 만료까지 차단 | `bridge-activity` 가 fresh/stale 분리, 게이트는 fresh 만 |
| P2 | 러너 draining 분기 하한 없음 → RPM 소진 | `_DRAINING_RETRY_FLOOR_SEC=0.5`(백오프 아님) |
| P3 | lease 상수 중복 진실 | `_bridge_lease_minutes()` 로 정본 참조 |
| P3 | MCP 라우트 `lb_policy` 부재(random) | `ip_hash` — stateless 가 깨져도 고장이 "느려짐" 에 머물게 |
| P3 | loopback 판정에 IPv4-mapped 누락 | `_loopback_only` 로 단일화 + `::ffff:127.0.0.1` |

**테스트 vacuous pass 도 함께 해소**: stateless 는 소스 문자열 → `_server_kwargs()` **실행** +
설치 SDK 시그니처 대조로, `server_llm_blocked` 는 `printf`(exit 0) 스텁 → exec 실패/미설정
sentinel 양측으로, fallback 은 strict 스텁 2케이스(조용함/관측불가)로 바꿨다.

### 4. Dissent / residual risks

- **강행 경로는 남는다.** 상한(180s)을 넘기면 진행 중 왕복이 끊긴다. 작업은 회수로 보존되지만
  이미 쓴 토큰·조사는 버려진다 — `bridge_continuity_summary` 가 그 사실을 숨기지 않는다.
- **`read_task_attachment` 는 lease 를 검사한다**(`submit_answer` 와 달리). 회수가 실제로 발동한
  배포에서, 살아남은 소유자가 첨부를 더 읽으려 하면 409 → 재점유가 필요하다. 회수 범위를 배포
  창으로 좁혀 발생 확률을 크게 줄였고, 드레인 중 첨부 읽기는 면제했다. 완전 해소는 lease 판정에
  소유자 예외를 두는 별 cycle 의 일이다(계약 변경이라 이 cycle 에서 하지 않았다).
- **A3 P3-7**: stateful 로 뜨면 상시 SSE 스트림 때문에 `stop_grace 130s` 를 통째로 쓴다. 위 P1
  수정으로 stateless 가 실제 적용되면 자연 해소되며, `test_installed_sdk_accepts_the_flag_where_we_put_it`
  이 그 전제를 SDK 업그레이드 시점에 다시 잡는다.
- **최초 전환 배포 1회**는 구 `ext-tool-mcp` 를 정리하는 순간이 있다. rollout 을 sweep 앞으로
  옮겨 창을 최소화했으나, 그 배포에서만 개인 AI 재연결이 필요할 수 있다(이후 배포부터 무중단).

- Human Approval Needed: no
