---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: backend-correctness
timestamp: 2026-06-12T00:00:00Z
trigger: schema/query keyword matched (coverage 계산 SQL·멀티 datasource 격리) — backend/qa dispatch (§18.8)
verdict: CONCERN
---

### 1. Blocking issues

(no findings)

### 2. Cross-domain concerns

- **동명 DB 멀티-datasource 이중 카운트 (흡수 완료)**
  - Evidence: `order = [r["schema_name"] for r in db_rows]` 는 중복 제거가 없고 `per_db_by_name` 은 DB명 단일 키 dict 라, 같은 schema_name 이 서로 다른 datasource_key 그룹에 등록되면(멀티 datasource 의 정상 시나리오 — 같은 'dbCommon' 이 여러 서버에 존재) 합산 루프가 그 DB 를 두 번 순회해 total_objects/analyzed_objects/connected_count 가 이중 계상되고 per_db 에도 동일 행이 두 번 노출된다.
  - Location: unit/feature-0003-agent-web-ui/src/app.py:14402 (합산 루프 `for db in order:`)
  - Reason: pct = analyzed/total 분수가 동명 DB 수만큼 부풀려져 완료율이 실제보다 왜곡된다. 멀티 datasource(1:N) 가 본 TASK 의 핵심 시나리오라 동명 DB 충돌 가능성을 무시할 수 없다.
  - Action: 합산 루프에 `seen_dbs: set` 가드를 추가해 동일 DB명을 한 번만 집계·노출하도록 수정(이미 흡수 — `if db in seen_dbs: continue; seen_dbs.add(db)`). 회귀 테스트 599 passed 무회귀 재확인.

### 3. Challenge to current spec

- 혼합 engine(MySQL+MSSQL 동시 바인딩) 시 top-level `base["engine"] = engines_seen[0]` 는 dict 순회 첫 값일 뿐 대표성이 없다. per_db 행은 그룹별 정확한 engine 으로 계산되므로 **계산은 정확**하고 표기만 오해 소지 — 저위험. 단일 datasource 는 항상 1엔진이라 무회귀. 후속에서 `len(set(engines_seen))>1` 시 "mixed" 표기 고려(이번 cycle 범위 외).
- 한 그룹의 PG 통찰 조회 실패 시 `pg_failed=True; break` 로 전역 측정 불가 처리(이미 쌓인 정상 그룹 결과 폐기). PG 단일 연결이라 한 scope 실패는 연결/쿼리 전반 문제일 확률이 높아 방어적으로 합리적 — 부분 가시성보다 데이터 무결성 우선. 회귀 아님.
- `_analyzed_sets_for_scope` 내부 `pgc = pg.cursor()` 는 예외 시 cursor 미닫힘 가능성이나, 호출부 `except: pg_failed=True; break` → finally `pg.close()` 로 connection 이 항상 닫혀 psycopg2 가 cursor 를 회수 → 실 fd/connection 누수 없음. 위생 개선(`with pg.cursor()`)은 후속.

### 4. Verdict

CONCERN — BLOCKER 0. 핵심 버그 2개(① 멀티 datasource datasource_key 별 그룹핑, ② db.py `LOWER(TABLE_SCHEMA)` 대소문자 매칭)는 올바르게 해결됐고 단일 datasource 무회귀·datasource 격리(각 그룹이 자기 coords/scope 만 사용 → cross-datasource 누수 없음)·SQL injection 무표면(LOWER 변경이 bound param 유지)·pg 연결 finally close 는 PASS. §2 의 동명 DB 이중 카운트 1건을 머지 전 흡수(seen_dbs 가드) → SHIP. 나머지 challenge 는 저위험 후속.
