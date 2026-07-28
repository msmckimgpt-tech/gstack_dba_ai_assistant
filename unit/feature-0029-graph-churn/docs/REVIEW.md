---
doc_type: REVIEW
feature_id: feature-0029-graph-churn
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260728T140500-ai-root-graph-churn 설계 판단 근거
- Related TASK: feature-0029-graph-churn / Timestamp: 2026-07-28T14:05:00Z
- **왜 (a) 가 1순위**: 실측상 churn 의 63%가 값 무변경 행이다. 신선도를 전혀 거래하지 않고
  (값이 같으면 그래프도 같다) 사라지는 순수 낭비 — 리스크 대비 효과가 압도적.
- **트리거를 `to_jsonb` diff 로**: 컬럼 목록을 하드코딩하면 신규 컬럼 추가 시 비교 누락으로
  조용히 churn 이 부활한다. `updated_at`/`last_validated_at` 만 제외하는 방식이 미래 안전.
  적용 범위는 `table_relationships` 트리거만 — 다른 테이블의 `set_updated_at()` 불변.
- **히스테리시스 폭 선정**: `_TRUST_CEIL - _TRUST_EXIT = 0.15 > _NEG_STEP(0.14)` — 음성 1회로
  trusted 가 깨지지 않는 최소 폭. `_BREAK_EXIT=0.30` 은 양성 1회(0.12→0.25)로는 못 넘고 2회면
  넘는 값 — 학습 능력은 유지하되 즉시 왕복만 차단.
- **(c) 를 rid 기반 재작성 대신 게이트로**: `apply_relationship_signal` 의 다방향 갱신(추론
  A→B + 대화 B→A 동시 갱신)은 **의도된 설계**다. rid 한정으로 바꾸면 그 의도가 깨진다 —
  broken 부활만 막는 최소 게이트가 정확한 수술.
- **(e) 캐시를 커서에 부착**: 전역 캐시는 실행 간 오염(그래프 재생성 후 정점 부재인데 캐시
  히트) 위험. 커서 수명이 sync 실행과 정확히 일치.
- 사전 승인: deploy_scope: included. migrate-lint PASS(expand-safe). PB-0008 비대상.

## REV-20260728T233000-ai-root-graph-churn [AGENT-TEAM: SHIP-WITH-FIXES]
- **Related Change:** feature-0029 (CHG-20260728T140500). **Panel:** §18.8 backend/data-integrity
  렌즈(라이브 PG·컨테이너 실증 동반). **Verdict:** BLOCK → 전 결함 in-cycle 수정 후 SHIP.
- **Timestamp:** 2026-07-28T23:30:00Z

### 수용·수정한 결함 (전건 라이브 실증 기반)
- **[B-1, 치명]** 정점 캐시가 **프로덕션에서 100% 비활성** — `psycopg.Cursor.__slots__ == ()`
  라 커서 속성 부착이 항상 AttributeError(라이브 insight-worker 실증). fake 커서 테스트만
  통과해 드러나지 않았다. **FIX:** 캐시를 **명시 파라미터**(`new_anchor_cache()` →
  `sync_relationship(cache=...)`)로 전환 + `__slots__` 스텁 회귀 테스트 + **라이브 이미지
  실증**(관계 3건 cypher 유발 15→9, Table MERGE 1회).
- **[B-2, 치명]** alembic 0046 트리거가 `positive_signals`/`negative_signals` 를 diff 에 포함해
  파이썬 측 `_graph_changed` 를 **매번 덮어씀** → 신호 경로(라이브 2h churn 의 54%)는 조건화가
  무효. **FIX:** 트리거 제외 목록에 신호 카운터 2종 + `source_run_id` 추가하고, **트리거를 단일
  정본**으로 선언 — upsert 의 20줄 CASE와 `_graph_changed` 분기 **삭제**(중복 정책 제거).
- **[B-3]** upsert 비교 튜플이 `source_run_id` 누락인데 주석은 "전량"이라 주장(라이브 63개 run
  으로 회전 — 순수 no-op upsert 가 churn 유발). **FIX:** B-2 의 트리거 단일화로 해소 +
  배포 후 `alembic_version` 확인을 TASK 체크리스트에 추가(stale image 전례).
- **[B-4]** 캐시가 rollback 을 무효화하지 않아, 활성화되는 순간 SAVEPOINT 롤백된 정점을
  "있다"고 속여 후속 `_merge_edge` 가 **조용히 0행**(엣지 소실). **FIX:** pending/committed
  2단 캐시 — 행 성공 시 commit, 실패 시 drop, 배치 롤백 시 reset + 각 경로 테스트.
- **[락 창]** 0046 에 `SET LOCAL lock_timeout='5s'` 추가 — 41분 `--full` sync 와 겹칠 때
  마이그레이션이 writer 를 줄세우지 않고 짧게 실패(배포 재시도가 처리).
- **[도전 수용]** (b) 히스테리시스의 churn 기여는 사실상 0 → 가치를 "UI 표시 안정성"으로 정정.
  "churn 근절" → **"churn 감쇠"** 로 범위 정직화(신호 경로 절반은 (d)+dedupe 소관).
  broken 흡수상태·증분 self-heal 상실을 FUNCTION §8 에 명시.
- **[검증 서사]** 신규 16건 PASS 상태에서 B-1/B-2 가 성립했으므로 "테스트 통과 = AC 달성"을
  쓰지 않는다 — 라이브 타입/라이브 PG 실증을 근거로 병기한다.

### 패널이 결함 없음으로 확증
(b) status 도메인(DB CHECK 제약으로 소문자 3값 — 빈/NULL 분기 도달 불가, trusted 영구 고착
없음), (c) 생성 SQL 문법·파라미터 순서·NULL 삼킴 없음, 마이그레이션 단일 트랜잭션(무트리거 창 없음).
