---
doc_type: RUNBOOK
feature_id: feature-0016-metadata-graph
status: draft
edit_policy: rewrite
---

# RUNBOOK — Apache AGE 운영 cutover (Phase 5)

> **상태: 미실행 (cutover 직전 준비물).** 운영 PostgreSQL 이미지 교체는 비가역·외부영향이라
> 사용자 승인 게이트 + 롤백 플랜과 함께 별도 진행한다. 본 문서는 정확한 절차·검증·롤백을 사전 명세한다.
> Phase 0~4 (이미지 빌드·그래프 스키마·동기화/투영 모듈·API·UI·AI tool) 는 검증 완료.

## 0. 사전 조건
- [ ] Phase 0~4 머지 완료(feature-0016 PR).
- [ ] **백업 선행** (feature-0015 자산): `bin/backup.sh` 로 postgres-data 스냅샷 + `bin/restore-rehearsal.sh`
      로 복원 리허설 PASS 확인. (cutover 는 DB 이미지 교체라 데이터 보존이 최우선.)
- [ ] 커스텀 이미지 빌드 확인: `sudo docker build -f unit/feature-0016-metadata-graph/docker/Dockerfile.pg-age
      -t <prod-tag> unit/feature-0016-metadata-graph/docker/` (또는 compose `build:` 등록).
- [ ] 유지보수 창(짧은 PG 재시작 — feature-0014 무중단은 web 계층, DB 재시작은 순단 발생 가능).

## 1. compose 변경 (postgres + postgres-replica 동시)
docker-compose.yml 의 **세 pgvector 서비스 중 KB primary·replica** (postgres, postgres-replica):
- `image: pgvector/pgvector:pg16` → 커스텀 AGE 이미지(또는 `build:` Dockerfile.pg-age).
- `command:` 의 server params 에 `-c shared_preload_libraries='age'` 추가
  (기존 shared_preload 값이 있으면 콤마 병기: 예 `'age,pg_stat_statements'`).
- **primary 와 replica 가 동일 이미지·동일 shared_preload** 여야 streaming replication 정합(replica 도 age 로드).
- pgbouncer 는 변경 없음(앱→pgbouncer→postgres 경로 유지). pgbouncer transaction-mode 안전성은 마이그의
  `ALTER ROLE ... SET search_path` 가 보장(Phase 4 검증).

## 2. 적용 순서 (순서 중요)
1. [ ] compose 변경 반영 + **postgres·postgres-replica 재생성**:
       `sudo docker compose up -d --no-deps postgres postgres-replica`
2. [ ] AGE 로드 확인: `sudo docker compose exec postgres psql -U postgres -d agent_kb -c
       "SHOW shared_preload_libraries;"` → `age` 포함. replica 도 동일 확인.
3. [ ] **alembic 0025 적용**: `bin/alembic-migrate.sh`(또는 프로젝트 표준) — CREATE EXTENSION age +
       create_graph('metadata_kb') + 라벨 13 + GRANT + ALTER ROLE search_path. 멱등.
4. [ ] `.env` 에 `AGENT_METADATA_GRAPH_SYNC_ENABLED=1` 추가 → 워커·web 재시작 반영
       (ask-worker/insight-worker/web). **이때 web 도 재빌드**(Phase 2/3 코드 baked):
       `sudo docker compose build web && sudo docker compose up -d --no-deps web-a web-b`
       (feature-0014 롤링: deploy-web.sh 사용 권장).
5. [ ] **초기 그래프 적재**: `bash bin/metadata-graph-sync.sh` (전체 scope 투영). telemetry 확인
       (tables/columns/relationships/glossary 카운트).

## 3. 검증 (배포 후)
- [ ] API: `GET /api/admin/metadata/graph?q=<테이블명>` → nodes 반환(관리자 세션).
- [ ] UI(PB-0008, 실제 Windows 브라우저): 관리콘솔 > 메타데이터 > 🕸 그래프 뷰 → 검색 → 노드 클릭 →
       이웃 확장 + 통합 엔티티 카드(설명·컬럼·관계·용어) 렌더. mermaid 처럼 vendored 동작.
- [ ] AI: flow/관계/구조 질문 → assistant 가 `graph_navigate` 호출(대규모 스키마 subgraph) → 정확 응답.
- [ ] 회귀: `make test` 전체 + 기존 pgvector/pg_trgm 경로(KB 검색·임베딩) 무회귀.
- [ ] replica RO 경로(`_pg_connect_ro`)로 그래프 read 동작(투영 API 가 replica 사용).

## 4. 주기 동기화 (cron, cutover 후) ✅ 설치됨 (2026-06-30)
- [x] `bin/install-metadata-graph-sync-cron.sh` (feature-0015 backup-cron 동형) — 매 30분
      `bin/metadata-graph-sync.sh` 실행. 관계형 SSOT 변경(설명 편집·FK introspect·대화학습 엣지)을
      그래프에 반영. 멱등(MERGE)이라 중복 무해.
- **⚠️ 반드시 `sudo`(root crontab)로 설치**: 이 호스트는 일반 사용자에게 docker 소켓 접근이 없어
  (permission denied) user cron 은 docker exec 실패. root crontab 에서만 동작(backup cron 과 동일).
  설치: `sudo bin/install-metadata-graph-sync-cron.sh` · 제거: `sudo … --remove`.
- 로그: `../artifacts/metadata-graph/cron.log`. 검증: root 컨텍스트 sync 1회 PASS(153 tables, 0 errors).

## 5. 롤백 (문제 시)
관계형 SSOT 는 **무변경**이라 그래프만 되돌리면 됨:
1. [ ] `.env` `AGENT_METADATA_GRAPH_SYNC_ENABLED=0` → 워커/web 재시작 (graph_navigate·sync no-op).
2. [ ] (선택) 그래프 제거: alembic downgrade 0025 (`drop_graph('metadata_kb', true)`) — 확장은 보존.
3. [ ] (필요 시) compose 이미지 라인 revert(`pgvector/pgvector:pg16`) + shared_preload 제거 →
       `sudo docker compose up -d --no-deps postgres postgres-replica`. AGE 확장은 이미지에서만 사라지고
       관계형 데이터·pgvector·pg_trgm 무영향(데이터는 동일 PGDATA).
4. [ ] web 은 graph 서브탭이 빈 그래프로 graceful(투영 API 503/empty) — 치명 아님.
> AGE 확장이 설치된 PGDATA 를 구 이미지(age 없음)로 기동 시 `shared_preload_libraries='age'` 가 남아
> 있으면 기동 실패 → 롤백 시 compose 의 shared_preload 도 함께 제거할 것.

## 6. 리스크 체크리스트
- [ ] replica shared_preload 누락 → replica 기동 실패. (primary·replica 동시 변경 필수.)
- [ ] PGDATA 에 age 설치 후 구 이미지 기동 + shared_preload 잔존 → 기동 실패. (롤백 §5-3 주의.)
- [ ] 8K 노드 초기 sync 시간 — bin/metadata-graph-sync.sh 가 수 분 소요 가능(워커 1회 실행, 비차단).
- [ ] WAL/디스크 — AGE 라벨 테이블 + 인덱스 추가분(노드/엣지 수 대비 소량).
