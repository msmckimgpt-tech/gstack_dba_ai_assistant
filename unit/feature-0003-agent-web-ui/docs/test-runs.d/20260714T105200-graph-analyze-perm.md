---
run_at: 2026-07-14T10:52:00+09:00
session: graph-analyze-perm (ai/claude/feature-0003-graph-analyze-perm)
scope: RBAC — AI 능동 분석 실행 권한(metadata.graph.analyze)을 조회(graph.read)에서 하위 분리 + 프론트 버튼 게이팅
verdict: PASS
---

### Run (2026-07-14) — graph-analyze-perm: AI 능동 분석 실행 하위 권한 분리 (Critical §12.3) — **Environment: agent-container pytest (--no-deps)**

- 방법: `docker compose run --rm --no-deps agent`(CI-클린 env: `AGENT_RUNTIME_READ_BACKEND=`·`AGENT_TIMEOUT_SEC=60`) + `PYTHONPATH=.../src`.
- 단위 검증:
  - `test_metadata_perm_split.py`: 신규 — **graph.read 만으론 metadata.graph.analyze 미부여**(함의/역함의 없음, A안 핵심 계약)·graph.analyze 독립부여·catalog(group=kb)·admin seed+catchup 포함·stock role 미부여. + 기존 R1~R8/R3c 유지. PASS.
  - `test_permission_dependency_map.py`: t5 — `metadata.graph.analyze → metadata.graph.read` 종속(하위)·tree depth(graph.read=0·graph.analyze=1). PASS.
- 회귀: **feature-0003 전체 스위트 PASS(회귀 0)**.
- 문법: `py_compile`(web_context.py·admin_metadata.py) OK · `node --check`(admin.js·graph-ctxmenu.js module) OK.
- backend 게이트 전수(수동 확인): 실행 POST 2개(`/graph/analyze`·`/graph/analyze-schema`)만 `metadata.graph.analyze` 로 전환. GET `/graph/analyze`·`/analyze/node`·`/analyze/status`·`/columns`·`/graph` 는 `metadata.graph.read` 유지(읽기). `relationship/curate`=`metadata.table.manage`(무관).
- frontend 게이트 전수(§18.8 MEDIUM 반영 — 게이트 분리): **실행 트리거** 5곳만 `can("metadata.graph.analyze")` 게이팅 — 노드 상세 실행 버튼/popover(`metaGraphAiBtn`·`metaGraphAiPop`, 바인딩 skip)·노드 우클릭·스키마 우클릭·combo 우클릭·클러스터 카드 버튼(`#metaGraphClusterAnalyzeBtn`, 렌더 조건 가드+바인딩 null-safe). **결과 조회는 graph.read** — 상세 패널 AI 섹션 컨테이너·결과 box(`metaGraphAiBox`)·`_metaGraphLoadNodeAnalysis`(결과 로드)는 항상 렌더(view-only 뷰어 결과 열람 보장, graph.read 설명·백엔드 GET 계약 정합).
- §18.8 보안 렌즈 적대 리뷰: MEDIUM 1건(AI 섹션 전체를 실행 게이트로 감싸 view-only 결과 조회 상실) 적발 → 게이트 분리 수정 + 회귀 테스트 `test_graph_analyze_fe_gate_split` 추가. LOW(읽기 GET 4개 docstring stale) 정정. 나머지 5축 CLEAN. VERDICT PASS(수정 후).
- 결과: 코드/단위 PASS.

### Run (2026-07-14) — 프론트 버튼 게이팅 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산 + authz 게이팅)**: 정적 자산은 이미지 baked 라 배포 후에만 라이브 반영. 게이팅 검증에 graph.read-only 계정(능동 분석 버튼 **미노출**) + graph.analyze 보유 계정(버튼 노출·실행) 테스트 계정이 배포 환경에 필요 → 배포 전 headless 로 대체 불가.
- **배포 후 계획(PB-0008)**: web 재배포 후 win-browser relay 로 https://localhost/admin 그래프 뷰 — (a) graph.analyze 미보유(graph.read-only) 계정: 노드 상세 패널에 'AI 능동 분석' 섹션·버튼 부재, 우클릭 메뉴에 'AI 능동 분석'/'DB 전체 AI 능동 분석' 부재, 클러스터 카드에 분석 버튼 부재 확인 + POST `/graph/analyze` 직접 호출 시 403. (b) graph.analyze 보유(admin) 계정: 버튼 노출·능동 분석 실행 정상. + admin catchup 실증(`WebRolePermissions` 에 admin×metadata.graph.analyze row).
- 결과: 정적 검증 PASS · 라이브 시각검증 DEFERRED(배포 후).
