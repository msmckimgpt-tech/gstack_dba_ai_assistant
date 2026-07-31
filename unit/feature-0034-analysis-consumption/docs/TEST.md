---
doc_type: TEST
feature_id: feature-0034-analysis-consumption
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

1. **정직성** — 근거 수를 반드시 병기하고, 근거 0은 "추정"으로 표기한다.
2. **매칭 정확성** — 질문에 등장한 테이블만, 짧은 이름 제외, scope·schema 격리, 라벨 조회.
3. **fail-soft** — 연결·조회·테이블 부재 어느 실패도 답변을 막지 않는다.
4. **배선** — 답변 경로가 실제로 로더를 호출하고 datamark·근거 해석 지시·지연 계측을 갖춘다.

## 2. 자동 테스트 — `tests/test_cluster_grounding.py` (28건)

| 축 | 케이스 |
|---|---|
| A 정직성 | 근거 수 표기 · 근거 0 → "추정" · 길이 절단 · limit · malformed row skip · 공백 정규화 |
| B 매칭 | strpos 사용 · **ILIKE 미사용**(`_` 와일드카드 오탐) · 근거순 정렬 · 짧은 이름 제외 · scope 격리 · **schema 격리**(`(scope, schema, label)`) · **effective_schema 원본과 동형**(드리프트) · 라벨 조회(cluster_id 미사용) · 행 상한 · 매칭 0건 시 2단계 생략 |
| C fail-soft | cursor 예외 · 테이블 부재 · scope 없음 · 비활성 시 연결 미개설 · 공백 질문 |
| D 배선 | 로더 호출 · datamark · **"근거 없음은 단정 말라" 지시** · `cluster_summary_ms` 계측 · try/except |
| 지연 | `SET statement_timeout` + **`RESET` 짝**(SET LOCAL 은 autocommit 에서 무효) |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. `cluster_summaries` 에 요약이 있는 datasource 로 전환한 뒤, 그 묶음의 테이블명을 포함한
   질문을 던져 답변 컨텍스트에 `TABLE GROUP SUMMARIES` 가 실리는지 확인.
2. `duration_breakdown.init_detail.cluster_summary_ms` 실측 — 주입 전후 체감 지연 대조.
3. 근거 0 요약이 주입됐을 때 답변이 그것을 단정으로 옮기지 않는지 표본 판독.
4. 스위치를 0 으로 내리면 섹션이 사라지는지(live 반영).
