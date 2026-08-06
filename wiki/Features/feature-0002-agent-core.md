---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, agent, llm, kb]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0002-agent-core
linked_unit: unit/feature-0002-agent-core
created: 2026-05-26
sources:
  - ../../unit/feature-0002-agent-core/docs/FUNCTION.md
  - ../../docs/DECISIONS.md
  - ../../docs/KB_PG_DIALECT_NOTES.md
---

# Feature — Agent Core

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0002-agent-core |
| 상태 | active |
| 정본 | [[../../unit/feature-0002-agent-core/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | agent CLI · core loop · modules · KB Postgres · insight worker |

## 1. 개요

자연어 요청을 받아 **LLM tool-call loop** (SQL 작성·실행·메모리·지식·복구) 를 수행하는 핵심 에이전트 feature. Postgres `agent_kb` (pgvector, runtime + KB 단독 정본) 위에서 step loop 가 작동하며, insight worker 가 백그라운드로 schema/table 인사이트를 캐시한다.

> **2026-06 멀티 데이터소스 시대**: 단일 MySQL replica → **N 개 데이터소스 (MySQL·MSSQL)** 동시 분석으로 일반화. dialect 추상화 + datasource registry (envelope 암호화) + DB-단위 접근 + datasource-aware insight 가 배포·라이브검증 완료. §2.5 참조.

## 2. 상세

### 2.1 책임 경계

- **입력**: 사용자 질문 + `.env` agent 설정 + MySQL/MCP 런타임
- **출력**: CLI 응답 (Rich Markdown) / Web UI JSON / 메모리·지식·로그 기록 / SQL 실행 결과
- **side-effect**: `agent_memory` MySQL DB write · `agent_kb` Postgres dual-write (M2~) · `artifacts/shared/logs/insight_worker.log` 등

### 2.2 핵심 흐름 (FUNCTION §7)

1. `agent_core.run_agent()` 진입 → OpenAI SDK client 준비 (Bedrock gateway 경유)
2. `agent_memory` 대화/메시지/KV 보장 + `origin_request` / `thread_goal` 3-state 판정
3. `_build_knowledge_context()` 로 SCHEMAS / RELEVANT TABLES 블록 주입
4. **Step Loop**: `tool_calls` 최대 3 개씩 실행 (`execute_sql` / `describe_table` / `describe_routine` / `search_tables` / `get_sample_rows`), 결과 메모리 기록. tool_calls 없으면 최종 답변.
5. 루프 상한 = `AGENT_MAX_STEPS` + `AGENT_TIMEOUT_SEC * 3`, Web UI "중단" / "즉시 답변" 감지.

### 2.3 KB 마이그레이션 (TASK-0015 M0~M5)

| Phase | 상태 | 산출 |
|---|---|---|
| M0 | done | `pgvector/pgvector:pg16` compose service standalone |
| M1 | done | `agent_kb_schema.sql` (~241 LOC, IF NOT EXISTS) + RBAC role |
| M2-a/b/c/d | done | KbBackend ABC + `_DualWriteMirror` + cross-DB audit + pg_branch xmax |
| M3 | done | `kb_backfill.py` + `kb_embedding_worker.py` ETL |
| M4 | done | FULLTEXT → pg_trgm rewrite + `AGENT_KB_READ_BACKEND=postgres` |
| M5 | window | `bin/kb-cleanup-mysql.sh` + ADR-0025 14-day monitoring |

자세히: [[../Decisions/ADR-0021-kb-postgres-rbac]], [[../Decisions/ADR-0025-m5-cleanup]].

### 2.4 RBAC role

- `agent_kb_rw` — SELECT/INSERT/UPDATE/DELETE on 4 tables + VIEW SELECT (M2+ 사용)
- `agent_kb_ro` — SELECT only (read-only audit / debug)
- Application-level: `kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export` (별 cycle)

### 2.5 멀티 데이터소스 (2026-06, TASK-0187/0205/0206/0219)

| 영역 | 메커니즘 | concept |
|---|---|---|
| dialect 추상화 | `modules/dialects/` — `Dialect` ABC + `MySQLDialect`/`MSSQLDialect` | [[../concepts/multi-datasource]] |
| 연결 라우팅 | `db.connect(datasource_key, database)` + `_DatasourceRouter` (호출 단위 lock) | [[../concepts/multi-datasource]] |
| 자격증명 저장 | `WebDatasources` + KEK/DEK envelope (`cred_crypto.py`), resolve 시 복호 | [[../concepts/datasource-registry]] |
| 접근 경계 | DB-단위 allowlist (`WebProductDatabases.SchemaName`=catalog), 시스템 DB 가시성만 | [[../concepts/db-level-access]] |
| insight 격리 | `rag_objects.datasource_key` + endpoint-hash `compute_scope_key` (라벨 rename 불변) | [[../concepts/datasource-aware-rag]] |
| 보안 게이트 | 3축 (AST allowlist · RO GRANT · sql_guard denylist), fail-closed | [[../concepts/multi-datasource]] |

- 시드 데이터 MySQL = `main_mysql` datasource. shadow flag `AGENT_MULTI_DATASOURCE_ENABLED`.
- EXPLAIN pre-gate + `MAX_EXECUTION_TIME` (DESIGN-self-interrupt → self-interrupt-lite, TASK-0172): `AGENT_QUERY_GUARD_MODE` (off/warn/gate) + `confirm_heavy` override.
- **연결 격리 + 3색 상태 (TASK-0247/0255/0282)**: per-datasource **circuit breaker** (scope_key=엔진+host+port, half-open 락내 토큰) + bounded `AGENT_DB_CONNECT_TIMEOUT_SEC`(10s, 쿼리예산 분리) 로 불안정 datasource 1개가 단일 직렬 ask-worker 를 점유하는 starvation 차단. `modules/conn_health.py` 가 2-stage probe (TCP→DB `SELECT 1`) 로 **정상/불안정/끊김** 분류 → web 작업화면·관리콘솔 노출. control-plane(memory DB) 은 breaker 미적용 (마비 방지).

## 3. 특징

- **fail-soft**: PG unavailable 시 `_pg_available()` False → MySQL only path 자연 fallback.
- **fail-loud (`AGENT_KB_PG_REQUIRED=1`)**: M2-b+ 부터 깨진 schema 위 시작 차단.
- **cross-DB audit (best-effort)**: KB mirror write 가 MySQL `WebAuditEvents` 에 `kb.write.mirror` row append.
- **`pg_branch` tag**: `RETURNING id, (xmax = 0)` 패턴으로 INSERT vs UPDATE 구분 — `_pg_op_local` threadlocal capture.
- **insight worker fail-safe**: heartbeat stale 시 `_should_run_inline_insight_scan()` 가 인라인 scan 트리거.
- **insight 효율·안정성 (2026-07-03, 정본 REPORT — 비사용자향)**: ① 동일구조 테이블 그룹화(insight-table-grouping) — 날짜/번호 suffix 만 다른 샤드를 (base_stem, fingerprint)로 묶어 **대표 1회 LLM 분석 + 형제 LLM-free fan-out**(신규 일자 샤드는 KV 상속으로 LLM 0), per-table `table_insight` fact 유지로 NL→SQL 무회귀. ② 부하 분산(insight-load-spread, cross-feature 0016) — 실패 대상 격리·재시도 backoff + graph sync batched commit/incremental(57,000+ 요소 개별 MERGE WAL fsync ~5.7만 → ~114). ③ healthcheck false-negative 해소(insight-heartbeat-liveness) — 긴 cycle 중 진행-중 heartbeat throttle 갱신. ④ 요청레벨 LLM fallback(claude-corp→root→edge gemma, 정본 feature-0007).
- **read-only 도구·가드 확장 (2026-07-13, conversation_audit 발)**: 저장 프로시저/함수 정의 조회 전용 도구 **`describe_routine`** 신설(`SHOW CREATE PROCEDURE` 를 execute_sql 로 실행하다 보안 가드에 차단되던 마찰 해소·사용자 승인 Option 1) + **sql_guard read-only shape 과차단 보정**(최상위 UNION·읽기전용 SHOW(테이블/뷰/config) 허용 — 쓰기·allowlist·금지함수·multi-statement 불변·tools.py stale 'UNION 불가' 힌트 제거). 코드 거주 0002(tools/sql_guard). 정본 TASK `20260713T140405`·`20260713T171821`.
- **답변 정확도·발견 도구 확장 (2026-07-14, conversation_audit·정본 REPORT 발)**: ① MySQL **시스템 변수(@@) 읽기 과차단 해소** — sql_guard denylist 가 `SELECT @@...` 읽기전용 조회를 잘못 차단하던 것 보정(07-13 UNION/SHOW shape 보정과 별건). ② **첨부↔실DB grounding 모순 완전 제거 + 식별자 대소문자 false-missing 봉인** — 첨부 리뷰가 실DB 대조와 모순되거나 대소문자 차이로 '없음' 오판하던 것 봉인 + **부분 증거(절단 미리보기) 전수 단정 환각 방지** + LLM 요청-레벨 오류 분류. ③ **MSSQL 구조화 발견 도구 DB(catalog) 인지** — cross-DB 검색·describe(관리 콘솔 메타데이터 여러 DB 검색). ④ **첨부 갱신요청 시 새 첨부 버전 전달 선호**(07-13 재업로드 버전관리 후속). 코드 거주 0002(tools/sql_guard/llm)·cross-cut 0003. 정본 TASK `20260714T153113`(sysvar)·`20260714T210000`/`20260714T221500`(grounding)·`20260714T063200`(부분증거)·`20260714T161500`(mssql-crossdb)·`20260713T185846`(attach-versioned).
- **첨부 변경 사실 = 코드-권위 사실 (2026-08-05, conversation_audit `FR-attachment-change-false-absence`, Major)**: 이번 턴에 무엇이 새로 첨부되고 무엇이 버전 갱신됐는지는 애플리케이션이 첨부 저장소에서 계산하는 **사실**이며 LLM 추론 대상이 아니다 — 단일 사실 채널(`_ATTACHMENT_TURN_FACTS_CTX`, compose 첫 문장에서 항상 클리어 → 워커 스레드 교차-대화 오염 차단)에서 한 번 계산해 ⓐ `compose_system_prompt` 말미 권위 블록 · ⓑ user turn 매니페스트(LLM 전달용 한정) · ⓒ red-team 리뷰어 사실 블록 3곳에 같은 값으로 싣는다. 금지 대상은 **"제공 사실의 부정" 하나**뿐이고(내용 동일·변경 불충분 결론은 정당) · 신규 0건이면 **세 블록 모두 미주입**(클라이언트 신호의 빈 값을 '첨부 없음' 으로 단정하면 이 봉인이 막으려는 마찰을 스스로 생산) · 파일명은 비신뢰 입력이라 건별 캡 + 평탄화. §18.8 backend/qa 적대 패널 **BLOCK** 판정 [P1]5·[P2]8 전건 흡수 + 뮤테이션 역검증 8종 KILLED. 배포 완료(PR #1155 → main `70df13a3`) · 라이브 사용자 대화 실측만 잔여. 정본 FUNCTION `(attach-change-false-absence)` · TASK `20260805T1600`.
- **첨부 전달은 답변의 출력 예산과 분리된다 (2026-08-06, conversation_audit `FR-attach-delivery-truncated-by-output-cap`, Major)**: 첨부 갱신본을 답변 본문 `attachment-edit` 블록으로 실으면 그 payload 가 답변 서술과 **같은 출력 창(`max_tokens`)을 두고 경합**하고 파일이 늘면 서로를 밀어낸다. 관측 대화에서 6파일 전문이 `completion_tokens=100,000` 상한에 정확히 도달해 1건만 전달됐는데, 잘리기 전에 쓰인 "6개 전부 갱신했습니다" 는 그대로 남았다 — `finish_reason` 은 코드 전체에서 **한 번도 읽히지 않았고** red-team 은 materialize **이전**에 돌아 실제 전달 결과를 구조적으로 볼 수 없었다. 증상 대응(감지·리뷰·순서)이 "전달 payload 가 출력 예산을 공유한다" 는 전제를 남긴다는 사용자 지적을 받아 **구조 개선**으로 재설계했다: 파일마다 독립 턴의 창을 쓰는 **`update_attachment` 도구**(`_ATTACHMENT_UPDATE_RUN_CAP` 20 · 블록 폴백은 `_ASSISTANT_EDIT_COUNT_CAP` 5) + unified-diff **`patch` 전달**의 fail-closed 적용기 `modules/patch_apply.py`(문맥 불일치 · ±400줄 안 모호한 다중 일치 · hunk 겹침/역순 · 알 수 없는 접두 · **잘린 패치**(머리말 선언 길이 ↔ 본문 크기 불일치) · 문맥 줄 없는 hunk → 하나라도 걸리면 **전체 미적용**, 원본의 지배적 줄바꿈 보존) + `finish_reason=="length"` 를 **초안 확정 시점에 latch**(red-team 의 revise/rederive 가 값을 덮으므로 리뷰 이후 재조회 금지) → 답변 말미 사용자 경고 + 리뷰어 사실 + 리뷰어 `DELIVERY FACTS`(블록 경로 전달은 리뷰 **이후** materialize 라 집계 밖 = **floor**. 총량으로 읽으면 정직한 혼합 턴을 BLOCK 한다). **가드는 분기하지 않는다** — 도구도 블록 경로와 같은 materialize(대화·소유권·kind·용량·명명·확장자)를 태우고 스코프는 `read_attachment` 와 동일 집합이며 bounded 발신자에겐 도구 자체가 노출되지 않는다. §18.8 [P1] 4 · [P2] 9 · [P3] 6 전건 흡수 중 결정적인 건 **도구로 만든 첨부가 다운로드 칩에 안 나오던 것** — 도구 호출 시점엔 `MetaJson.message_id` 가 없어 전달 id 를 `result["tool_delivered_attachment_ids"]` 로 내보내고 답변 저장 후 `_bind_tool_delivered_attachments` 가 워커·web inproc **양쪽**에서 바인딩한다(빠뜨리면 파일은 만들어졌는데 사용자에겐 아무것도 안 보여 도구 결과의 "칩으로 받습니다" 가 거짓이 된다). 테스트 56건 · 뮤테이션 9/9 KILLED · `docs/SECURITY.md §39` · 코드 거주 0002(`agent_core`·`tools`·`patch_apply`·`redteam`) + 0003(`routers/_conv_store.py`·`routers/conversations.py`). 정본 FUNCTION `(attach-delivery-tool, 2026-08-06)` · TASK `TASK-20260806T1600`.
- **`read_attachment` 완전성 계약 (2026-08-05, conversation_audit `FR-read-attachment-preview-looks-partial`, Major)**: 도구 결과가 **읽은 범위의 완전성을 스스로 진술**하고, 모델이 "어디까지 봤는지" 를 추론하게 두지 않는다 — 전문이면 범위 표기를 쓰지 않고(`1~42번째 줄 / 전체 42줄` 은 사람에게도 모델에게도 **부분 조회처럼 읽힌다**), 절단이면 이어읽기가 "방법" 이 아니라 **의무**이며(그 파일 전체를 근거로 삼는 판단 전에 반드시 이어 읽거나 답변에 확인 범위를 명시), 전달 줄 0건도 사유·유효 범위와 함께 명시한다(**빈 본문 ≠ 내용 없음**). **모든 수치는 실제 전달분에서 파생한다** — 문자 상한이 줄 중간을 자르면 조각줄을 버리고 온전한 줄만 센다. 종전에는 자르기 전 청크 길이를 돌려줘 `남은 0줄 미열람` 같은 **정량화된 허위**를 냈고 이어읽기 시작점이 전달분보다 앞서 **어떤 호출로도 오지 않는 구멍**이 생겼다(§18.8 backend/qa [P1]). 도구 description 이 `max_lines` 임의 축소를 금지한다 — 실측상 시스템 기본 캡(600줄)은 발동한 적이 없고 절단은 전부 모델의 자기 제한이었다. 표시층은 별개 축: 단계 결과 발췌(`_STEP_PREVIEW_CAP_CHARS` 500)는 "발췌" 임을 명시하되 **모델이 무엇을 받았는지 단정하지 않고**(`_cap_tool_result` 가 먼저 자를 수 있어 "전문 전달" 문구가 진짜 미열람을 덮는다) 모델측 절단은 `result_capped_for_model` 로 **반대 방향 경고**만 한다. 캡은 올리지 않는다 — steps 가 run 진행 중 폴링으로 반복 전송돼 상향이 매 payload 에 곱해지기 때문이다. 정본 FUNCTION `(read-attach-completeness, 2026-08-05)` · TASK `TASK-20260805T1900`.
- **백그라운드 pass 계측의 도달 규약 + 클러스터 라벨 "현재 유효성" (2026-08-06, aiops-hygiene · label-namespace, Minor 2 cycle)**: `run_insight_cycle` 의 `scan_report` 에 **dict 로 담긴 계측은 운영자에게 도달하지 않는다** — `_telemetry_sweep` 이 스칼라만 payload 로 흘리기 때문이고, 이 워커는 계측을 *만드는 것* 과 *도달시키는 것* 의 구분을 놓쳐 무음을 네 번 겪었다(auto_reanalysis 2회 · analysis_verify · domain_synthesis). 최소 계약 = 명시 payload 등재 · 0 인 tick 도 싣는 **`ran` 지표**(*요청이 없어 조용한 것* 과 *배선이 죽어 조용한 것* 을 가른다) · **`attempted` 와 산출 분리**(LLM 을 태우고 산출 0 인 pass 포착) · 기록 게이트에 카운터 조건 금지. 이어 L3 도메인 합성이 스키마의 클러스터 요약을 **전량** 재료로 써, 클러스터가 재구성돼도 지워지지 않는 옛 행이 섞이며 `cluster_count`/`member_count` 가 부풀려진 채 답변 프롬프트에 실리던 것(저장 90행/887멤버 ↔ 실제 84/770 · 라이브 `domain_summaries` 5건 전부 해당)을 **살아있는 라벨 집합**으로 필터한다. 판정 축은 시간이 아니라 **존재** — 같은 라벨의 여러 행이 "버전" 이 아니라 동시에 살아있는 다른 클러스터인 경우가 있어 "최신 1건" 처방은 직전 cycle 에서 **반증돼 철회**됐고(정합 편차 339→645 로 1.9배 악화), 라벨 저장처가 멤버 종류로 갈려(테이블→`rag_objects` — MSSQL 은 리터럴 `dbo` 라 `effective_schema` 필수 / 루틴→`routine_objects`) **한쪽만 보면 다른 쪽이 전멸한다**(`rag_objects` 단독 50.6% 사망 판정 → 루틴 합산 시 **3.4%**, 버려질 뻔한 933행 중 870행이 살아있는 루틴 클러스터 · `atum2_db_1` 은 라벨 달린 루틴 865 vs 테이블 115). 조회 실패는 **fail-closed**(합성 skip), 라벨 0 은 로그(head-of-line 정지 식별). 정본 FUNCTION `백그라운드 pass 계측의 도달 규약 (2026-08-06)` · `클러스터 라벨의 "현재 유효성" 판정 (2026-08-06)` · TASK `TASK-20260806T110000-aiops-hygiene` · `TASK-20260806T170000-label-namespace`.

## 4. 사용법

```bash
# CLI 1 회 실행
make ask QUESTION="SELECT ..."

# Insight worker 헬스 체크
docker compose logs insight-worker

# KB backfill (M3)
bash bin/kb-backfill.sh --all

# Cutover readiness
bash bin/kb-cutover-readiness.sh

# M5 cleanup (dry-run)
bash bin/kb-cleanup-mysql.sh --dry-run
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0007-bedrock-llm-provider]] — `LLM_BASE_URL` / `LLM_API_KEY` env 단일 진입

### 5.2 본 feature 를 의존하는 feature

- [[feature-0003-agent-web-ui]] — Web UI 가 본 core import
- [[feature-0005-qa-mcp]] — agent/MCP 모드 검증

## 6. 관련 정본

- [[../../unit/feature-0002-agent-core/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0002-agent-core/docs/TASK|TASK.md]]
- [[../../unit/feature-0002-agent-core/docs/AGENT_CORE_INTERNALS|AGENT_CORE_INTERNALS.md]]
- [[../../unit/feature-0002-agent-core/docs/INSIGHTS|INSIGHTS.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-datasource-registry|DESIGN-datasource-registry.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-db-level-access|DESIGN-db-level-access.md]]
- [[../../unit/feature-0002-agent-core/docs/DECISIONS|DECISIONS.md]] (ADR-CORE-*)
- [[../../docs/KB_PG_DIALECT_NOTES|KB_PG_DIALECT_NOTES]]

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — agent loop ↔ Bedrock gateway / Postgres 흐름
- [[../concepts/multi-datasource]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/datasource-aware-rag]] · [[../concepts/insight-worker]]
- [[../Decisions/ADR-0019-web-audit-events]] — audit dispatcher
- [[../Decisions/ADR-0021-kb-postgres-rbac]] — KB 2-layer RBAC
- [[../Decisions/ADR-0024-postgres-database-isolation]] — `agent_kb` / `agent_drag` namespace
- [[../Decisions/ADR-0025-m5-cleanup]] — MySQL KB drop 시점
- [[../Decisions/ADR-0027-agent-runtime-pg-schema]] · [[../Decisions/ADR-0028-runtime-mysql-cleanup]] — runtime PG 이관
- [[../Decisions/ADR-0030-ssrf-guard-toggle]] — datasource 보안 경계 토글

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0001-platform-runtime]] · [[feature-0003-agent-web-ui]] · [[feature-0007-bedrock-llm-provider]]

## 9. 외부 link

- [pgvector — Postgres vector extension](https://github.com/pgvector/pgvector)
- [pg_trgm — Postgres trigram similarity](https://www.postgresql.org/docs/current/pgtrgm.html)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/agent` · `#domain/llm`
