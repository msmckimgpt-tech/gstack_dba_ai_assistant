---
doc_type: TASK
feature_id: feature-0016-metadata-graph
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 0. 맥락
- REQ-20260630-metadata-graph (FUNCTION.md §2). 사용자 결정 A3(AGE 즉시 도입)·한 묶음·신규 feature-0016.
- 등급: **Critical** (운영 PostgreSQL 커스텀 이미지 + 그래프 마이그레이션 + 무중단 배포 영향).
- RFC: 세션 아티팩트 "메타데이터 지식그래프 아키텍처" (v2-data-grounded).

## 1. Phase 0 — AGE 인프라 토대 (de-risk, worktree-local 비파괴) ✅ PASS (2026-06-30)
- [x] T0.1 `docker/Dockerfile.pg-age` — base `pgvector/pgvector:pg16` 위에 Apache AGE
      `release/PG16/1.6.0` 소스 빌드 + `make install` + 툴체인 purge. (이미지 496MB, ~4분)
- [x] T0.2 격리 컨테이너 검증: AGE 1.6.0 `create_graph` + Cypher CREATE/MATCH (Table/Column/REFERENCES).
- [x] T0.3 공존 회귀 0: pgvector 0.8.2 (vector+ivfflat+cosine) + pg_trgm 1.6 (GIN+similarity) = AC-1 PASS.
- [x] T0.4 REPORT.md 기록 완료. **발견: `shared_preload_libraries='age'` 필수**(비superuser LOAD 불가).

## 2. Phase 1 — 그래프 스키마 + 동기화 + 엣지 적재 (한 묶음 핵심)
### 2a. 스키마 (alembic, agent_kb) ✅ PASS (2026-06-30)
- [x] T1.1 alembic 0025 `20260630_0025_age_metadata_graph.py`: `CREATE EXTENSION age` +
      `create_graph('metadata_kb')` 멱등 + **vlabel/elabel 13개 사전선언**(동적 라벨 회피) +
      role-guarded GRANT. downgrade=`drop_graph`. throwaway 검증: 적용+멱등+RBAC PASS.
- [x] T1.2 라벨/속성 규약(FUNCTION.md §4) + RBAC 검증: rw 쓰기 ✓ / ro 읽기 ✓ / ro 쓰기 차단(permission denied) ✓.
      **앱 코드는 `SET search_path = ag_catalog,"$user",public` (LOAD 없이) — shared_preload 의존.**
      create_vlabel/elabel 은 `(cstring,cstring)` 시그니처(변수 `::cstring` 캐스트 필수).
### 2b. 동기화 (관계형 SSOT → AGE 투영) ✅ 모듈 PASS (2026-06-30)
- [x] T1.3 `modules/metadata_graph.py` — sync_table/column/relationship/glossary + sync_graph(전체) +
      투영(search_nodes·neighborhood). 멱등 MERGE, Cypher injection 방어(_cq), 화이트리스트 라벨/속성,
      8K 보호 cap. 라이브 AGE 행위검증 PASS(test_metadata_graph_age.py): 멱등·한국어·k-hop·injection.
- [ ] T1.4 `bin/metadata-graph-sync.sh` (run + rebuild) + insight-worker 주기 훅. 〔다음〕
### 2c. 엣지 적재 (빈 table_relationships 채우기)
- [ ] T1.5 FK introspection 실제 실행 경로 점검·기동 (20 datasource). 적재량 telemetry.
- [ ] T1.6 대화 JOIN 학습 훅 활성 확인(feature-0013 재사용). FK 미선언 DB 대비 LLM 관계 추론 seed(gated).

## 3. Phase 2 — 그래프 투영 API
- [ ] T2.1 `modules/metadata_graph.py` 조회부: Cypher 로 (a) 검색(이름/설명 부분일치)
      (b) 노드 k-hop 이웃 → `{nodes[],edges[]}`. 상한(노드/엣지 cap)·전체덤프 금지.
- [ ] T2.2 엔드포인트 `GET /api/admin/metadata/graph?q=&node=&depth=` (RBAC `kb.ingest.manual`,
      audit, ds-scope cascade). app.py(feature-0003).
- [ ] T2.3 단위/계약 테스트 (cap·scope 격리·빈 그래프 graceful).

## 4. Phase 3 — 통합 그래프 UI (Cytoscape)
- [ ] T3.1 `static/vendor/cytoscape.min.js` vendoring (mermaid 패턴 동형) + 무결성 주석.
- [ ] T3.2 admin.js/admin.html: 메타데이터 탭에 **그래프 뷰** 추가(평면 list-detail 과 토글).
      노드 클릭 → **통합 엔티티 카드**(테이블 설명 + 컬럼 목록·설명 + 관계 엣지 + 관련 용어).
- [ ] T3.3 검색창 → 투영 API 연동, 결과 노드 중심 이웃 렌더, 이웃 확장(expand) 인터랙션.
- [ ] T3.4 8K 노드 대비: 검색/이웃 스코프 강제(전체 렌더 금지), 빈 그래프·로딩·실패 graceful.

## 5. Phase 4 — AI 정합
- [ ] T4.1 `_build_knowledge_context`(agent_core): 질문 관련 엔티티를 그래프에서 **묶어 주입**
      (테이블+컬럼+관계+용어 한 블록), datamark 유지. 기존 7블록과 정합/중복제거.
- [ ] T4.2 (컨텍스트 초과 해소) AI tool `graph_navigate` — 제한된 Cypher/이웃 조회 tool 추가
      (read-only, 화이트리스트). 게임 용어 기반 질의에서 관련 서브그래프 자율 탐색.
- [ ] T4.3 KB 회귀 스위트 통과 + 신규 단위.

## 6. Phase 5 — 측정 + 배포
- [ ] T5.1 ITEM-01 eval harness A/B(그래프 컨텍스트 on/off) — 임베더/bedrock-auth 복구 전제. 수치 기록.
- [ ] T5.2 `make test` 전체 회귀 progress-char 대조.
- [ ] T5.3 **운영 cutover (게이트)**: docker-compose postgres/postgres-replica `image:` 를 커스텀 AGE
      이미지로 교체 + **`command:` 절에 `-c shared_preload_libraries='age'` 추가(서버 재시작 — load-bearing,
      Phase 0/1a 검증)** + alembic 0025 + 그래프 rebuild + web 재빌드. **1줄 게이트 표면화 + 롤백 플랜**
      (이미지 revert + 그래프 drop, 관계형 SSOT 무변경). pgbouncer/replica 호환 + replica 의 shared_preload 정합 확인.
- [ ] T5.4 PB-0008 라이브 브라우저 검증(그래프 UI) + canary.

## 7. 검증 게이트 (각 Phase 공통)
- 적대 패널: backend/security/qa (AGE Cypher 인젝션·RBAC·scope 격리·확장 공존 회귀).
- `bin/verify-completion.sh --pre-commit feature-0016-metadata-graph`.
- migrate-lint (expand/contract, CONVENTIONS §12) — AGE 마이그레이션 비파괴 확인.

## 8. 리스크 / 비고
- R1: AGE 소스 빌드 실패/PG16 비호환 → Phase 0 에서 조기 발견. 실패 시 사용자에 A2 재제안.
- R2: 커스텀 이미지 cutover 가 무중단 배포(feature-0014)와 충돌 → Phase 5 게이트에서 정합·롤백 필수.
- R3: 8K 노드 그래프 UI 성능 → 검색/이웃 스코프로 제한(전체 렌더 금지).
- R4: FK 미선언으로 엣지 희소 → 대화 학습·LLM 추론으로 점진 보강(엣지 0 이어도 노드 그래프는 가치).
