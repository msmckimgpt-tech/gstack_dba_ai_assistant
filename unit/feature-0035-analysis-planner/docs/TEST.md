---
doc_type: TEST
feature_id: feature-0035-analysis-planner
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

1. **결정성** — 같은 상태에서 같은 순서. 입력 순서를 뒤집어도 동일 결과.
2. **신호 우선순위** — 대화 조인 이력 > 관계 차수.
3. **스키마 축** — `object_key` prefix + `strpos` + `DISTINCT`.
4. **비용 유계** — 스키마당·사이클 2중 상한, 큐잉 재구현 없음.
5. **fail-soft** — 선정 실패·설정 부재가 insight 스캔을 막지 않는다.

## 2. 자동 테스트 — `tests/test_analysis_planner.py` (28건)

| 축 | 케이스 |
|---|---|
| A 결정성 | 순서 무관 동일 결과 · limit · 빈 입력 |
| B 신호 | 대화 이력이 차수 30 을 이김 · 차수 정렬 · 대소문자 · 미지 테이블 0점 · 양방향 집계 · conversation 분리 계수 |
| C 스키마 | `object_key` prefix(schema_name 미사용) · **LIKE 미사용** · **DISTINCT** · 분석 완료 제외 · 후보 상한 · node_key 형식 |
| D 안전 | 조회 실패 fail-soft · 잘못된 입력 단락 · 후보 0 시 신호 쿼리 생략 · 설정 불가 시 비활성/0 · **사이클 상한 배선** · 사이클 상한 ≥ 스키마당 상한 |
| E 배선 | 큐잉 재구현 부재(`enqueue_change_analysis` 사용) · 구조 변경 없는 분기에서만 · fail-soft · 연결 해제 |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. insight 로그에서 `분석 우선순위 선정 … 최고점=N` · `커버리지 시드 … 시드=M status=running` 확인.
2. 사이클 1회당 시드 총합이 `CYCLE_CAP` 이하인지 — 스키마 여러 개를 도는 사이클에서 확인
   (여기가 이번 리뷰의 P1 이었다).
3. 시드된 테이블이 실제로 중요도 상위인지 표본 확인 — 대화에서 조인된 이력이 있는 테이블이
   먼저 뽑혔는가.
4. 며칠 후 커버리지 재측정(11.9% 대비 증가) + 클러스터 요약의 `analyzed_count` 분포 개선 확인.
