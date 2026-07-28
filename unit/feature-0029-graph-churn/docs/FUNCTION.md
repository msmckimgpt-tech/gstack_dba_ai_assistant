---
doc_type: FUNCTION
feature_id: feature-0029-graph-churn
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
메타데이터 그래프 incremental sync 의 **churn 감쇠**(근절 아님 — §18.8 도전 수용). 30분 cron 이 매번
관계 수백~수천 건을 AGE 로 재투영하던 원인 3종(값 무변경인데 `updated_at` 전진 · status
왕복 · 공유 정점 중복 MERGE)을 제거한다. 그래프 신선도·자기교정 semantics 는 보존한다.

## 2. Goal
- REQ-20260728-graph-churn: 그래프 sync 부하 감쇠 (사용자 지시 2026-07-28 "그래프 sync churn 감쇠 진행").
  - AC-20260728T140000-graph-churn-1 (**a**): 관계 upsert·신호 write-back 이 **그래프에 보이는
    값**(cardinality/confidence/weight/status 등)이 실제로 바뀔 때만 `updated_at` 을 전진시킨다.
    `table_relationships` 트리거도 값 변경 시에만 갱신(`set_updated_at_if_changed`, alembic 0046) —
    rotation-only UPDATE(`last_validated_at` 만 바꾸는 프로브 neutral·backoff)가 sync 대상에서 빠진다.
  - AC-20260728T140000-graph-churn-2 (**b**): status 전이에 히스테리시스 — trusted 는
    `_TRUST_EXIT`(0.70) 아래로 내려가야 강등, broken 은 `_BREAK_EXIT`(0.30) 이상이어야 부활.
    승격/파단 임계(0.85/0.15)와 분리해 왕복(flap)을 차단한다. **가치 정정(§18.8)**: 신호
    1건마다 weight 가 움직여 어차피 재투영되므로 (b) 의 churn 기여는 사실상 0 — 실제 가치는
    **UI 실선/점선 표시의 의미론적 안정성**(145회 왕복하던 참인 관계가 안정)이다.
  - AC-20260728T140000-graph-churn-3 (**c**): 프로브 write-back 이 `broken` 행을 부활시키지
    않는다(`allow_revive=False`) — 무방향 중복 행을 통한 교차오염 차단. 대화 JOIN 학습(실행
    성공=강한 증거)은 종전대로 부활 허용.
  - AC-20260728T140000-graph-churn-4 (**e**): 한 sync 실행 안에서 공유 정점(Table/Schema)과
    그 엣지를 중복 MERGE 하지 않는다 — 관계당 cypher 11회 → 대개 1~3회.

## 3. In Scope
- `modules/relationships.py`: upsert `updated_at` 조건화, 신호 write-back 조건화, 히스테리시스
  상수·상태머신, `allow_revive` 게이트(프로브 3 호출부).
- `modules/metadata_graph.py`: `_anchor_seen_cache` + `_anchor_relationship_column` 중복 제거.
- alembic 0046: `set_updated_at_if_changed()` + `table_relationships` 트리거 교체(expand-safe).

## 4. Out of Scope
- 무방향 중복 행 dedupe(라이브 1,181 그룹·7,663행) — 별도 데이터 위생 cycle.
- sync 대상에서 weight-only 변경 제외(lever d) — (a)(b)(e) 적용 후 잔여량 실측 뒤 판단.
- `AGENT_XDS_RELATIONSHIP_INFER_AUTO=1` 의도 확인, stale watermark(mssql-06656002eda6) 조사.
- **잔여 churn 의 절반은 범위 밖**(§18.8 도전 3): 신호 경로(2h 1,181행)는 weight 가 매번
  바뀌므로 어떤 조건화로도 안 줄고, 진짜 lever 는 (d) weight-only 제외 + 무방향 중복 dedupe
  (신호가 중복 행에 2배 기록)다. 본 cycle 이 줄이는 것은 **rotation-only + 값 무변경 upsert**.

## 6. Outputs
- `artifacts/metadata-graph/cron.log` 의 `relationships`/`relationships_deleted`/`duration_ms`
  감소(feature-0026 M4 계측). AGE cypher 호출량·WAL 생성량 동반 감소 기대.

## 8. Edge Cases
- 정점 캐시는 **커서(=sync 실행) 수명** — 실행 간 오염 없음. 캐시가 스킵하는 MERGE 는 불변
  식별 속성만 쓰는 것이라(description/source/ordinal 미SET) 결과 동일.
- broken 행이 `updated_at` 을 더 이상 밀지 않으면 파단 시점 1회만 삭제된다 —
  `delete_relationship` 은 멱등이고 일 1회 `--full` sync 가 회수한다.
- 히스테리시스는 파단을 1주기 늦출 수 있으나 down>up 비대칭(자기교정 방향성)은 불변.
- **broken 은 사실상 흡수상태**(§18.8): LLM 컨텍스트 제외(`_fetch_relationships`) + 프로브
  부활 봉인(c) + 부활 밴드(b)가 겹쳐, 오파단 회수의 현실적 수단은 **관리자 큐레이션**
  (`admin_metadata` trust/break)과 사람이 그 JOIN 을 실제 실행하는 대화뿐이다.
- **증분 self-heal 상실**: 종전엔 churn 덕에 실패 행이 30분 뒤 자동 재시도됐다. (a) 적용 후
  per-row `errors` 행의 변경은 일 1회 `--full`(04:17)까지 최대 ~24h 누락될 수 있다.

## 10. Dependencies
- feature-0026 계측(duration_ms·churn 관측), feature-0016 그래프. deploy_scope: included.
