# TODOS

이 파일은 gstack 워크플로우와의 인터페이스다. 특정 feature 에 귀속되는 작업 항목은 `unit/feature-NNNN/docs/TASK.md` 의 Task Queue 에서 관리하며, 본 파일은 **repo-level · cross-cutting · 운영 후속** 항목만 추적한다.

기록 규칙:
- 본문: 한 줄 요약 + **Why** / **Where** / **Next step** 세 보조 라인
- 상태: `[ ]` (미착수) / `[~]` (착수 중) / `[x]` (완료 — 최근 N개만 보존)
- 우선순위: `P1` (다음 세션에 반드시) / `P2` (가까운 일정) / `P3` (여력 될 때)
- feature 단위 작업은 여기에 쓰지 말고 해당 feature 의 `TASK.md` 에 기록한다

---

## Active

- [~] **P2** 리미디에이션(Task 10 #13) RAG 레이어 정리 — **(a)(b)(c) 핵심 완료**, cosmetic/dead 잔여만
  - **Why**: KB 쓰기는 TASK-0127 로 복구됐으나 retrieval 측 (a) `_load_rag_objects_for_request` 에 PG 분기 없어 항상 [](복구된 rag_objects 미사용 — D0-D3 스키마 routing 죽음), (b) "pgvector RAG" 가 실제론 trigram(임베딩 807건 NULL, 사용자 결정 B=벡터 강제활성화), (c) `knowledge.py` 3376줄 god-module + fact_entries/rag_documents 중복 + 미사용 matview.
  - **Where**: `knowledge.py`(_load_rag_objects_for_request ~1294, _load_rag_documents_for_request_pg 패턴), `kb_backend.py`(search_rag_documents 모델 → search_rag_objects 신설), `litellm_config.yaml`(임베딩 모델), `kb_embedding_worker.py`(스케줄)
  - **Next step**: ~~(a)~~ **완료 TASK-0135**: `PgKbBackend.search_rag_objects` + `_load_rag_objects_for_request_pg` + 분기(780행 검증). ~~(b)~~ **완료 TASK-0135**: titan-embed(1024d) gateway 라우트 + `<=>` 벡터-우선 읽기 + 임베딩 백필 810/810(edge400 880→0). **(c) 거의 완료**: ~~knowledge.py 분할~~ **완료 TASK-0142**(→kb_scope/kb_retrieval/kb_write + 71줄 facade, 소비처 무수정, ARCHITECTURE.md §7 갱신, 173 tests). ~~matview 폐기~~ **완료 TASK-0140**. **잔여 disposition(2026-06-04)**: (i) kb_retrieval.py 추가 분할 — **불필요**(TASK-0150 dead-code 정리로 ~1530줄 제거되어 god-module 문제 자연 해소, 라이브 entry 11개로 축소). (ii) `kb_ingest.py`(221줄) — **dead/broken**(호출처 0 + 드롭된 MySQL `AgentMemory*` 테이블 참조하는 cutover 고아). admin 진입점 배선 시 PgKbBackend 로 전환하거나, 그때까지 dead-code 로 분류(다음 dead-path 정리 패스에서 삭제 후보). (iii) MySQL fail-soft fallback 제거 — cutover 완결([[project_may27_cutover_broke_writes]]) 의존, 그 전엔 보존이 옳음.

- [x] **P3** 리미디에이션(Task 11) LLM 비용/토큰 — **회계·노출 완료(TASK-0136), 예산/캐싱은 무효 판정(현 config)** (2026-06-04)
  - **완료 (TASK-0136)**: `agent_runtime.llm_usage` + 전 LLM 호출 capture + admin 한정 `GET /api/admin/usage`(RBAC `console.usage.read`) + 콘솔 'LLM 사용량' 패널. 가시성·권한 충족.
  - **disposition — 예산/cap/캐싱/thinking-disable 미진행(실효성 없음)**: 라이브 실측(7일 llm_usage) = **100% `edge`(로컬 Ollama), Bedrock 사용 0**. 로컬 구동이라 **per-token 과금 없음** → 일일 cap/circuit-breaker/prompt-caching 의 비용 절감 가치 0. litellm thinking(16k/5k)은 미사용 Bedrock alias 에만 적용 → thinking-disable 도 N/A. 로컬 컴퓨트 부하는 사용자가 감수 결정(2026-06-04). Bedrock 전환 시 재개 — 그 전엔 항목 종결.

- [~] **P3** 리미디에이션(TASK-0143/0149 #15) alembic 마이그레이션 — **DDL 이관·라이브 stamp 완료**, 부트스트랩 제거만 잔여
  - **완료(TASK-0143)**: alembic 프레임워크 + env.py(.env AGENT_KB_PG_* 재사용) + MIGRATIONS.md.
  - **완료(TASK-0149)**: 빈 baseline → **라이브 스키마 전체 재현**(확장3+12테이블+인덱스40+(HNSW)+트리거6+FK4+함수/뷰, scratch DB 검증 차이 0). HNSW drift 정본화. **프레임워크 실동작 수정**(Dockerfile baking + `-w /app` — 이전엔 이미지 미포함으로 프로덕션 미동작). **인증 모델 대응**: postgres superuser=로컬 trust 소켓 전용 → `bin/alembic-migrate.sh`(offline `--sql`→postgres 소켓 적용, 인증 변경 0). 라이브 `agent_kb`→`0001_baseline` stamp 완료, `make migrate*` 동작 검증.
  - **부트스트랩 제거 disposition — 의도적 보류(현행 공존 유지)** (2026-06-04): `_ensure_pg_schema()` 부트스트랩 DDL 은 `IF NOT EXISTS` 멱등이라 **harmless backstop** 이고, 제거하면 fresh-deploy 가 기동 전 `make migrate` 선행에 의존하게 되어(웹 컨테이너는 privileged 소켓 미접근) **deploy 계약이 바뀌는데 기능 이득은 0**. alembic 이 versioned 정본(이미 확정)이고 부트스트랩은 런타임 안전망으로 공존 — 제거는 deploy-시퀀스 재설계 동반 시에만. **결론: 이관의 실효(versioned 정본+라이브 stamp+동작하는 make migrate)는 완료, 부트스트랩 제거는 ROI 음수라 의도적 보류.**
  - **나머지 후속**: MySQL `agent_memory` 별도 alembic 환경(별 사이클). `make migrate-new` autogenerate 는 target_metadata 미정의라 빈 revision 수기 작성만(현 운영엔 충분).

- [x] **P3** 리미디에이션(TASK-0138 #7) planner.py + phantom AGENT_* 플래그 정리 **완료**
  - **해결**: call-graph 도달성 분석으로 `planner.py`(2276줄) 라이브 미도달 확인 후 `from .planner import *` 제거 + 파일 삭제. phantom `AGENT_*` 18개(소비처 0) 삭제, 라이브 소비 플래그는 보존. CODEBASE_MAP 의 `agent_cli` "primary source" 오표기 → agent_core 정정. import smoke + 167 tests + 라이브 ask 통과.
  - ~~잔여: 죽은 소비 함수 7개~~ **완료 TASK-0150**: 7개 소비 함수 + 전이 고아 클러스터 제거(llm/sql_ops/kb_retrieval/kb_write/render/schema, **-2860줄**). grep+fixpoint 로 dead 전수 검증(라이브/테스트/타모듈 참조 0), import OK + ruff + 177 tests + 라이브 ask 회귀 0.

- [x] **P2** 리미디에이션(TASK-0137 #8) os.environ 첨부 채널 → contextvar 전환 **완료**
  - **해결**: 첨부 메타(ids/new_ids/inline image·text path)를 프로세스 전역 os.environ → run_agent 의 요청별 `contextvars.ContextVar`(allowlist 패턴과 동형, `asyncio.to_thread` 가 context 복사 전파)로 전환. app.py 의 env set/pop 전부 제거 + run_agent kwarg 전달. ctx 미설정(CLI/테스트) 시 `_ctx_or_env` 로 env fallback(하위호환).
  - **검증**: `asyncio.to_thread` 동시 2요청이 각자 첨부만 read(A=11,12/new12, B=21,22,23/new23 교차오염 0) + env fallback PASS, ruff/160 tests + 라이브 ask(첨부 없음 경로) error='' 정상.

- [~] **P2** 리미디에이션(#9) async 핸들러 동기 DB I/O — **핸들러 offload 30건 완료**, [B] 22건 잔여
  - **풀 결론(TASK-0144)**: db.py opt-in 커넥션 풀 출하(기본 OFF, +6 테스트). canary 실측 — 풀 ON=ask당 신규 conn **16** vs OFF=**2**. 기존 connect 패턴이 이미 lean, 풀은 eager pool_size 생성으로 **악화** → **무익, 기본 OFF 유지**. pgbouncer 는 PG 측 이미 사용 중.
  - **핸들러 offload(TASK-0148, 완료)**: await 0(동기 DB I/O 만)인 async 핸들러 **30건 → `def` 전환**(Starlette anyio threadpool). 느린 쿼리 1건이 이벤트 루프를 stall 시키던 핫스팟 제거, 동작 무변경(잃을 await 없음). ruff/177 tests + 라이브 6엔드포인트 200 검증.
  - **[B] disposition — 미진행(실효성<위험)** (2026-06-04): body-파싱 22건은 `await request.json()`(루프-안전, 빠른 non-blocking) 후 **단일행 write**(brief). [A] 무거운 read(SELECT)가 이벤트-루프 stall 의 실병목이었고 그게 TASK-0148 로 해소됨. [B] 의 brief write 를 to_thread 로 추출하는 것은 루프-블로킹 절감이 미미한 반면, auth/account mutation 핫패스(login/signup/admin update 등)의 핸들러별 본문 추출이라 **회귀 위험이 이득을 상회**. [C](ask/upload/ask_result)는 이미 적정 async. **결론**: #9 의 실효 부분(풀 진단 + [A] offload)은 완료, [B]/[C]/ask-conn-lifecycle 은 부하테스트·staged rollout 전제라 보류가 옳음 — 항목 실질 종결.

- [x] **P2** 리미디에이션(TASK-0141 #10) app.py silent except 가시화 **완료(판단 기반)**
  - **해결**: except 364건 전수 분류 후 명백한 fail-open swallow(bare `pass`) **26건**만 `logger.warning(exc_info=True)`로 가시화(PG 듀얼라이트/첨부 cascade/audit dispatch/best-effort enrichment 등 — 조용한 cutover 회귀·orphan 탐지 가치). **333건은 의도된 제어흐름**(멱등 ALTER, cleanup-of-cleanup, parse-후-default, 재시도 루프)이라 보존 — 로깅 시 노이즈/동작 위험. **동작 무변경**(제거 26줄 전부 bare pass, 제어흐름 라인 0) diff 확약 + ruff/compile 통과.

- [x] **P2** 리미디에이션(TASK-0139 #11) CI 격리 8건 테스트 정비 **완료 — deselect 8→0**
  - **해결**: 실제 실패 원인이 "라이브/PATH 환경 의존"이 아니라 **stale 결함**임을 실행근거로 규명·수정. anchor S6=matview DDL marker 미반영(matview 폐기로 시나리오 제거), N1=`_FakeCursor` rowcount/lastrowid 미구현(fixture 보강), m5_cleanup 6건=`kb-cleanup-mysql.sh` 의 `set -euo pipefail`+`.env` grep rc=2 조용한 종료(`|| true` 무해화). 전부 환경 비의존, deselect 0. **167 passed/0 deselected**.

- [x] **P2** gstack 후속: `/setup-deploy` 배포 파이프라인 — **결정: 미도입(현행 유지)** (2026-06-04)
  - **결정**: 운영 환경이 단일 docker host(로컬)이므로 `/setup-deploy` 불필요. 배포 표준 = `make up`/`make web` + (스키마) `make migrate`. CI 성장 또는 다중 호스트 전환 시 재평가. 본 repo 조치 없음 — 항목 종결.

- [x] **P3** 원본 GitHub repo `msmckimgpt-tech/ai_desk_mysql.git` 처리 — **결정: 사용자 외부 조치(본 repo 무관)** (2026-06-04)
  - **결정**: origin 은 이미 `gstack_dba_ai_assistant.git` 로 전환 완료. 구 repo archive/README 안내는 **GitHub UI 에서 사용자만 가능**(에이전트 권한 밖). 본 repo 내 코드/문서 조치는 없음 — TODOS 추적 종결(사용자 재량 항목).

- [x] **P3** CHANGELOG.md 생성 — **결정: 미도입(현행 유지)** (2026-06-04)
  - **결정**: 변경 이력은 `docs/STATUS.md`(정본) + `unit/feature-NNNN/docs/REPORT.md` + 커밋 메시지로 추적(CLAUDE.md 규약). 이중 기록 회피 위해 CHANGELOG 미도입. 외부 tagged release 이벤트 발생 시 재검토 — 항목 종결.

- [x] **P3** docs/LEARNINGS.md 와 gstack `/learn` 분리 정책 — **결정: 정책 확정** (2026-06-04)
  - **결정**: 프로젝트 의사결정·설계 판단 = `docs/LEARNINGS.md`(LRN-id), 스킬 운영 노하우 = gstack `~/.gstack/projects/*/learnings.jsonl`. 중복 시 LEARNINGS.md 우선. 실제 충돌 사례 발생 시 갱신 — 정책 확정으로 항목 종결.

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
