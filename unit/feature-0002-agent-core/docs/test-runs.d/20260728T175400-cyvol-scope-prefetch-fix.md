---
run_at: 2026-07-28T17:54:00+09:00
session: ai/claude/feature-0030-cyvol-scope-prefetch-fix
scope: cyvol 차수 선조회 cypher 조립 결함 — scope 술어 위치 수정 회귀 잠금 (feature-0030)
verdict: PASS
---

# Run — cyvol scope-prefetch cypher 문법 결함 (Environment: CLI + live PG ground-truth)

## 0. 발견 경로 (라이브)

`bin/routine-backfill.sh` 전 datasource 실행(2026-07-28 17:0x, routine-column-edges POST-DEPLOY)
리포트에 다음이 남았다:

```
WARNING metadata_graph sync_graph partial: errors=6 …
  'routine_prefetch: SyntaxError syntax error at or near ":"
   LINE 1: ...utine) WHERE r.scope_key = \'mssql-ba175631e9fc\'-[u:ROUTINE_U...'
```

## 1. 근본 원인

`metadata_graph.py` 의 cyvol 선조회는 scope 술어를 **문자열 fragment 로 만들어 노드 패턴 직후에
고정 보간**했다. 서명 쿼리는 패턴이 노드 하나뿐이라 유효했지만, 차수 쿼리는 그 뒤에 관계 패턴이
이어져 `WHERE` 가 패턴 **중간**에 들어갔다.

```
# 수정 전 (scope_key='ds-x')
MATCH (r:Routine) WHERE r.scope_key = 'ds-x'-[u:ROUTINE_USES]->() RETURN r.key, count(u)
                                             ^ openCypher 문법 위반
# 수정 후
MATCH (r:Routine)-[u:ROUTINE_USES]->() WHERE r.scope_key = 'ds-x' RETURN r.key, count(u)
```

`scope_key is None` 인 경로만 술어가 빈 문자열이라 유효했다 → **모든 per-datasource sync** 의
차수 선조회가 도입 이래 항상 실패했다.

## 2. 영향 (정직 표기 — 정합성 아님, 최적화·부하)

실패 시 `except` 가 `_deg_by_key` 를 빈 dict 로 두므로 `_routine_edges_intact` 가 차수 0 ≠ 기대치로
판정해 **전량 재작성**(= 최적화 이전 동작)으로 강등된다. 즉 **fail-safe** 이며 그래프 최종 상태는
옳았다. 실질 손실은 셋이다:

1. 스코프 sync 에서 cyvol W2(ROUTINE_USES 전량 DELETE+재MERGE 감축, 실측 전체의 32%)가 통째로 무효.
2. §18.8 패널이 B3 로 요구한 "서명 동일 + 엣지 소실" 재조정 안전망이 스코프 경로에선 차수 판정
   없이 보수적으로만 동작(= `--full` 보장이 사실상 전량 재작성으로 대체).
3. 예외 경로가 매 스코프 sync 마다 `rollback()` + `anchor_cache_reset()` 를 1회 유발 — 그 시점의
   미커밋 정점 마크가 폐기돼 재-MERGE 가 추가로 발생.

## 3. 검증

### 3.1 결함 재현 (수정 전 FAIL — 역검증)
신규 테스트 3건을 먼저 넣고 **수정 없이** 실행:

```
FAILED test_scoped_degree_prefetch_cypher_is_wellformed
FAILED test_scoped_prefetch_result_actually_skips_rewrite
2 failed, 32 passed
```

기존 32건은 전부 통과했다 — **기존 스위트가 이 결함을 구조적으로 놓쳤음이 실증된다**. 원인은
기존 `test_sync_graph_prefetch_is_scope_filtered` 가 **서명 쿼리만**(유효한 쪽) 검사했고, mock
커서가 파서가 아니라 malformed cypher 를 그냥 삼켜 "선조회 결과가 소비되는 것처럼" 보였기 때문이다.

### 3.2 하네스 보강 — mock 이 PG 를 대신 거부한다
`_assert_cypher_parses(sql)` 를 `_SyncCur.execute` 에 배선했다. cypher 본문을 dollar-quote 에서
추출해, 한 절의 `WHERE` 이후 `RETURN` 전까지 구간에 관계 패턴(`-[`)이 나타나면 거부한다
(openCypher 의 `WHERE` 는 패턴 전체 뒤에만 올 수 있다). 이 가드가 있어야 3.1 의 두 번째 테스트가
**행위 수준**에서 결함을 잡는다 — 문자열 단정만으로는 "그 문장이 라이브에서 죽는다"를 표현할 수 없다.

### 3.3 라이브 PG ground-truth (proxy ≠ ground-truth, §16.3)
하네스 판정을 신뢰하지 않고 실 PG/AGE(`repo-postgres-1`, `metadata_kb`)에 두 형태를 직접 던졌다:

| 형태 | 결과 |
|---|---|
| 수정 전 | `ERROR: syntax error at or near ":"` / `LINE 3: ...utine) WHERE r.scope_key = 'mysql-ddae8975d793'-[u:ROUTINE_U...` — **라이브 리포트와 문구 동일** |
| 수정 후 | 실제 행 반환 (`"mysql-ddae8975d793:account_db.SP_ACC_BAN_PLAYER()" | 1` 등 4행) |

### 3.4 회귀
- `test_graph_cypher_volume.py` + `test_routine_column_refs.py` + `test_routine_sync_crossdb.py`
  **86 PASS / 0 FAIL**.
- feature-0002 전체 스위트를 **main 기준선과 동일 하네스로 2회 실행해 실패 집합을 대조**:
  base 32 / fix 32, **차집합 양방향 0** — 신규 회귀 0. 32건은 전부 src·tests·shared 만 마운트한
  실행 레이아웃 artifact(`bin/` 스크립트·repo 문서 부재로 `FileNotFoundError`)이며 본 변경과 무관하다.

## 4. 한계

- 본 Run 은 CLI + 라이브 PG 문법 검증이다. **UI 표면 변경 0**(백엔드 sync 경로만)이므로 PB-0008
  Windows-browser 검증 대상이 아니다 — verify-completion check #13 도 web 자산 미변경으로 skip.
- 배포 후 라이브 재확인(스코프 sync 리포트에서 `routine_prefetch` 오류 소실)은 워커 이미지 재배포가
  선행되어야 하므로 POST-DEPLOY 항목으로 남긴다.
