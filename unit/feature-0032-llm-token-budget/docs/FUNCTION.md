---
doc_type: FUNCTION
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function: 백그라운드 LLM 토큰 예산

## 개요

사람이 요청하지 않은 자동 LLM 지출(노드 분석·클러스터 라벨·분류 제안·insight)에 **rolling
24시간 토큰 상한**을 둔다. 상한에 닿으면 새 백그라운드 작업이 다음 주기로 밀린다.
**사용자가 기다리는 호출(대화 답변·자가검증·제목 생성·원본 전환 분류)은 세지도 막지도 않는다.**

## 1. 왜

`TODOS.md` P3 는 *"라이브 100% edge(로컬 Ollama) → per-token 과금 없음 → 일일 cap 가치 0"* 을
근거로 종결돼 있었다. 2026-07-30 라이브 재실측이 그 전제를 반전시켰다:

| 구분 | 콜 | 토큰 |
|---|---|---|
| 7일 Anthropic(claude) | 8,654 | 55,567,176 |
| 7일 edge/기타 | 25 | 30,404 |

과금 lane 99.7%. 그중 백그라운드가 약 2,600만 토큰/7일이며 상한이 없었다.

## 2. 계량

- **원천**: `agent_runtime.llm_usage` — 이미 모든 LLM 호출이 기록되는 테이블이라 새 계측이 없다.
- **창**: rolling 24시간(자정 리셋 아님). 타임존 논쟁이 없고 자정 직후 폭주 재개가 없다.
- **범위**: `USER_FACING_TASKS`(`agent`·`redteam`·`topic`·`classify`·`prompt_gen`)를 **뺀 전부**.
  블랙리스트 형태라 새 백그라운드 작업이 생겨도 자동으로 예산 안에 들어온다 — 보수적인 방향으로
  틀린다. 화이트리스트면 반대로 새 작업이 조용히 예산 밖으로 샌다.
- **캐시**: 60초 TTL. 게이트가 매 tick 마다 PG 를 때리지 않는다. 조회 실패(-1)는 캐시하지 않는다
  (일시 장애가 TTL 동안 굳지 않게).

## 3. 게이트

`shared.llm_budget.allowed()` 가 백그라운드 **진입점**에서 호출된다:

| 진입점 | 위치 | 소진 시 반환 |
|---|---|---|
| 노드 분석 tick | `node_analysis._process_pending_inner` (claim 전) | `rep["skipped"]="llm_token_budget"` |
| 클러스터 유지보수 pass | `semantic_cluster.run_cluster_maintenance` 래퍼 | `{"skipped": "llm_token_budget"}` |
| 제품 분류 pass | `product_classify.run_classify_pass` 래퍼 | `{"skipped": "llm_token_budget"}` |

노드 분석은 **claim 전**에 본다 — 잡을 집어온 뒤 막으면 그 잡이 실패·재시도를 오가며 `attempts`
만 소모한다(T0 의 LLM 슬롯 clamp 와 같은 이유).

**커버리지(정직하게)**: LLM 호출에 단일 choke-point 가 없다 — `chat.completions.create` 가
15곳에서 직접 호출된다. 위 3개 진입점이 백그라운드 소비의 약 96%(node_analysis + cluster_label)를
차지하고, 나머지(table/account/schema insight)는 **계량되지만 차단되지 않는다**. 콘솔의 수치는
"전체 소비"이고 차단은 "일부 경로"라는 사실을 숨기지 않는다.

## 4. fail-open (3중)

상한은 안전망이지 필수 경로가 아니다. 계량 장애가 기능 정지로 번지면 안 된다.

1. 상한이 0 이하면 무제한 — 소비 조회조차 하지 않는다.
2. 소비를 조회할 수 없으면(`-1`) 허용한다.
3. `llm_budget` 모듈 자체가 없으면(부트스트랩 창) 게이트 없이 종전 동작.

## 5. 상한값

`AGENT_BACKGROUND_LLM_TOKEN_CAP_24H` — 기본 **20,000,000**(콘솔 live 조절, 0=무제한).
최근 24시간 백그라운드 실측이 6,847,798 토큰이므로 기본값은 약 3배 여유다. 정상 운영에는
닿지 않고 폭주만 잡는다.

## 6. 관측

관리 콘솔 `AI 운영 현황` 에:
- **현황 막대** — `소비 / 상한` + 사용률 + 남은 여유. 80% 이상 주황, 도달 시 빨강.
- **면제 안내** — "사용자가 기다리는 호출은 이 예산에서 제외"를 화면에 명시한다. 없으면 운영자가
  "분석이 멈췄으니 답변도 멈추겠다"고 오해해 불필요하게 상한을 올린다.
- **attention** — 80% 이상 `watch`, 도달 시 `degraded`. 소진이 조용히 지나가면 "왜 분석이 안
  도나"의 답을 찾는 데 시간이 든다.
- **상태 구분** — "상한 없음"(비활성)과 "조회 불가"(계량 장애)를 다른 문구로 표시한다.

## 7. 이 기능이 하지 않는 것

- **circuit-breaker 아님** — 429/401 대응은 `llm_provider_health` 가 이미 한다(분류 → restricted
  → 복구 probe). 중복 구현하지 않았다.
- **호출 수 상한 아님** — 콜 기준 상한은 `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP` 이 별도 축으로
  담당한다. 비용은 콜이 아니라 토큰에 비례하므로 두 축은 대체 관계가 아니다.
- **사용자 요청을 막지 않음** — 이것은 성능 특성이 아니라 **설계 불변식**이다.
