# TODOS

이 파일은 gstack 워크플로우와의 인터페이스다. 특정 feature 에 귀속되는 작업 항목은 `unit/feature-NNNN/docs/TASK.md` 의 Task Queue 에서 관리하며, 본 파일은 **repo-level · cross-cutting · 운영 후속** 항목만 추적한다.

기록 규칙:
- 본문: 한 줄 요약 + **Why** / **Where** / **Next step** 세 보조 라인
- 상태: `[ ]` (미착수) / `[~]` (착수 중) / `[x]` (완료 — 최근 N개만 보존)
- 우선순위: `P1` (다음 세션에 반드시) / `P2` (가까운 일정) / `P3` (여력 될 때)
- feature 단위 작업은 여기에 쓰지 말고 해당 feature 의 `TASK.md` 에 기록한다

---

## Active

- [ ] **P2** 리미디에이션(Task 10 #13) RAG 레이어 정리 — 3개 분리 작업
  - **Why**: KB 쓰기는 TASK-0127 로 복구됐으나 retrieval 측 (a) `_load_rag_objects_for_request` 에 PG 분기 없어 항상 [](복구된 rag_objects 미사용 — D0-D3 스키마 routing 죽음), (b) "pgvector RAG" 가 실제론 trigram(임베딩 807건 NULL, 사용자 결정 B=벡터 강제활성화), (c) `knowledge.py` 3376줄 god-module + fact_entries/rag_documents 중복 + 미사용 matview.
  - **Where**: `knowledge.py`(_load_rag_objects_for_request ~1294, _load_rag_documents_for_request_pg 패턴), `kb_backend.py`(search_rag_documents 모델 → search_rag_objects 신설), `litellm_config.yaml`(임베딩 모델), `kb_embedding_worker.py`(스케줄)
  - **Next step**: ~~(a)~~ **완료 TASK-0135**: `PgKbBackend.search_rag_objects` + `_load_rag_objects_for_request_pg` + 분기(780행 검증). ~~(b)~~ **완료 TASK-0135**: titan-embed(1024d) gateway 라우트 + `<=>` 벡터-우선 읽기 + 임베딩 백필 810/810(edge400 880→0). **(c) 거의 완료**: ~~knowledge.py 분할~~ **완료 TASK-0142**(→kb_scope/kb_retrieval/kb_write + 71줄 facade, 소비처 무수정, ARCHITECTURE.md §7 갱신, 173 tests). ~~matview 폐기~~ **완료 TASK-0140**. **잔여(후속)**: kb_retrieval.py(2170줄) 추가 분할 여지 + admin-only `kb_ingest.py` PG 전환 + MySQL fail-soft fallback 경로(cutover 완결 시 제거 — [[project_may27_cutover_broke_writes]] 의존).

- [~] **P3** 리미디에이션(Task 11, 후순위) LLM 비용/토큰 회계 + 예산/레이트리밋 — **회계·노출 완료 TASK-0136**, 예산/캐싱 잔여
  - **Why**: 사용자 지정 후순위. ~128 step frontier 호출에 토큰 회계/계정별 cap/circuit breaker 없음. 활성 고장 아닌 운영·비용 가시성 강화.
  - **완료 (TASK-0136)**: `agent_runtime.llm_usage` 테이블 + 전 LLM 호출 사이트(메인 루프 + 7개 direct-create) capture + admin 한정 `GET /api/admin/usage`(RBAC `console.usage.read`, 비인증 401·authed admin 200+집계 검증) + admin 콘솔 'LLM 사용량' 패널(권한 게이트). UX 노출 범위·권한 충족.
  - **잔여 (P3)**: LiteLLM per-key budget + 계정별 일일 토큰 cap/circuit breaker(비용 **제어**), prompt caching, topic/summary/classify thinking 비활성 별칭. **보류 사유**: 가시성(핵심)은 출하됨, 제어/캐싱은 LiteLLM 설정 레이어 최적화로 활성 고장 아님.

- [~] **P3** 리미디에이션(TASK-0143/0149 #15) alembic 마이그레이션 — **DDL 이관·라이브 stamp 완료**, 부트스트랩 제거만 잔여
  - **완료(TASK-0143)**: alembic 프레임워크 + env.py(.env AGENT_KB_PG_* 재사용) + MIGRATIONS.md.
  - **완료(TASK-0149)**: 빈 baseline → **라이브 스키마 전체 재현**(확장3+12테이블+인덱스40+(HNSW)+트리거6+FK4+함수/뷰, scratch DB 검증 차이 0). HNSW drift 정본화. **프레임워크 실동작 수정**(Dockerfile baking + `-w /app` — 이전엔 이미지 미포함으로 프로덕션 미동작). **인증 모델 대응**: postgres superuser=로컬 trust 소켓 전용 → `bin/alembic-migrate.sh`(offline `--sql`→postgres 소켓 적용, 인증 변경 0). 라이브 `agent_kb`→`0001_baseline` stamp 완료, `make migrate*` 동작 검증.
  - **잔여(후속, 위험)**: `_ensure_pg_schema`/`agent_kb_schema.sql` 의 부트스트랩 CREATE/ALTER 를 제거하고 alembic 단독 소유로 전환(현재는 idempotent backstop 공존 — 라이브 36GB, 백업 선행). MySQL `agent_memory` 별도 alembic 환경. `make migrate-new` autogenerate 는 metadata(target_metadata) 미정의라 빈 revision 수기 작성만 지원.

- [x] **P3** 리미디에이션(TASK-0138 #7) planner.py + phantom AGENT_* 플래그 정리 **완료**
  - **해결**: call-graph 도달성 분석으로 `planner.py`(2276줄) 라이브 미도달 확인 후 `from .planner import *` 제거 + 파일 삭제. phantom `AGENT_*` 18개(소비처 0) 삭제, 라이브 소비 플래그는 보존. CODEBASE_MAP 의 `agent_cli` "primary source" 오표기 → agent_core 정정. import smoke + 167 tests + 라이브 ask 통과.
  - **잔여(후속)**: planner 를 유일 호출처로 가졌던 죽은 소비 함수 7개(llm/sql_ops/knowledge/render/schema 내, 정적 미도달)는 본 작업 범위 밖 — 별도 dead-path 정리 시 함께.

- [x] **P2** 리미디에이션(TASK-0137 #8) os.environ 첨부 채널 → contextvar 전환 **완료**
  - **해결**: 첨부 메타(ids/new_ids/inline image·text path)를 프로세스 전역 os.environ → run_agent 의 요청별 `contextvars.ContextVar`(allowlist 패턴과 동형, `asyncio.to_thread` 가 context 복사 전파)로 전환. app.py 의 env set/pop 전부 제거 + run_agent kwarg 전달. ctx 미설정(CLI/테스트) 시 `_ctx_or_env` 로 env fallback(하위호환).
  - **검증**: `asyncio.to_thread` 동시 2요청이 각자 첨부만 read(A=11,12/new12, B=21,22,23/new23 교차오염 0) + env fallback PASS, ruff/160 tests + 라이브 ask(첨부 없음 경로) error='' 정상.

- [~] **P2** 리미디에이션(#9) async 핸들러 동기 DB I/O — **핸들러 offload 30건 완료**, [B] 22건 잔여
  - **풀 결론(TASK-0144)**: db.py opt-in 커넥션 풀 출하(기본 OFF, +6 테스트). canary 실측 — 풀 ON=ask당 신규 conn **16** vs OFF=**2**. 기존 connect 패턴이 이미 lean, 풀은 eager pool_size 생성으로 **악화** → **무익, 기본 OFF 유지**. pgbouncer 는 PG 측 이미 사용 중.
  - **핸들러 offload(TASK-0148, 완료)**: await 0(동기 DB I/O 만)인 async 핸들러 **30건 → `def` 전환**(Starlette anyio threadpool). 느린 쿼리 1건이 이벤트 루프를 stall 시키던 핫스팟 제거, 동작 무변경(잃을 await 없음). ruff/177 tests + 라이브 6엔드포인트 200 검증.
  - **잔여(staged)**: [B] body-파싱 22건(`await request.json()` 후 동기 DB 작업) → async 유지 + 동기부 `to_thread` 추출 필요(핸들러별·회귀위험). [C] ask/upload/ask_result 는 이미 적정 async. ask() 커넥션 lifecycle(에이전트 실행 전 반환)은 별도·복잡. **보류 사유**: [B]/[C] 는 단위테스트로 동시성 회귀 검출 불가 → 부하테스트 필요.

- [x] **P2** 리미디에이션(TASK-0141 #10) app.py silent except 가시화 **완료(판단 기반)**
  - **해결**: except 364건 전수 분류 후 명백한 fail-open swallow(bare `pass`) **26건**만 `logger.warning(exc_info=True)`로 가시화(PG 듀얼라이트/첨부 cascade/audit dispatch/best-effort enrichment 등 — 조용한 cutover 회귀·orphan 탐지 가치). **333건은 의도된 제어흐름**(멱등 ALTER, cleanup-of-cleanup, parse-후-default, 재시도 루프)이라 보존 — 로깅 시 노이즈/동작 위험. **동작 무변경**(제거 26줄 전부 bare pass, 제어흐름 라인 0) diff 확약 + ruff/compile 통과.

- [x] **P2** 리미디에이션(TASK-0139 #11) CI 격리 8건 테스트 정비 **완료 — deselect 8→0**
  - **해결**: 실제 실패 원인이 "라이브/PATH 환경 의존"이 아니라 **stale 결함**임을 실행근거로 규명·수정. anchor S6=matview DDL marker 미반영(matview 폐기로 시나리오 제거), N1=`_FakeCursor` rowcount/lastrowid 미구현(fixture 보강), m5_cleanup 6건=`kb-cleanup-mysql.sh` 의 `set -euo pipefail`+`.env` grep rc=2 조용한 종료(`|| true` 무해화). 전부 환경 비의존, deselect 0. **167 passed/0 deselected**.

- [ ] **P2** gstack 스킬 도입 후속: `/setup-deploy` 로 배포 파이프라인 구성 여부 결정
  - **Why**: 현재 배포는 `make web` + docker compose 로컬 재빌드 중심. 공식 deploy target 이 없어 `/ship` 이후 자동화가 비어있음.
  - **Where**: repo 루트 `Makefile` + `docker-compose.yml`
  - **Next step**: 운영 환경이 단일 docker host 라면 `/setup-deploy` 를 건너뛰고 `/ship` 이후 수동 `make web` 으로 충분. CI 성장 시 재평가.

- [ ] **P3** 원본 GitHub repo `msmckimgpt-tech/ai_desk_mysql.git` 처리 결정
  - **Why**: 2026-04-23 origin 을 `gstack_dba_ai_assistant.git` 으로 전환하면서 기존 repo 가 고아 상태. 혼란 방지를 위해 README 에 이전 안내를 추가하거나 archive 처리 필요.
  - **Where**: GitHub `msmckimgpt-tech/ai_desk_mysql`
  - **Next step**: 사용자가 GitHub UI 에서 직접 README 교체 또는 archive 전환. 본 repo 내 조치는 없음.

- [ ] **P3** CHANGELOG.md 생성 필요성 재검토
  - **Why**: gstack 의 `/ship` 스킬은 CHANGELOG 를 가정하지만 본 repo 는 `REPORT.md` + 커밋 메시지로 변경 이력을 추적. 이중 기록을 피하기 위해 도입 유보.
  - **Where**: repo 루트
  - **Next step**: 외부 배포 이벤트(tagged release 등) 가 필요해지는 시점에 도입 검토.

- [ ] **P3** docs/LEARNINGS.md 와 gstack `/learn` 의 분리 정책 확정
  - **Why**: 현재 `docs/LEARNINGS.md` 가 프로젝트 고유 학습 기록(LRN-YYYYMMDD-NNNN) 을 담당. gstack 글로벌 `~/.gstack/projects/<slug>/learnings.jsonl` 과 중복 가능성.
  - **Where**: `docs/LEARNINGS.md` + `~/.gstack/projects/*/learnings.jsonl`
  - **Next step**: 원칙은 "프로젝트 의사결정·설계 판단 = LEARNINGS.md, 스킬 운영 노하우 = gstack jsonl". 실제 충돌 사례가 생기면 갱신.

## Parking Lot (feature scope 항목 포인터)

feature 단위로 관리되는 미완료 작업은 다음 위치를 참조:
- `unit/feature-0001-platform-runtime/docs/TASK.md` — TASK-0004 (엄격한 운영 검증 시나리오)
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0034 (복잡 QA 성능 테스트, 진행 중)
- `unit/feature-0004-browser-automation/docs/TASK.md` — TASK-0004 (엄격한 브라우저 시나리오)
- `unit/feature-0005-qa-mcp/docs/TASK.md` — TASK-0004 (엄격한 QA 시나리오), TASK-0005 (MCP 기동 검증)
- `unit/feature-0006-lan-proxy-access/docs/TASK.md` — TASK-0004 (엄격한 네트워크 시나리오)

전체 진행률 / 의존성 / 블로킹은 `docs/STATUS.md` 참조.

## Recently Done (최근 N개)

- [x] 2026-04-23 origin 을 `gstack_dba_ai_assistant.git` 으로 전환 + `CLAUDE.md` 에 gstack skill routing 섹션 주입 + `TODOS.md` 신설
