---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260630-0001 — 적대적 코드 리뷰 (backend+security 렌즈, Phase 1c~4 diff)
- Related Change: feature-0016 커밋 306f19c·bbafb52·08621f0·209e09b·0250fc4 (AGE 그래프 토대~AI tool).
- 방식: §18.8 적대 패널 — Cypher/SQL injection·RBAC·XSS·graceful·migration·logic 6 카테고리 정밀 감사.
- 결과:
  - **BLOCKER B1 — Cypher dollar-quote breakout 인젝션**: `_cypher` 가 본문을 정적 `$$…$$` 로 감싸고
    `execute(f"…")` 에 바인드 파라미터가 없어(simple protocol = 다중 statement 허용), 값에 `$$` 가
    섞이면 외곽 SQL 탈출 → 임의 SQL(DROP/UNION exfil). 도달: search `q`(admin HTTP + AI tool)·node key·
    저장된 description(sync 시 stored injection). **→ 수정**: `_cypher` 가 query 에 없음이 보장되는
    동적 dollar-tag(`$mdgq…$`) 사용 + `_cq` single-quote 이스케이프(이중 방어). 회귀 테스트 추가
    (sentinel DROP 시도 차단 + `$$` 값 무손상 저장·검색) — PASS.
  - MINOR M1(confidence nan/inf → 유효 Cypher 아님): `math.isfinite` 가드 추가. **수정**.
  - MINOR M2(neighborhood 의 key 없는 노드 → phantom None 붕괴): `if not b_key: continue`. **수정**.
  - MINOR M3(`_unwrap` 부분 이스케이프): `json.loads` 디코드(+fallback). **수정**.
  - CLEAN: RBAC(엔드포인트 kb.ingest.manual·읽기전용), XSS(admin.js 전 필드 esc()+style 은 고정 dict),
    graceful degradation(AGE 부재 시 no-op), migration 0025 멱등·SSOT 무손상·role-guard, depth/limit 정수강제.
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. 라이브(cutover 후) 엔드포인트·UI·AI tool e2e 는 PB-0008 게이트.
- Open Questions: 없음.
- Human Approval Needed: Phase 5 운영 cutover(비가역 prod 이미지 교체) — 사용자 승인 게이트(RUNBOOK-cutover.md).

## REV-20260701T120000-ai-claude-feature-0016-graphux5 [AGENT-TEAM: PASS] — graphux5 그래프뷰 UX 4항목 적대 리뷰
- Related Change: feature-0016 graphux5 (검색 유사도 명시·AI 능동분석 재귀/백그라운드·컬럼 즉석 introspection·이웃깊이 즉시 갱신). 파일: metadata_graph/node_analysis/llm/insight.py, app.py, admin.js/html, styles.css, alembic 0026, config.py.
- 방식: §18.8 적대 패널 — Workflow 로 5렌즈(backend-correctness/security/api-contract/frontend/migration-db) 병렬 리뷰 → 발견 16건 → 발견별 적대 검증(refute-default) → 확정 10건.
- 결과 (확정 10건 전량 수정):
  - **HIGH — stale 'running' 잡 미회수**: 워커 크래시/SIGTERM 시 running 갇힘 → run 영구 미완료 + enqueue dedup 이 그 run 을 계속 재사용 → 재트리거 영구 불가. **→ 수정**: process_pending 시작에 lease(`AGENT_NODE_ANALYSIS_LEASE_SEC`=900s) 초과 running→pending reaper + enqueue dedup 을 `updated_at > now()-lease` run 만 재사용.
  - **MEDIUM — node_budget 비원자 read-modify-write**: 다중 워커/replica 동시 처리 시 예산(LLM 비용) 초과 enqueue. **→ 수정**: `_enqueue_neighbors` 를 run 행 `FOR UPDATE` 트랜잭션으로 원자화(락 보유는 짧음 — LLM 은 밖).
  - **MEDIUM — enqueue 서버 실패 400 오분류**: PG 미가용/enqueue 실패가 4xx. **→ 수정**: 서버 실패 503, 입력오류만 400.
  - **MEDIUM — 폴 단일 오류 시 영구 중단**: 일시 오류 1회로 폴 루프 종료. **→ 수정**: catch 에서 bounded 재시도(≤240).
  - **LOW ×6**: get_run_status 404/503 혼동(폴 재시도로 완화), 중복 폴 취소(`activeRunId`), stale 검색 % 라벨/배지 정리(`lastQuery` gate + relLabel 제거), 컬럼 재-introspect 방지(`introspected` Set + anchorHasCols), 폴 캡 도달 안내, `scope_key` [:96] 절단. 전량 수정.
- Verdict: PASS — 확정 결함 잔여 0(전량 수정 후 py_compile 6파일·`node --check admin.js`·`migrate-lint --base main`(0026 expand-safe) 재검증 PASS). 라이브 e2e(그래프뷰 4항목)는 PB-0008 배포 후.
- Human Approval Needed: 없음(비파괴 추가 alembic 0026·기존 RBAC kb.ingest.manual 재사용, 파괴적/인증 변경 0). 배포는 deploy_scope: included(1줄 게이트 표면화).
