---
doc_type: TEST
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: append-only
source_of_truth: true
---

# Test

## 1. Strategy

이 기능의 결함은 **조용하다** — 배포는 성공으로 끝나고, 끊긴 것은 사용자의 AI 연결뿐이다.
그래서 텍스트 단정만으로 만족하지 않고 **원문을 실행**해 게이트의 실제 행동을 본다
(`if false;` 나 상수 치환 같은 무력화는 문자열 검사로 잡히지 않는다).

계약을 네 층으로 나눈다:

| 파일 | 무엇을 지키나 |
|---|---|
| `test_bridge_drain.py` | 대기/작업의 **구분** — 합치면 배포가 멈추거나 질문이 죽는다 |
| `test_bridge_deploy_gate.py` | 스파인이 실제로 **기다리는가**(실행 검증) |
| `test_mcp_replica_topology.py` | MCP 표면이 배포를 견디는 구조인가 |
| `test_internal_endpoints.py` | 배포 제어 창구의 **경계**와 **의미** |

## 2. Cases

- 대기·작업 카운터 분리 / 예외 시 감소 / snapshot 단일 출처
- 드레인 멱등 · 해제 복구
- 미들웨어: 도구 호출 계상 · 대기 경로 제외 · 비-도구 경로 무접촉
- 드레인 중 신규 도구 호출 503 + `X-Bridge-Draining` · 대기 경로는 200 유지
- `predrain`: in-flight 대기(3회 폴링) · 대기(waiters)는 즉시 통과 · 강행 기록 · probe 실패 대체
- 드레인 probe 가 `/livez` 미사용 · recreate 실패 시 해제 · 롤링 전 청소
- 회수: 강행 시에만 · grace 창 · `ClaimedBy` 보존
- MCP: 2 replica 동일 정의 · 구 서비스 부재 · stateless · stop_grace > 중계 상한 ·
  엣지 2-upstream · active health 부재 · 어댑터 드레인 재라우팅
- quiesce: 브리지 축 포함 · `unknown` ≠ 조용함 · 브리지 운영에서 영구 차단 없음 ·
  `server_llm_blocked` 기본값(미설정 = 차단) 5케이스

## 3. Runs

### Run 2026-08-27 (Environment: repo-pytest)
- Command: `python3 -m pytest unit/feature-0045-zd-bridge-continuity/tests/ -q`
- Result: **60 passed** (적대 검증 반영 후 — 회귀 가드 10건 + vacuous pass 해소 3건 포함)
- 회귀: `unit/feature-0014-zero-downtime-deploy/tests/`,
  `unit/feature-0020-zd-deploy-all/tests/`, `unit/feature-0041-external-ai-tool-surface/tests/`,
  `unit/feature-0043-external-llm-bridge/tests/` 각각 PASS(개별 실행)

> `test_llm_gate.py` 3건은 feature-0041/0043 스위트를 **함께** 돌릴 때만 실패한다. 원인은
> `modules` 네임스페이스가 feature-0003/0002 사이에서 갈리는 기존 환경 특성이며, `main`
> 에서도 동일하게 재현된다(내 변경 이전 상태에서 확인). 정본 판정은 컨테이너 `make test`.

### Run 2026-08-27 (Environment: live-deploy) — **PASS**

배포 `e7d54f70` (scope=all). 배포 프로세스 `EXIT=0`(파이프로 가리지 않은 실 exit).

| 관측 | 결과 |
|---|---|
| `bridge_continuity_summary` | **"대기는 드레인으로 교대했고 진행 중 왕복은 완주했다(끊김 0)"** |
| pre-drain (web-a) | `active_streams=0 bridge_inflight=0, 드레인된 대기=1` → 즉시 통과 |
| pre-drain (web-b) | 동일 — 그 AI 가 web-a→web-b 로 옮겨갔다가 다시 교대(릴레이 확인) |
| MCP 롤링 중 엣지 | `POST /api/ai/mcp` → **400**(502 아님). `상대 ext-tool-mcp-b 가 서빙` 로그와 동시 관측 |
| 완결 판정 | `ext-tool-mcp-a/b = e7d54f70 (healthy)` — MCP 가 판정에 포함됨 |
| 엣지 무중단 | 배포 창 `no upstreams available` **0건** |
| 엣지 경계 | `POST /internal/bridge-drain` → **404**(엣지 차단 작동) |
| 점유 회수 | 실행 안 됨 — `PREDRAIN_FORCED=0` 이므로 평상시 no-op 설계대로 |

**직전 배포(1차)와의 대비가 이 feature 의 실증이다**: 1차에서는 상대 replica 가 구 이미지라
드레인 창구가 없어 fallback(`브리지 축은 미확인`)을 탔고, MCP 는 단일 컨테이너라 전환 중
`/api/ai/mcp` 가 502 였다. 2차에서는 양쪽 모두 신 코드라 드레인이 실제로 걸렸고, MCP 는
`상대가 서빙` 하는 채로 하나씩 교체되어 그 경로가 끊기지 않았다.

**부수 실증**: 새 `/livez` 가 `bridge_waiters: 1` 을 노출하는 동안 `active_streams` 는 0 이었다.
종전 게이트가 "조용하다" 고 읽던 바로 그 상태에서 개인 AI 한 대가 대기 중이었다는 뜻이다.

### 검증이 놓쳤던 것 (REV-20260827-0001)

초판 46건은 전부 green 이었는데 P1 6건이 살아 있었다. 세 가지가 **문자열 검사**였기 때문이다:

| 놓친 것 | 왜 통과했나 | 지금은 |
|---|---|---|
| `stateless_http` 가 v2 생성자에 없음 | `assert "stateless_http=True" in src` | `_server_kwargs()` **실행** + 설치 SDK 시그니처 대조 |
| `server_llm_blocked` 항상 unknown | 스텁이 `printf`(exit 0) 라 `printenv` 의 exit 1 경로 미실행 | exec 실패/미설정 sentinel **양측** 케이스 |
| fallback 이 fail-open 헬퍼 사용 | 스텁이 그 헬퍼를 0 으로 덮음 | strict 스텁 2케이스(조용함 / 관측 불가) |

교훈은 하나다 — **"그 이름이 소스에 있다" 와 "그 배선이 런타임에 작동한다" 는 다른 사실이다.**

## 4. Coverage Notes

- **미작성**: 실제 두 replica 를 띄운 상태의 통합 롤링 e2e. 컨테이너 오케스트레이션이 필요해
  단위 층에서 재현하지 않고, 라이브 배포의 `bridge_continuity_summary` 로 대체 관측한다.
- 드레인 중 Caddy 가 실제로 2초 안에 후보를 빼는지는 Caddy 동작이라 여기서 검증하지 않는다
  (설정값 `health_interval 2s` · `health_fails 1` 은 feature-0014 테스트가 잠근다).
