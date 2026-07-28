---
run_at: 2026-07-28T18:20:00+09:00
session: ai/claude/feature-0030-cyvol-postverify
scope: cyvol scope-prefetch 수정 POST-DEPLOY — 라이브 스코프 sync 오류 소실 재확인 (feature-0030)
verdict: PASS
---

# Run — cyvol scope-prefetch POST-DEPLOY (Environment: CLI + 라이브 배포본)

## 1. 배포

PR #1022 머지(main `44fe939d`) → `bin/deploy-web.sh`(전체 스코프: web 롤링 + 워커 + gateway
reconcile), **soak 통과**. `deploy_scope: included`(FIRST_REQUEST.md 전역 사전 승인) 근거로 confirm
없이 진행하고 착수 시 1줄 표면화했다.

| 컨테이너 | GIT_COMMIT |
|---|---|
| `repo-web-a-1` / `repo-web-b-1` | `44fe939d` |
| `repo-ask-worker-1` / `repo-insight-worker-1` | `44fe939d` |

`metadata_graph.py` 는 워커(sync)와 web(그래프 조회 API) 양쪽이 쓰므로 `--web-only` 가 아니라 전체
스코프로 롤아웃했다.

## 2. 오류 소실 재확인 (수정 전/후 대조)

`bash bin/routine-backfill.sh --scope mysql-ddae8975d793` (스코프 지정 = 결함이 항상 발동했던 경로):

| 신호 | 수정 전 (image `96dfdbdd`) | 수정 후 (image `44fe939d`) |
|---|---|---|
| sync_graph 리포트 | `errors=6` — `routine_prefetch: SyntaxError syntax error at or near ":"` 포함 | **`errors: []`** |
| 워커 로그 `routine_prefetch`/`syntax error` | 발생 | **0회** |
| 스코프 backfill exit | 0 (fail-safe 폴백) | 0 |

**silence ≠ success 방지**: "오류가 없다"만으로 끝내지 않고 ① 리포트의 `errors` 배열이 실제로 빈
리스트인지 ② 워커 로그에 해당 문자열이 0회인지 ③ 데이터가 온전한지를 각각 확인했다.

- mysql-local scope `ROUTINE_USES` **601 엣지** / 그중 `ref_columns` 보유 **370** — 데이터 무손상.
- 스코프 backfill 연속 2회 실행 → `with_cols` **257 불변**(멱등).

## 3. 커버리지 변화 (귀속 분리 — 정직 표기)

배포 창 전후 실측:

| 지표 | 배포 전 | 배포 후 |
|---|---|---|
| `routine_objects` 중 `cols` 보유 | 5,807 | **7,377** |
| AGE `ROUTINE_USES` 중 `ref_columns` 보유 | 2,725 | **9,269** |
| `cols` 보유 scope 수 | 5 | **8** |

**이 증가를 본 수정 단독의 효과로 주장하지 않는다.** 같은 창에서 세 가지가 함께 작용했다 —
① 전 datasource backfill 재실행 ② 새 이미지의 insight-worker cadence 진행 ③ 본 수정(스코프 sync 의
차수 선조회 복구). 기여 분리는 측정하지 않았다.

## 4. 미해결 관측 (§8.1 기록만 — 원인 미확정)

17:06 의 1차 전체 backfill(수정 전 image `96dfdbdd`) 이후 `mysql-local` 의 `with_cols` 가 **6 으로
불변**이었는데, 수정 후 같은 datasource 를 스코프 지정으로 돌리자 **257** 이 되었고 즉시 재실행에도
불변이었다. 확인된 사실만 적는다:

- `routines.py`(파서)는 두 이미지 간 **바이트 동일** — 파서 변화는 원인이 아니다.
- 본 결함(차수 선조회)의 실패 경로 `rollback()` 은 **그래프 sync 자신의 커넥션**에만 작용하고,
  `routine_objects` 는 `introspect_and_store` 가 별도 KB 커넥션으로 쓴다 — 코드 독해상 이 결함이
  `cols` 미persist 의 원인일 수는 없다.
- 유력 후보는 **`introspect_and_store` 의 예외 삼킴**이다(docstring: "예외는 삼켜서 0/부분 카운트
  반환(insight 루프 비차단)"). 1차 전체 backfill 은 27 datasource 동시 처리 + AGE deadlock 관측의
  고부하 창이었고, 컬럼 인벤토리 조회(`_fetch_columns`)가 전이적으로 실패하면 **커버리지가 조용히
  줄어든 채 exit 0** 이 된다. 즉 "부분 성공"과 "완전 성공"이 리포트에서 구분되지 않는다.
- **1차 전체 backfill 의 리포트가 유실**되어(백그라운드 실행의 stdout 캡처가 0 바이트) per-(ds,
  schema) 카운트·errors 를 사후 확인할 수 없었다. 2차는 `tee` 로 보존했다(`stored_total=1082`,
  `errors=21` — 전부 미도달/권한).

→ 개선 후보(미실행): `introspect_and_store` 가 컬럼 인벤토리 실패를 반환값·리포트에 구분 신호로
남기게 하고, backfill 리포트에 per-schema `cols` 채움 수를 포함. 본 cycle 범위 밖이라 기록만 한다.

## 5. 한계

- 스코프 sync 1건(`mysql-ddae8975d793`)으로 확인했다. 27 datasource 전체의 스코프 경로를 각각
  재확인하지는 않았다 — 결함은 `scope_key is not None` 이면 항상 발동하는 결정론적 문법 오류였고
  라이브 PG ground-truth 로 두 형태를 직접 대조했으므로 scope 값에 의존하지 않는다.
- UI 표면 변경 0 — PB-0008 Windows-browser 대상이 아니다(verify-completion check #13 skip).
- 같은 리포트의 `rag_table`/`relationship` step `Entity failed to be updated: 3` ·
  `DeadlockDetected` 는 여전히 남아 있다(별개 클래스, 본 cycle 범위 밖).
