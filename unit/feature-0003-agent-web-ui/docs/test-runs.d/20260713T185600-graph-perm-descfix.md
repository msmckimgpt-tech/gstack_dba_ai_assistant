---
run_at: 2026-07-13T18:56:00+09:00
session: graph-perm-descfix (ai/claude/feature-0003-graph-perm-descfix)
scope: 부트스트랩 robustness — seed catchup 1406(Description 255자 초과) hotfix
verdict: PASS
---

### Run (2026-07-13) — graph-perm-descfix: seed catchup 1406 hotfix — **Environment: agent-container pytest (--no-deps) + 배포 후 라이브 로그/DB 실증(예정)**

- **적발(배포 후 실증)**: graph-perm-split(PR #765, main b2e86880) 무중단 배포 후 `agent_memory.WebSchemaMigrations` 미존재(ERROR 1146) 확인 → backfill 미실행. web-a 로그: `[web.startup] seed catchup skipped: 1406 (22001): Data too long for column 'Description' at row 1`.
- **근본원인**: `WebPermissions.Description` = VARCHAR(255)인데 `kb.ingest.manual` 설명이 301자 → `_ensure_permission_catalog` INSERT 1406 → `_ensure_seed_catchup`(fast path) try/except 로 전체 skip → `_ensure_seed_roles`·backfill 미실행.
- **영향 실측(라이브 MySQL)**: 묶음 보유 role 중 graph.read 없는 role = **없음**, 묶음 ALLOW override 계정 중 graph 없는 계정 = **0**. 전 role 중 묶음 보유는 admin 뿐(has_bundle=1·has_graph=1). → **그래프 접근 상실 사용자 0명**.
- **수정 검증(agent 컨테이너, env 중립화)**: py_compile OK · feature-0003 전체 스위트 PASS(회귀 0) · 전 permission description ≤255·label ≤128 AST 전수 확인(잘림 0).
- **배포 후 재실증(예정, 완료 판정)**: web 재배포 후 (1) web 로그에서 `seed catchup skipped` 소멸, (2) `agent_memory.WebSchemaMigrations` 에 `graph-perm-split-v1` row 존재, (3) 묶음 보유 principal 의 graph.read 획득(현재는 admin 뿐이라 no-op 이나 마커로 재실행 차단 확정).
- 결과: 코드/단위 검증 PASS · 라이브 재실증 배포 후.
