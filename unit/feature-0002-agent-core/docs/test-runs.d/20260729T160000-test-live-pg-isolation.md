---
run_at: 2026-07-29T16:00:00+09:00
session: ai/root/test-live-pg-isolation
scope: make test (컨테이너 전체 스위트 — feature-0002 + feature-0003 + feature-0023)
verdict: PASS
---

# Run — TASK-20260729T160000-test-live-pg-isolation

## Environment

- 하네스: `make test` (agent 이미지 격리 컨테이너, `--no-deps` + `TEST_ISOLATION_ENV`)
- worktree: `.worktrees/test-live-pg-isolation`, `COMPOSE_PROJECT_NAME=repo`
  (worktree 기본 프로젝트명은 별도 네트워크를 만들어 DNS 실연결 판정이 달라진다)
- 라이브 스택: 기동 상태 (pgbouncer·postgres-replica 도달 가능) — **격리가 작동해야 하는 조건**

## Before (main, 2baf8de2)

```
13 failed
  test_attach_inline_honesty.py           4건
  test_attachment_idor.py                 4건
  test_attachment_user_version_context.py 5건
```

전부 라이브 PG 실접속으로 fake conn 이 무시된 결과. 단독 실행에서도 동일 재현(순서-의존 아님).

## 대조 실험 (원인 확정)

| 조건 | 결과 |
|---|---|
| main 그대로 | 13 failed |
| 라우팅만 `mysql` 중립화 | 13건 소멸, 신규 실패 0 |
| PG 포트만 차단 | 13건 소멸, **라이브 PG 의존 2건 노출** (`test_routine_dbanalysis` · `test_item11_batch8_update_conv_product`) → 2 failed / 2974 passed |

두 실험이 같은 원인을 양방향으로 지목. 노출된 2건 중 `test_routine_dbanalysis` 는 테스트가 아니라
코드 결함(연결 저하 계약 위반)이라 함께 수정.

## After (본 cycle)

```
2976 passed, 2 skipped, 37 warnings — 0 failed
```

2회 연속 동일 수치. `make test` 종료코드 0. ruff: All checks passed.

## 판정

PASS — 기준선 13건 → 0건. 신규 실패 0. 라이브 데이터플레인 도달면(MySQL·PG·스냅샷·라우팅)이
하네스(1차)와 루트 `conftest.py`(2차) 양쪽에서 차단되어, 인프라 기동 상태와 무관하게 결정적.
