---
doc_type: REPORT
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 진행 요약 (2026-07-30)

백그라운드 LLM 토큰 예산 신규 — 구현·테스트 완료, codex 적대 리뷰 반영(P1·P2 각 1건), 배포 대기.

## 왜 이 cycle 이 생겼나

T2(합성·소비) 진입 전 게이트를 점검하다가 `TODOS.md` P3 의 종결 근거를 실측으로 확인했고,
그 전제가 **반전돼 있었다**. 종결문은 "라이브 100% edge(로컬 Ollama) → per-token 과금 없음 →
일일 cap 가치 0"(2026-06-04)이었다.

| 실측 (2026-07-30, `agent_runtime.llm_usage`) | 콜 | 토큰 |
|---|---|---|
| 최근 7일 Anthropic(claude) | 8,654 | 55,567,176 |
| 최근 7일 edge/기타 | 25 | 30,404 |
| 최근 24시간 백그라운드(예산 대상) | 1,865 | 6,847,798 |

과금 lane 99.7%. 즉 사람 confirm 없는 자동 지출에 상한이 없는 상태였다. T2 는 여기에 L2 요약을
더 얹는 트랙이라, 절대량이 작더라도 상한 없는 자동 지출을 늘리는 방향이다.

## 무엇을 만들었나 (그리고 만들지 않았나)

**만든 것**: `shared/llm_budget.py` — rolling 24시간 백그라운드 토큰 집계 + 게이트 + 콘솔 현황.

**만들지 않은 것**:
- **circuit-breaker** — `llm_provider_health` 가 이미 429/401 을 분류해 provider 를 restricted 로
  내리고 복구 probe 를 돈다. 같은 축의 두 번째 구현은 서로를 모르는 두 개의 진실을 만든다.
- **콜 수 상한** — `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP` 이 별도 축으로 담당한다. 비용은 콜이
  아니라 토큰에 비례하므로 대체 관계가 아니다.

## 설계에서 가장 중요한 한 가지

**사용자 요청 경로는 세지도 막지도 않는다.** 대화 답변·자가검증·제목 생성·원본 전환 분류는
사람이 기다리는 호출이다. 예산으로 그것을 막으면 비용 사고를 막으려다 더 큰 사고를 만든다.
이 제외가 실제 집계 SQL 에 반영되는지까지 테스트가 파라미터를 직접 검사한다 — 상수 선언만
확인하면 쿼리가 바뀌었을 때 조용히 어긋난다.

## 정직하게 남기는 한계

게이트 커버리지는 **96%** 다. LLM 호출에 단일 choke-point 가 없어(`chat.completions.create` 가
15곳에서 직접 호출된다) 백그라운드 진입점 3곳에만 게이트를 걸었고, 나머지(table/account/schema
insight)는 계량되지만 차단되지 않는다. 콘솔 수치가 "전체 소비"이고 차단이 "일부 경로"라는 사실을
코드 주석·FUNCTION·콘솔 설명에 그대로 적었다. 100%인 척하면 나중에 "상한이 있는데 왜 넘었나"라는
더 나쁜 혼란이 생긴다.

## 리뷰

codex P1 1건(**캐시 race 로 최대 60초간 예산 초과 허용**)을 single-flight 로 구조적 제거,
P2 1건(상한 0 일 때 불필요한 PG 조회) 반영. 나머지 6개 가설은 코드 근거로 반증됐다.
상세는 `REVIEW.md`.

## claude-corp 계정 사용량 관측 (사용자 요청)

계정 구분은 `resolved_model` 의 `-root` 접미로 한다 — feature-0007 의 요청-레벨 fallback 체인이
`claude-haiku-4`(claude-corp) → `claude-haiku-4-root`(root Max) → edge 순이므로, `-root` 가
붙었다는 것은 claude-corp 에서 429 를 맞고 넘어갔다는 뜻이다.

| 시점 | claude-corp 5h rolling | root(Max) fallback | 백그라운드 24h |
|---|---|---|---|
| 착수 전 | 461콜 / 3,772,469 | 0콜 | 1,865콜 / 6,847,798 |
| 구현 후 | 468콜 / 3,934,178 | 0콜 | 1,859콜 / 6,814,071 |

**root fallback 0** — 관측 구간 내내 claude-corp 이 429 를 맞지 않았다. 5시간 창 소비는
16만 토큰 증가(백그라운드 정상 동작분)로, 이 cycle 자체가 라이브 LLM 을 쓰지 않았음과 정합한다.

관측 쿼리:
```sql
SELECT COUNT(*), COALESCE(SUM(total_tokens),0) FROM agent_runtime.llm_usage
WHERE created_at > now() - interval '5 hours'
  AND COALESCE(NULLIF(resolved_model,''),model) LIKE 'claude%'
  AND COALESCE(NULLIF(resolved_model,''),model) NOT LIKE '%-root%';
```

## 남은 것

- 배포 후 콘솔 예산 막대 PB-0008 + 상한을 일시적으로 낮춰 게이트 실동작 관측(같은 창에서 대화
  답변이 정상인지 확인) → `TEST.md` §4.
- 이후 T2(ITEM-07 L2 클러스터 요약 → ITEM-08 L3 lazy → ITEM-09 grounding 배선).
