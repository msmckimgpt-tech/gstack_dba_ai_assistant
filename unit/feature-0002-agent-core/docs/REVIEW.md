---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

> 이전 기록(94건): [REVIEW-archive-20260711T120311.md](./_archive/REVIEW-archive-20260711T120311.md)

## REV-20260623T145444-sample-flywheel-core [SUBAGENT:sample-flywheel-adversarial-backend-security]
- Date: 2026-06-23
- Cycle: TASK-20260623T145444-sample-flywheel-core (ROADMAP ITEM-02+03 샘플쿼리 flywheel PR-A 코어), **Major §12.3** + 보안 표면(PII·injection-only).
- Trigger: §18.8 — schema/query/embedding(backend) + PII 마스킹·프롬프트 주입(security). 적대 코드리뷰(general-purpose outside voice, REFUTE: SQLi/injection-only/PII/ds-scope/approved gate/poisoning/연결/마이그/blast).
- 초기 VERDICT: **SHIP-WITH-FIXES** → BLOCKER 흡수 후 SHIP.
- **흡수한 BLOCKER (embedding ::vector 누락)**: `register_sample` INSERT 가 embedding list 를 캐스트 없는 `%s` 로 vector 컬럼에 바인딩 → psycopg3 가 float8[] 로 보내 타입 불일치 런타임 실패(write/promote 경로 무동작). FakeConn 단위·리터럴 dry-run 이 못 잡음. **수정**: `%s::vector`(search·kb_backend 선례 정합). **라이브 검증**: list 임베딩 register→search retrieval sim=1.0.
- **흡수한 MINOR**: down-vote "검색 가중 강등" 주석이 미구현 동작 주장 → 정정(현재 down 은 승급 거부만, 자동 가중 강등은 follow-up).
- **수용(문서화 한계)**: ①`ux_sample_queries_scope_nl` UNIQUE on text — nl_question >~2704B 면 btree row-size 초과(NL 질문 짧아 저확률, 입력 cap follow-up). ②`_mask_prose` regex-only — 한국어 이름 등 free-form literal 통과(기존 문서화 한계; write-path 적용은 정확). PII 는 defense-in-depth(부분).
- Confirmed-safe: SQLi 없음(전 param %s/named). **injection-only 확정**: 샘플 sql 은 load_example_queries_context 프롬프트 텍스트로만 읽힘 — execute_sql/커서 쿼리 전달 경로 0(grep). agent_core 예시-not-execute 펜스 + datamark. PII write-path 적용·승급 시 마스킹분 carry. ds-scope 캐스케이드. approved∧active∧embedding NOT NULL gate(기본 approved=false). poisoning: 승급 명시 호출만·down 미승급. 연결 owned-close finally. 마이그 0014→0013 head·멱등·GRANT 선례·ivfflat partial. agent_core blast: gate+try/except, embed None(titan 다운)→"" → 0 변경.
- Verification: test_sample_flywheel.py 12/12 + py_compile + 라이브 pg16 dry-run + 라이브 ::vector register→search sim=1.0. **AC-d A/B 측정은 titan-embed 401 다운으로 보류**(복구 후 harness off/on).
- Cross-ref: CHG-20260623T145444-sample-flywheel-core / REQ-20260623-1620·1621 / AC-a~e / ROADMAP dba-ai-nl2sql ITEM-02+03(PR-A).

## REV-20260623T151643-self-reflection [SUBAGENT:self-reflection-adversarial-backend-security]
- Date: 2026-06-23
- Cycle: TASK-20260623T151643-self-reflection (ROADMAP ITEM-07 Self-Reflection 자가수정 루프), **Major §12.3** + 보안(guard 제외).
- Trigger: §18.8 — query/제어흐름(backend) + 에러시 프롬프트 동봉·guard 우회(security). 적대 코드리뷰(general-purpose outside voice, REFUTE: 폭주/guard 우회/프롬프트인젝션/gating/last_sql 신선도/분류).
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0).
- **흡수한 MAJOR**: **M1(near-inert)** — `_is_fixable_sql_error` 가 `오류` 시작만 매칭했으나 실제 DB 실행 실패는 `tools.py:1073` 가 `SQL 실행 오류: {e}` 로 반환(="SQL" 시작) → unknown column/table/syntax 주 대상 미발동. **수정**: prefix 집합 `오류`/`SQL 실행 오류`/`도구 실행 오류`. **M2** — 테스트가 합성 `오류:` 만 써 M1 마스킹 → 실제 shape 회귀 테스트 추가.
- **흡수한 MINOR**: N1(guard 마커가 call-site wording 의존·fragile — `시스템 스키마` 안정 토큰으로 확장; 단 현재 struct 경로라 라이브 미도달) · N2(분류 substring 순서 — syntax 를 column/table 앞으로 재배치, "near 'table'" 오분류 방지).
- Confirmed-safe: bounded(reflection_count run당 0 초기화·cap 미만만 증가 → ≤cap, MAX=0 무력화) · max_steps/similar-retry 와 직교(이중 증폭 없음) · 라이브 execute_sql guard 메시지(보안차단/접근불가/내부차단/시스템스키마) 전부 제외(우회 유도 없음) · 프롬프트인젝션(넛지는 kind+last_sql[≤400]+고정 힌트만, 에러 raw text 미삽입·datamark 이후 동봉) · last_sql 은 동일 execute_sql 호출분(stale 아님) · gate off → 바이트 동일.
- Verification: test_self_reflection.py 7/7(실제 'SQL 실행 오류:' shape 포함) + prompt-injection 회귀 10 + py_compile. 라이브: describe-first agent 가 무에러 교정 → reflection 백스톱(단순 fixture 미발동). **AC-b 정량 회복률 보류**(에러유발 traffic/error-injection 모드 필요).
- Cross-ref: CHG-20260623T151643-self-reflection / REQ-20260623-1670 / AC-a~d / ROADMAP dba-ai-nl2sql ITEM-07.

## REV-20260623T163242-sample-embed-dim-1024 [SUBAGENT:embed-dim-fix-adversarial-backend]
- Date: 2026-06-23
- Cycle: TASK-20260623T163242-sample-embed-dim-1024 (ITEM-02 PR-A 후속 — sample_queries.embedding 1536→1024 정렬), **Minor §12.3**.
- Trigger: §18.8 — schema/migration → backend. 적대 코드리뷰(general-purpose, REFUTE: 마이그 정합/다운그레이드/차원 일관/blast/cascade).
- VERDICT: **SHIP** (BLOCKER 0, MAJOR 0).
- Confirmed-safe: 마이그 0015 down_revision=0014(단일 head, branch 없음) · DROP COLUMN+ADD 비파괴(컬럼 0행·FK/view/generated 의존 0, ivfflat 만 의존→명시 drop 후 재생성 byte-identical) · 멱등(IF EXISTS 가드) · downgrade 대칭(1024→1536) · 차원 일관(schema.sql/config/live/baseline texts 모두 1024) · search ::vector dim-agnostic · vector_cosine_ops dim-무관 · config 기본 변경 blast 0(AGENT_KB_EMBEDDING_DIM 유일 소비자 kb_embedding_worker 가 settings dict 에 넣되 미사용·dimensions param 미전달; live .env 이미 1024) · DROP COLUMN 비-CASCADE.
- 흡수한 NIT: sample_queries.py docstring 1536→1024.
- **Flag(범위 밖·기존 drift)**: schema.sql:68 texts + kb_backend.py:940 주석이 stale vector(1536)(정본 alembic 0001 texts=1024). 동작 무관(라이브/정본 1024)하나 fresh-install bootstrap 정합 cleanup 권장 — 별도 follow-up.
- Verification: 라이브 pg16 0015 적용 + 1024 register→search sim=1.0 + test_sample_flywheel 12 회귀 0 + py_compile.
- Cross-ref: CHG-20260623T163242-sample-embed-dim-1024 / ROADMAP dba-ai-nl2sql ITEM-02.

## REV-20260623T170000-task0305-followup-docs [SKIPPED:docs-only-no-code]
- Date: 2026-06-23
- Cycle: TASK-0305 후속 (라이브 배포 검증 정정 + 교훈 기록), **docs-only(런타임 코드 0)**.
- Trigger: §18.8 panel 비대상 — code 변경 없음(LEARNINGS/REPORT/TASK/MODIFY/wiki 문서만). 라이브 배포 검증 자체가 1차 증거(실측 review).
- VERDICT: **SHIP** (docs 정확성 정정, 런타임 영향 0).
- 근거(라이브 실측, 본 cycle): sudo 배포 후 RC5 cycle summary `db_failed:38 perm:0 circuit:38 other:0` + `agent_runtime.datasource_health` down 12개 전부 circuit_open/timeout → 축 A 가 GRANT(perm) 아니라 네트워크임을 확정. fingerprint backfill 후 샘플 stored==recomputed 10/10 일치 + tables_generated 0 복귀 + 통찰 8,833/238 무손실.
- 정정 내용: 머지 docs 의 "축 A=GRANT 지배" 서술에 라이브 정정(=네트워크) 추가(이력 보존), 교훈 LRN-20260623-0001/0002 영속, wiki §5 진단 순서 보강.
- Verification: docs-only — 빌드/테스트 무관. 정정의 사실 근거는 위 라이브 실측.
- Cross-ref: CHG-20260623T170000-task0305-followup-docs / TASK-0305.

## REV-20260623T180000-migration-split-brain-hygiene [SUBAGENT:migration-hygiene-adversarial-backend]
- Date: 2026-06-23
- Cycle: TASK-0306 (마이그 split-brain 해소 + 재발 방지 hygiene), **Major §12.3**.
- Trigger: §18.8 — schema/migration keyword → backend dispatch. 적대 코드리뷰(general-purpose outside voice, REFUTE: 0015 가드 정확성/체인/varchar/downgrade 대칭) + **라이브 PG 실측 검증**.
- VERDICT: **ACCEPT-WITH-NITS** (BLOCKER 0, MAJOR 0).
- 라이브 실측 통과: ①pgvector `format_type(atttypid,atttypmod)` 가 정확히 `'vector(1024)'`/`'vector(1536)'`/`'vector'` 반환 확인 → 가드 문자열 비교 정확. 1536 모사 테이블 dry-run 으로 REGENERATE 분기, 실 1024 로 SKIP 분기 발화 확인. DO $$ 블록 실행(rollback) 유효. fresh-install(0014=1536→0015) 정렬 동작 보존. `CREATE INDEX`(IF NOT EXISTS 제거)는 DROP COLUMN 직후 분기 안에서만 실행→충돌 잔존 인덱스 불가, 안전. ②schema.sql 1024 는 baseline 0001(=1024)·live·config(AGENT_KB_EMBEDDING_DIM=1024) 와 일치(새 drift 아님). ③alembic_version 라이브 이미 VARCHAR(128)·값 34자 보유, ALTER 멱등·PK 충돌 없음, down_revision 체인 0001→…→0015 단일 선형. ④downgrade 1024→1536 비대칭은 방향별 정확성(0014 복원)으로 정당.
- NIT(LOW, 차단 아님): NIT-1 `kb_backend.py:940` stale 1536 주석 → **본 PR 에서 같이 정정**. NIT-2 wiki `nl2sql-flywheel.md`/`docs/STATUS.md` 의 1536 서술 → doc-sync 후속(TASK 에 기록).
- Verification: 0015 py_compile + alembic-migrate.sh bash -n + 라이브 0013 적용·stamp·glossary 기능복구 검증.
- Cross-ref: CHG-20260623T180000-migration-split-brain-hygiene / TASK-0306 / LRN-20260623-0003.

## REV-20260625T012217-kb-pg-superuser-host [SKIPPED: deploy 설정값 1줄 — 코드·런타임 동작 무변경, 패널 불요]
- Date: 2026-06-25
- Cycle: kb-pg-superuser-host (CHG-20260625T012217-kb-pg-superuser-host). Minor §12.3.
- 변경: `.env.example` `AGENT_KB_PG_SUPERUSER_HOST=postgres` + 주석(superuser DDL 은 pgbouncer 우회 직결).
- SKIP 사유(§18.4): 설정 예시값 1줄 + 주석뿐 — 코드 무변경. 근본원인은 연결 실측(superuser 직결 OK / pgbouncer 경유 bouncer config error 재현 / rw@pgbouncer OK)으로 확증, fix 는 `make up` exit 0 으로 검증됨(라이브 게이트).
- Human Approval Needed: 아니오.

## REV-20260623T190000-embedding-auto-backfill [SUBAGENT:embed-autotick-adversarial-backend]
- Date: 2026-06-23
- Cycle: TASK-0307 (texts 임베딩 백필 + 자동 백필 데몬), **Major §12.3**.
- Trigger: §18.8 — embedding/worker keyword → backend dispatch. 적대 코드리뷰 **2-round** + 라이브 실측.
- Round 1 VERDICT: **REQUEST-CHANGES** — **F1(CRITICAL)**: 초기 설계는 `run_embedding_pass(200)` 를 insight tick(8s)에 **동기** 호출. 라이브 측정 titan-embed batch 100당 23-33초 → tick 당 50-60초 블로킹 → insight 스캔 본업 직렬 지연. (F2 동시백필 중복=비용낭비, F3 HNSW per-row autocommit=기존동작 동반 지적.)
- 재설계: per-tick 동기 호출 제거 → **별도 데몬 스레드**(`_embedding_backfill_loop`, conn_health 모니터와 동형 daemon)로 분리, tick 루프 비블로킹.
- Round 2 VERDICT: **ACCEPT-WITH-NITS** (BLOCKER 0). F1 구조적 해소(코드+라이브 확인: tick 8s 복원, 임베딩 HTTP 가 본 루프 미경유). 스레드 안전성 신규 결함 0 — pass 자체 PG conn open/close(메인 mem_conn/db_conn 비공유), 공유 global/advisory-lock 무접촉(grep), fail-soft 이중(pass dict + 루프 except), daemon=True 정리. degraded 가드는 메인 cycle 만 게이트(임베딩은 PG만 필요해 일반 degraded 에서도 적절히 동작).
- NIT(INFO, 비차단): N1 redeploy 중 in-flight pass 유실=resumable 무해. N2 sys.path 중복 prepend=양성(GIL atomic). N3 1회 백필↔데몬 동시 시 중복(idempotent)=배포 시퀀싱(백필 후 배포)으로 회피.
- Verification: py_compile 3 + import/early-return 라이브 + run_embedding_pass(이전 round ACCEPT) + 데몬 import 라이브 resolve 확인.
- Cross-ref: CHG-20260623T190000-embedding-auto-backfill / TASK-0307.

## REV-20260625T045450-limit-subject-msg [SKIPPED:message-text-only-no-logic] (Minor §12.3 — 요청량 한도 메시지 문구)
- Date: 2026-06-25
- Cycle: limit-subject-msg (CHG-20260625T045450-limit-subject-msg). cross-feature(feature-0002 주관 / feature-0003 cross-ref).
- 변경: `llm_provider_health.py` KIND_THROTTLED 메시지에서 provider 라벨(AWS Bedrock 등) 제거 → "서비스 자체의 요청량 한도..." 로 주체 명시 + 회귀 테스트 1건.
- SKIP 사유(§18.4/§18.8): 사용자 노출 메시지 문구만 — 분류 kind/HTTP 429/retryable/error_tag/응답 dict shape 무변경, 로직·인가·데이터·외부비용·스키마 0 표면. 자격증명 비유출 원칙은 본 변경으로 오히려 강화(backend 명칭 비노출). 회귀 테스트(message 비유출·서비스 명시) 추가·통과 → 적대 패널 불요.
- Verification: py_compile + `pytest test_llm_provider_health.py` 19/19 PASS(신규 test_throttled_message_is_service_level_without_provider_name 포함).
- Human Approval Needed: 아니오 (Minor — 비파괴 문구 변경).
- Cross-ref: CHG-20260625T045450-limit-subject-msg / TASK limit-subject-msg / feature-0003 CHG·REV-20260625T045450-limit-subject-msg.
## REV-20260625T035655-init-embedding-latency [SUBAGENT:init-embed-latency-adversarial-backend]
- Date: 2026-06-25
- Cycle: init-embedding-latency (CHG-20260625T035655-init-embedding-latency), **Major §12.3** — LLM provider/인프라·성능, cross-feature 0002·0007.
- Trigger: §18.8 — performance/latency/caching keyword → backend dispatch. 적대 코드리뷰(general-purpose outside voice, REFUTE: 캐싱 정확성·sentinel 백워드호환·account_recall 게이트 순서·의미 동등성·timeout·GPU 경합·ds-scope 격리) + 라이브 실측.
- VERDICT: **ACCEPT-WITH-NITS** (BLOCKER 0, MAJOR 0).
- 검증 통과(라이브+코드): ① 캐싱/sentinel — `_shared_qvec is None` 시 sample 은 `and _shared_qvec` 게이트로 skip, recall 은 `if not qvec: return []` 단락 → 재임베딩 없음. sentinel per-module 이나 agent_core 가 전달 안 해 식별자 혼동 없음. standalone(`_QVEC_UNSET`) 경로 테스트 통과. ② account_recall 순서 — `git show main` 으로 conv_ids 게이트가 구코드에서도 임베딩보다 선행 확인(회귀 없음), 벡터-only fail-closed 보존. ③ 의미 동등성 — bge-m3 실측 cosine(raw-whitespace, normalized)=**1.000000**(account_recall 도 동일 정규화). 검색 품질 회귀 없음. ④ ds-scope — 임베딩=f(text), scope 는 SQL `scope_key = ANY(...)`·`_scope_candidates()` 에서 강제 → 벡터 공유 안전. ⑤ timeout 배선 — `_get_llm_client(timeout_sec=20)`→timeout_val=20, 캐시키에 timeout 포함(별도 클라이언트). ⑥ cold-load vs 20s — 전용 인스턴스 cold reload **실측 3.63초**(27~37s 는 경합 공유 인스턴스 한정), KEEP_ALIVE=-1 재핀. 20s 여유 충분. ⑦ volume 분리(named vs bind 별 경로) 동시쓰기 충돌 없음. ⑧ mem_limit 4g 여유(라이브 1.7/4GB).
- NIT(LOW, 차단 아님): N1 gateway→embed-ollama `depends_on` 부재 → 최초 cold-boot(빈 volume pull ~180s) 동안 grounding graceful-skip(무크래시·1회성). N2 GPU 경합(bge-m3 1.2GB 핀 ↔ 공유 gemma4 — gemma4 는 7.8GB 라 본래 CPU/GPU 스플릿, 핀이 CPU 비중 소폭 증가, 별 `local_llm` 보조 프로젝트라 본 앱 chat 무관) — diff 주석에 trade-off 명시, 수용. N3 주석의 "AGENT_TIMEOUT_SEC(300s)" 는 `.env` 운영값(코드 기본 60s) — cosmetic. N4 `kb_retrieval.py:458`(agent-run RAG retrieval, 준비 단계 아님)은 timeout 미적용 300s 유지 — 범위 밖 후속. N5 init-script `set -u` only(`ollama serve` 사망 시 restart=unless-stopped 복구, warm-up best-effort) — 라이브 "warm-up 완료" 확인, 무해.
- Human Approval Needed: 아니오 (BLOCKER/MAJOR 0, 라이브 검증 통과).
- Verification: GPU/latency 라이브 실측 + 단위테스트(account_recall·sample_flywheel 통과; attachment_idor 4건 사전존재·무관) + titan-embed gateway e2e 0.13s + chat 라우팅 정상.
- Cross-ref: CHG-20260625T035655-init-embedding-latency / TASK init-embedding-latency / feature-0007 litellm_config.yaml·embed-ollama.

## REV-20260625T164701-ds-conn-circuit-msg [SUBAGENT:ds-conn-circuit-adversarial-backend]
- Date: 2026-06-25
- Cycle: ds-conn-circuit-msg (CHG-20260625T164701-ds-conn-circuit-msg), **Minor §12.3** — datasource 회로차단 사용자 안내 문구 분리(cross-feature, feature-0002 주관, shared/db.py).
- Trigger: §18.8 — 핵심 경로(연결/에러 surface) 인접 코드 변경 → backend dispatch. 적대 코드리뷰(general-purpose outside voice, REFUTE 6축: ① `e` 바인딩 정확성/NameError, ② except 순서, ③ 누락 surface(옛 프레이밍 잔존), ④ 비밀 노출, ⑤ `str(e)` 안정성/insight 분류, ⑥ 테스트 회귀).
- VERDICT: **ACCEPT** (BLOCKING 0).
- 검증 통과(코드+런타임): ① 단일 fallback `isinstance(e,...)` 의 `e` 는 바깥 `except Exception as e`(첫 시도)에 바인딩 — NameError 불가. `connect_with_retry` 가 circuit 을 **게이트 단계**(연결 시도 전, breaker key=host:port·database 무관)에서 raise → 회로 열림 시 첫 시도가 즉시 circuit → 올바른 분류. 멀티 primary 경로는 단일 try/except 라 모호성 자체 없음. ② tools.py `except DatasourceCircuitOpen` → `except Exception` 특정→일반 순서 정상. ③ circuit 운영 도달 경로 3곳(멀티 primary·단일 fallback·tool conn_for) 전부 분기 적용; 메모리/control-plane 은 `datasource=None`(게이트 미적용)이라 circuit 미발생, eval 경로 운영 미도달 — 옛 프레이밍 잔존 없음. web-ui 는 `result["error"]` 를 prefix 없이 verbatim 렌더. ④ `user_message()`·`str(e)` 모두 host/port/scope_key/password 무노출(런타임 확인). ⑤ insight.py scan_outcome 은 `isinstance(..., DatasourceCircuitOpen)` 타입 분류 + 생성자 문자열 미변경 → 분류 무회귀. ⑥ circuit surface 문자열 단언 테스트 0건; `test_conn_health.py:195` 는 예외 타입만 단언. 실행: conn_health/ask_worker 33 PASS + tool/insight/datasource 153 PASS, py_compile 3파일 OK, ruff All passed.
- NIT(LOW, 차단 아님): N1 tools.py circuit 안내는 사용자 직접이 아니라 LLM tool-result 로 전달 → LLM 재프레이밍 여지(리터럴 "연결 실패" 접두어 제거는 정확히 달성, 톤 보장만 약함; 후속으로 tool-result 에 "그대로 전달" 지시 가능). N2 agent_core 안쪽 `except Exception:` 이 둘째 시도 예외를 버림(기존 동작 — 첫 시도가 비-circuit·둘째만 circuit 인 드문 순서에선 첫 오류 노출이나 의미상 수용). 둘 다 REVIEW 수용 기록.
- Human Approval Needed: 아니오 (Minor — 비파괴 문구 분리, BLOCKING 0).
- Verification: §18.8 적대 패널 + py_compile + ruff + 회귀 테스트(상기).
- Cross-ref: CHG-20260625T164701-ds-conn-circuit-msg / FUNCTION ds-conn-circuit-msg / TASK-20260625T164701-ds-conn-circuit-msg.

## REV-20260703T093000-insight-load-spread [SUBAGENT:insight-load-spread-adversarial-backend-qa]
- 대상: TASK-0308 insight/graph 부하 분산 4축 (relationships.py probe 격리 / insight.py scan skip / metadata_graph.py+CLI batched·incremental / bin·.env.example 분산).
- Round: 8축 적대 검증 — ① probe backoff SQL 정확성, ② fetch_probe_candidates rotation 회귀, ③ regex 오탐, ④ sync_graph batching 안전성(autocommit toggle·부분커밋 멱등·pgbouncer·owned=False), ⑤ incremental 정합(dropped node·column staleness·watermark 실패), ⑥ watermark kv PK, ⑦ should_fast_fail scope_key 정합, ⑧ 테스트 충분성. 라이브 테스트 실행 + regex 13메시지/backoff 동역학 시뮬레이션 동반.
- VERDICT: **ACCEPT-WITH-NITS** (BLOCKER 0, MAJOR 0). 4 메커니즘 기능 건전 — SQL 문법 정확(psycopg3, make_interval/GREATEST/timestamptz), scope_key 는 양측 `compute_scope_key(engine,host,port)` 동일 도출로 정합, batching 멱등·pgbouncer transaction-mode 안전(ag_catalog 완전수식), fail-open 기본값 안전(미초기화·비-DOWN·예외 → 정상 스캔), regex well-behaved(MySQL transient 문자열과 무교집합). Ship-able.
- MINOR 반영(3건 전부 이번 cycle 처리):
  - ① **backoff "exponential-ish" 주장 정정** → 실제는 **flat 3600s throttle**: fetch filter 가 `last_validated_at > now()` 후보를 제외하므로 창 만료 후에만 재프로브되고 그때 GREATEST 가 now()로 collapse(누적 불가). 코드 주석(`relationships.py` `_PROBE_FAIL_BACKOFF_SEC`/`_backoff_validated`)·REPORT 문구 정정(spin 차단 목적은 flat 으로 충분; 진짜 누적은 별도 fail-count 컬럼 필요 — 미채택 명시).
  - ② **`--full` node prune 명확화**: broken 관계만 delete(status 변경→updated_at→incremental·full 반영), dropped 테이블/컬럼 **노드** prune 은 pre-existing 범위 밖(가산적 재생성 투영). `sync_graph` docstring·REPORT 정정.
  - ③ **테스트 보강**: watermark set/get round-trip + scope 격리, exception→rollback→autocommit 복원 경로 추가(mock).
- Verification: test_relationships **57** + metadata_graph units **10** + load_spread **6** PASS. 신규 단위 = relationships 3(unknown database regex 매칭·negative 파단, backoff-window fetch 제외) + relationships 수정 3(transient→backoff) + metadata_graph 6(since 증분 필터 유무·batched commit·owned autocommit 복원·rollback·watermark round-trip). AST/`bash -n` OK. DB 통합(psycopg 필요)은 post-deploy(코드 대조로 owned=False 경로 기존 동일 확인).
- Human Approval Needed: 아니오(BLOCKER/MAJOR 0). 단 배포(agent 이미지 재빌드 + insight-worker/local-llm-edge 재기동 + cron 재설치)는 외부영향 — 사용자 confirm.
- Cross-ref: CHG-20260703T093000-insight-load-spread / TASK-0308 / feature-0016 REPORT "graph sync 부하 분산" / ANCHOR 0002 §3 · 0016 §1 무충돌.

## REV-20260703T104500-insight-heartbeat-liveness [SKIPPED:heartbeat-throttle-liveness]
- 대상: insight.py `_touch_worker_heartbeat_progress`(진행-중 heartbeat throttle) + 스키마·테이블 순회 삽입.
- SKIP 근거(§18.4 경량 cycle): (1) 로직 단순 — monotonic throttle + `save_memory_kv` 1회(기존 line 2273 갱신과 동일 KV·동일 함수), (2) **healthcheck 판정식 미변경** — 갱신 **지점**만 추가(cycle 완료 시각→진행 중에도), (3) status/hang 탐지 의미 보존(status 미변경, 생성 정지 시 stale 유지), (4) 신규 단위테스트 2(throttle 억제/경과 저장·None no-op·예외 삼킴) + insight 회귀 0(12 PASS) + AST 로 커버. 데이터손상/크래시/보안 표면 0.
- 잔여 인지(비차단): throttle 30s + `_is_insight_worker_heartbeat_fresh` age≤30s 경계 → inline-scan gate 가 가끔 stale 판정 가능(성능 이슈지 health 아님, docker health(age≤180s)는 확실 해소). 필요 시 throttle↓ 또는 STALE_SEC 조정 후속.
- Verification: 신규 test_insight_heartbeat_liveness.py 2 PASS + datasource_health·degraded_backoff 12 PASS + AST OK. 배포 후 docker inspect healthy 라이브 확인.
- Cross-ref: CHG-20260703-insight-heartbeat-liveness / feature-0002 REPORT·TASK insight-heartbeat-liveness.

## REV-20260707T100640-no-edge-conversation-answer [AGENT-TEAM:adversarial-2lens-refute] — 대화 답변 edge(gemma) 폴백 완전 차단 (CHG-20260707T100640, Major §12.3, conversation_audit)
- Date: 2026-07-07. Trigger 키워드 매칭(§18.8): LLM 모델 라우팅·폴백(L6/L8) + 비결정 행동(fallback→실패)·자격 경로 → **backend+qa+회귀+security**. Major(코어 LLM 경로·가용성 정책 변경) 라 커밋 전 2렌즈 독립 적대 패널(REFUTE-우선).
- 렌즈①(backend/correctness — 답변 경로 완전성·누수·깨끗한 실패·회귀): **C1~C5 전부 CONFIRMED, BLOCKING/MAJOR/MINOR 0**. 검증: `_call_llm` 이 유일한 task='agent' 답변 생성 경로(단일 caller agent_core.py:3748, 유일 create 2686)·다른 모든 create() 는 aux/insight/prompt_gen/node_analysis(무관)·insight/분석 무누수(각자 own model 직접 호출)·두 계정 실패 시 except(3758)→classify_llm_provider_error 친화 메시지→break(무한루프 없음, empty-retry 는 성공-빈응답만·cap 3)·sonnet/vision/thinking/max_tokens 무회귀(원본 model 키)·usage 원본 model 기록.
- 렌즈②(security/regression/litellm-config): **S1~S5 전부 CONFIRMED, BLOCKING/MAJOR 0**. 검증: chat-root fallback 미등록 → 종단 429/401 raise(설정 주석 lines 188-191 선례로 실증, classify 가 status 429/401/5xx 전부 친화 처리 — gemma 는 구조적으로 도달 불가라 안전은 무조건 성립)·`-chat` 은 is_allowed_api_model 검증 대상 아님(user model=claude-haiku-4 만 검증, 아웃바운드는 미검증)·순수 폴백 축소(신규 자격/RBAC/PII/secret 0, 동일 두 OAuth 키 재사용)·thinking 5000 동일·budget≤16000<max20000·bind-mount 재시작 반영.
- NIT(두 렌즈 독립 동시 지적, **수정 반영**): 봉인이 리터럴 `claude-haiku-4` 매핑 의존 → 기본 모델(API_DEFAULT_MODEL)이 다른 edge-fallback alias 로 바뀌면 봉인 silent 붕괴·기존 테스트 미포착. → **G5 가드 테스트 추가**(`test_default_conversation_model_chain_is_edge_free`): litellm_config.yaml 실제 파싱 → `conversation_answer_model(API_DEFAULT_MODEL)` 아웃바운드 alias 의 폴백 체인을 그래프 순회 → 도달 가능 모든 alias 의 실 model 이 `anthropic/*` 임을(로컬/edge/gemma 도달 불가) assert. 기본 모델 변경·체인 수정 시 자동 적발. PASS.
- 인지(범위 밖, 사용자 결정=답변 한정): context-feeding aux(summary/topic)·prompt_gen·node_analysis 는 여전히 gemma(ctx 4096) 강등 가능 — 본 cycle 미대상(사용자가 assistant 답변 경로로 명시 한정). 필요 시 후속.
- Verification: 신규 test **5 PASS**(G1~G4 헬퍼·_call_llm 라우팅·기록 + G5 체인 가드) + feature-0002 회귀 0. route-parity 실패=환경(clean main 동일, A/B 확인).
- Human Approval: 방향=사용자 결정(2026-07-07 AskUserQuestion). 구현+검증+배포=PLAN-APPROVED. 배포(ask-worker+web 재빌드 + bedrock-gateway 재생성)는 외부영향 confirm(Major override 불가).
- Cross-ref: CHG-20260707T100640-no-edge-conversation-answer(feature-0002/0007/shared MODIFY) · FRICTION_LEDGER FR-edge-fallback-conversation-context-loss · ANCHOR 0002 §1~§3 / 0007 §1~§2 무충돌(폴백 축소만).

## REV-20260707T134500-bedrock-chat-alias-probe-artifact [SKIPPED:docs-only-investigation] — bedrock-gateway 400 1회성 오류 조사 (no-op, CHG-20260707T100640 후속)
- Date: 2026-07-07. 코드/설정 변경 0(순수 조사 + 문서화) — §18.4 경량 cycle, 적대 패널 SKIPPED.
- 근거: 배포 타이밍 재구성(PR #600 머지 10:28:41 → gateway 재생성 10:31:02 → ask/insight 이미지 재빌드 10:32:18) + 실패 시각(10:37:18)의 실행 이미지(`634f9d6e7de7`)를 직접 열어 이미 수정 코드 보유 확인(stale-image 가설 기각) + 정적 코드 추적(`_call_llm` 유일 caller, claude-* 모델에 항상 `max_tokens=20000` 주입 — 충돌 경로 없음, 저장소 전체에서 `conversation_answer_model` 호출부 1곳뿐) + 게이트웨이 라이브 재현(`max_tokens<5000` 만 재현, `≥5000`/미지정은 정상) + 컨테이너 기동 이후 전체 로그 재발 0 확인.
- 결론: 코드 결함 아님. FRICTION_LEDGER 의 post-deploy "live probe" 절차가 만든 1회성 프로브 아티팩트 — 실 사용자 대화 트래픽 영향 없음(연계 conversation_id 없음).
- Cross-ref: CHG-20260707T134500-bedrock-chat-alias-probe-artifact(feature-0002 MODIFY) · FRICTION_LEDGER FR-edge-fallback-conversation-context-loss addendum.

## REV-20260710T232503-alembic-multihead-gate [SKIPPED:roadmap-spec-transcription] — 병렬 마이그레이션 번호 경합 CI 게이트 + 해소 자동화 (parallel-work-structure ITEM-02)
- Date: 2026-07-10. cycle: ai/claude-corp/feature-0002-agent-core — `/_dqa:improve_cycle parallel-work-structure` 드레인 2번째 항목(ITEM-02, Minor). **승인 근거: ROADMAP §6.1**(2026-07-10 사용자 지시 — Minor 는 드레인 자동 구현 범위).
- SKIPPED 사유: what/entry_points/acceptance/guards 가 ROADMAP ITEM-02 에 완전 명세 — 그 명세는 improve-fit-reviewer 2-round 적대 리뷰(REV-20260710T180820, meta/REVIEW.md)가 사전 검증. 구현은 명세 전사 + 검증 주도(아래) — DB 스키마 무변경(마이그레이션 0건), 제품 런타임 코드 무변경(도구·CI 게이트만), §18.8 dispatch(auth/schema/UI/API/perf) 비해당(스키마 '변경'이 아닌 스키마 변경의 '검사기').
- 검증(acceptance 전건 실증 — TEST.md §3 "alembic-multihead-gate"): self-test 10/10(신규 head 4 케이스 포함) · 현행 39체인 PASS · (a) 중복 0040×2 FAIL 적발 · (b) reparent 1회 PASS 복원 · (e) 병렬 브랜치 MAX_MIGRATION.txt git CONFLICT fail-fast 재현 · bash -n 2종 · (d) CI 스텝은 본 PR checks 로 확인.
- guard: reparent 는 origin/main 미머지 파일만(스크립트 강제 die) — 라이브 alembic_version stamp 파손 방지(MIGRATIONS.md 규약 절 명문화).
- Human Approval Needed: 아니오 — Minor·비파괴(검사기 추가)·배포 무관(CI/도구만). 전역 auto-sync + §6.1.
- Cross-ref: CHG-20260710T232503(MODIFY) · ROADMAP ITEM-02 note · MIGRATIONS.md "병렬 브랜치 번호 경합 게이트" 절.

## REV-20260711T120311-docs-archive [SKIPPED:mechanical-archiving] — MODIFY/REVIEW §5.5 아카이빙
- Related Change: CHG-20260711T120311-docs-archive. 검증이 결정적: 재구성 md5==원본(양 문서, assert)·엔트리 경계 verbatim·링크+압축 정보. 런타임 코드 0. 승인: 사용자 지시+§5.5 규약 내.

## REV-20260713T140405-describe-routine-tool [AGENT-TEAM:security+backend+qa-adversarial] — 저장 프로시저/함수 정의 조회 도구 (conversation_audit FR-show-create-routine-blocked)
- Date: 2026-07-13. Related Change: CHG-20260713T140405-describe-routine-tool. cycle: ai/claude-corp/feature-0002-agent-core.
- Trigger (§18.8 dispatch): changeset 이 카탈로그 조회 SQL(`query`/`schema`) + 신규 도구가 루틴 정의(소스) 표면화(데이터 노출·가드 경계 인접) → **security + backend/correctness + qa/regression** 3렌즈 병렬 적대 패널(각 REFUTE 목표). full panel default(프롬프트 키워드 0건 아님 — query/schema 매칭 + 보안 렌즈 명시).
- **security 렌즈**: 5주장 중 4 REFUTED(safe) — ① sql_guard SELECT/CTE-only 불변식 미변경(SHOW CREATE 여전히 거부, sql_guard.py 무수정) ② allowlist/내부스키마 게이트(`_struct_schema_access_error` 선행, agent_memory 영구차단) ③ 정보노출 privilege-equivalent(information_schema.ROUTINES 는 이미 execute_sql 로 조회 가능·DB GRANT backstop·정의 NULL 시 graceful) ④ redirect 정규식 무해(거부 메시지 append 만·ReDoS 없음). **MAJOR(CONFIRMED) 1건 → 수정 완료**: `_safe_ident` 가 역슬래시(`\`)를 미제거 → MySQL(백슬래시 이스케이프 기본 ON)에서 `schema='x\'` 가 `'{schema}'` 종료 따옴표를 이스케이프해 인접 `'{name}'` 이 raw SQL 로 탈출(UNION 인젝션). **pre-existing·구조화 도구 전반 공유 사인**(describe_table/search/indexes/fk 동일 패턴), allowlist 모드에선 차단·레거시 single-MySQL(allow=None)에서만 도달. **근본 수정**: `_safe_ident` strip set 에 `\` 추가 → describe_routine + 모든 구조화 도구 소급 방어(가드=권위적 방어선). 회귀 테스트 `test_safe_ident_strips_backslash`.
- **backend/correctness 렌즈**: BLOCKER/MAJOR 0. 컬럼 순서(정의 5·파라미터 4/5)·positional 인덱싱·MySQL(ROUTINES.ROUTINE_DEFINITION 본문·DTD_IDENTIFIER·PARAMETERS)·MSSQL(OBJECT_DEFINITION 4000자 절단 회피·스키마-vs-DB 의미=`describe_columns` 규약 일치, ADR-007 그래프 규약과 무관)·datasource 라우터 배선(build_tool_definitions_for_datasources datasource 인자 주입·activate/finally 복원)·multi-statement(multi=False, 단일 SELECT) 전부 REFUTED(correct). **MINOR(CONFIRMED) 1건 → 수정 완료**: MySQL 동명 PROCEDURE+FUNCTION 공존 시 `routine_parameters` 가 타입 미구분 → 두 루틴 파라미터가 양 헤더에 교차오염. **수정**: 파라미터 쿼리에 `ROUTINE_TYPE`(pr[4]) 추가(MySQL 실컬럼·MSSQL NULL 상수, MSSQL 은 동명 불가라 무관) + 다중 def_rows 시 타입별 필터. 회귀 테스트 `..._same_name_proc_func_param_isolation`.
- **qa/regression 렌즈**: BLOCKER/MAJOR 0. narration param 주입(FULL 공유 dict idempotent·reason-first)·핵심 도구 카운트 무가정(index[0]=execute_sql 불변)·거부 메시지 byte-동치(비-루틴 SQL 은 redirect 빈문자열)·LLM 노출(TOOL_DEFINITIONS→use_tools 확인) REFUTED(no regression). **MINOR(CONFIRMED) 1건 → 수정 완료**: 런타임 narration fallback 은 `agent_core._derive_step_work/_derive_step_reason` 인데 describe_routine 케이스 부재로 generic 라벨/빈 reason 파생(feature-0003 `_conv_store` 는 stored-work 있을 때 미도달). **수정**: agent_core 두 함수에 describe_routine 케이스 추가(feature-0003 companion 은 레거시 표시 경로로 유지).
- NIT 처리: 스테일 "핵심 4개" 주석 → "핵심 5개" 수정. 파라미터 표 `|`/정의 ``` 펜스 markdown escape → cosmetic 수용(소비자=LLM 텍스트, SQL 식별자에 `|`·삼중backtick 사실상 부재). 시스템 프롬프트에 describe_routine 미언급 → 수용(도구 description 자체가 사용 안내 + SHOW CREATE 거부 유도 힌트가 discovery 보완). schema_name 설명 MSSQL 오해소지 → 경미(sibling 도구 동일 관행).
- 검증: `tests/test_describe_routine_tool.py`(신규, 백슬래시·파라미터격리 보강 포함) + 보안 가드 3파일(test_query_guard/test_sql_trust_boundary/test_mssql_security_boundary) 재통과 + 전체 스위트 pytest RC=0(feature-0002+0003). py_compile clean.
- 라이브 실측 필요분(Phase 11b): 코드/테스트는 "도구가 정의를 반환·SHOW CREATE 유도·sql_guard 불변" 증명. "실제 대화에서 프로시저 검토 마찰 소멸" 은 배포 후 라이브 대화 실측분(미수행) → FRICTION_LEDGER `fixed:deployed:unverified-live`.
- Human Approval: 수정 방식(Option 1 전용 도구+유도)은 AskUserQuestion(2026-07-13) 사용자 승인. Major(신규 LLM 노출 도구·정의 표면화) → PR/deploy 는 외부영향 confirm 유지.
- Cross-ref: CHG-20260713T140405-describe-routine-tool(MODIFY) · FUNCTION REQ-20260713-describe-routine · TEST-20260713-describe-routine · FRICTION_LEDGER FR-show-create-routine-blocked · feature-0003 `_conv_store.py` narration(companion) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260713T151500-describe-routine-deploy [SKIPPED:post-deploy-doc-reconciliation] — 배포 완료 기록 + 원장 상태 정합
- Date: 2026-07-13. Related Change: CHG-20260713T151500-describe-routine-deploy. 코드 변경 0(docs-only).
- SKIPPED 사유: 런타임 코드 무변경 — PR #749(REV-20260713T140405 검증 완료) 배포 후 상태 정합(FRICTION_LEDGER fixed:undeployed→fixed:deployed:unverified-live + TASK 체크박스). 배포 검증은 결정적: 4서비스 GIT_COMMIT=6841eba2 + ask-worker 런타임 import 실증(describe_routine/handler/_safe_ident 백슬래시) + web /healthz. §18.8 dispatch 비해당(배포 기록).
- Human Approval: 배포는 사용자 confirm(AskUserQuestion 2026-07-13 "PR 머지 + 배포"). 본 follow-up 은 그 배포의 정직-상태 기록(docs-only).

## REV-20260713T171821-readonly-query-shapes [AGENT-TEAM:security+backend+qa-adversarial(세션한도 조기종료→인라인 자기검증 완료)] — read-only 쿼리 shape 과차단 보정 (conversation_audit FR-readonly-query-shapes-overblock)
- Date: 2026-07-13. Related Change: CHG-20260713T171821-readonly-query-shapes. cycle: ai/claude-corp/feature-0002-agent-core.
- Trigger (§18.8 dispatch): sql_guard 허용범위(`query`/보안 경계) 확장 → **security + backend/correctness + qa/regression** 3렌즈 병렬 적대 패널.
- **패널 상태 정직**: 3 서브에이전트 모두 실행 중 **API 세션 한도(17:30 KST 리셋)로 조기 종료**. security 렌즈가 종료 직전 **CONFIRMED 후보 1건** 표면화 → 저자가 **인라인으로 적대 검증 완료**(재spawn 은 동일 한도 회피). 리뷰어 probe 목록 전 항목을 코드 실행으로 자기검증.
- **MAJOR(CONFIRMED) 1건 → 수정 완료**: **데이터 수정 CTE 우회** — `WITH c AS (DELETE/INSERT/UPDATE … RETURNING) SELECT … c` 가 accepted shape(With→Select)로 통과(write 노드가 CTE 본체에 은닉). **pre-existing 잠복**(`With` shape 수용은 기존; MySQL/MSSQL DML-in-CTE 미지원·RO GRANT backstop 이나 guard 는 authoritative 여야 함). UNION 확장이 새 중첩 컨텍스트를 열어 표면 확대. **봉인**: `_find_write_node` 로 accepted 트리 전체(CTE 본체·서브쿼리·union 분기) write/DDL/command 노드(Insert/Update/Delete/Merge/Create/Drop/Alter/TruncateTable/Command/Copy/LoadData) 스캔 거부(defense-in-depth). read-only 트리 false-positive 0 실측. 회귀 테스트 `test_data_modifying_cte_blocked(_tsql)` + `test_recursive_and_nested_readonly_cte_allowed`.
- **security 나머지 REFUTED(safe, 실행 검증)**: UNION 분기 forbidden-schema(agent_memory) 차단 · 중첩 UNION/서브쿼리 forbidden 분기 차단(find_all 트리 전수) · UNION 분기 lock/into/금지함수(SLEEP) 차단 · read-only SHOW 화이트리스트 tight(GRANTS/DATABASES/PROCESSLIST/PRIVILEGES 거부) · SHOW 대상 forbidden schema 차단 · SHOW `.db` 가 collect_schema_refs→제품 allowlist 강제 · INSERT…SELECT/CTAS/REPLACE 거부(shape+write-node).
- **backend REFUTED(correct)**: `exp.SetOperation` 이 Union/Intersect/Except 공통 base(설치 sqlglot v27 확인) · lock/into 를 `root.find_all(Select)` 로 이동해도 benign 서브쿼리 무회귀(false-reject 0) · **SHOW under tsql 은 거부**(sqlglot tsql 이 SHOW 미파싱→Command→shape 거부; SHOW 는 MySQL 전용이라 MSSQL 경로 정상) · `_show_target_db` 는 CREATE TABLE/COLUMNS/INDEX/TABLE STATUS 의 `.db` 정확 추출 · read-only SHOW 는 guard_mode off(기본)라 load-estimate 미개입, warn/gate 여도 MySQL fail-open.
- **qa REFUTED(no regression)**: 전체 스위트 1899 PASS(RC=0) · self-reflection 은 "보안 정책상 차단" prefix(wording-drift 내성)로 새 거부메시지(only SELECT/CTE/UNION·write/DDL·Show KIND) 전부 자가수정 제외(우회 유도 안 함) · describe_routine 유지(SHOW CREATE PROCEDURE/FUNCTION 계속 거부→`_routine_introspection_redirect` 유도) · stale UNION-불가 tip 제거는 `test_gc_dialect_context` 1건만 영향(단언 갱신).
- 라이브 실측 필요분(Phase 11b): 코드/테스트/standalone 스모크는 "UNION·read-only SHOW 통과 + write/DDL·비-readonly SHOW·multi-statement 차단" 증명. "실제 대화에서 동적쿼리·테이블변경 리뷰 마찰 소멸" 은 배포 후 라이브 실측분 → FRICTION_LEDGER `fixed:deployed:unverified-live`.
- Human Approval: 범위(UNION + 읽기전용 SHOW) AskUserQuestion(2026-07-13) 사용자 승인. Critical(sql_guard 허용범위) → PR/deploy 는 외부영향 confirm.
- Cross-ref: CHG-20260713T171821-readonly-query-shapes(MODIFY) · FUNCTION REQ-20260713-readonly-query-shapes · TEST-20260713-readonly-query-shapes · FRICTION_LEDGER FR-readonly-query-shapes-overblock(+ FR-show-create-routine-blocked 후속) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260713T173000-readonly-query-shapes-deploy [SKIPPED:post-deploy-doc-reconciliation] — 배포 완료 기록 + 원장 생성
- Date: 2026-07-13. Related Change: CHG-20260713T173000-readonly-query-shapes-deploy. 코드 변경 0(docs-only).
- SKIPPED 사유: 런타임 코드 무변경 — PR #761(REV-20260713T171821 검증 완료) 배포 후 상태 정합(FRICTION_LEDGER FR-readonly-query-shapes-overblock 생성·fixed:deployed:unverified-live + REPORT + TASK). 배포 검증 결정적: 4서비스 GIT_COMMIT=9892fc3b + ask-worker 런타임 가드 동작 실증(UNION/SHOW 허용·write-CTE/GRANTS 차단) + web /healthz.
- Human Approval: 배포 사용자 confirm(AskUserQuestion 2026-07-13 "PR 머지 + 배포"). 본 follow-up 은 그 배포의 정직-상태 기록(docs-only).

## REV-20260713T185846-attach-update-versioned [AGENT-TEAM:security+backend+qa-adversarial] — 첨부 파일 갱신 전달 선호 + 명명 정합 (conversation_audit FR-attachment-update-pasted-not-versioned)
- Date: 2026-07-13. Related Change: CHG-20260713T185846-attach-update-versioned (+ feature-0003 CHG-20260713T185846-attach-filename-consistency). cycle: ai/claude-corp/feature-0002-agent-core.
- Trigger (§18.8 dispatch): 프롬프트·맥락 조립 code change(SYSTEM_PROMPT + compose_system_prompt) + 첨부 materialize 명명 — §18.8 표 키워드 0건 매칭 → **full panel default = security + backend/correctness + qa/regression** 3렌즈 병렬 적대 패널(security+qa 임의 축소 안 함).
- **패널 결과: BLOCKER/MAJOR 0**. 실질 조치 1건(MINOR security 회귀 봉인), 나머지 REFUTED.
- **security — SEC-1 CONFIRMED(MINOR) → 봉인 완료**: source `OriginalFilename` 에 확장자가 없고(그러나 Kind=text/csv) LLM 이 이중확장자(`x.exe.txt`)를 주면, 기존 수정안이 `x_v2.exe` 로 위험 확장자를 **유효(trailing) 확장자로 승격**(구 코드는 `x.exe.txt` 로 무해했음 → 회귀). 다운로드가 이미 하드닝(octet-stream·attachment·nosniff)이라 MINOR 지만, "실행파일류 확장자 차단" 불변식의 회귀라 봉인: 확장자 부재 시 `safe_ext = kind 기반(csv/txt)` 강제 → LLM 내부 dot 이 유효 확장자로 승격 불가(`_conv_store.py` naming 블록). 회귀 테스트 `test_n4_extensionless_source_forces_safe_ext`. **SEC-2~5 REFUTED**: materialize 가드(conv/account scope·text/csv-only·size cap·MinIO-before-INSERT·UNIQUE version race) 전부 diff 밖·불변 · 프롬프트 무관 런타임 IDOR 차단 유지 · directive 배치가 injection-guard precedence 미훼손(index 1 guard 불변, base 뒤 코드주입) · `_v\d+$` 정규식 bypass 불가(`or stem` empty-collapse 방어·end-anchored·slash 상류 strip).
- **backend/correctness — 전부 REFUTED**: `_next_version_filename` idempotent 이 realistic 입력 전부 정합(`report_v2.csv`+v3→`report_v3.csv`; `_version2`·leading `v2_`·multi-digit 정상; degenerate `_v2`·uppercase `_V2`·`a_v2_v3`는 NIT) · 명명 omitted/provided 양경로 무회귀(directory sep 은 stem 추출 前 strip, ext 강제) · `app.re` 는 `app.py:11 import re` 로 call-time 해소(런타임 crash 없음) · directive `parts` index 2·`"".join(parts)` 반환 포함·product/role/account 前 위치(의도) · version 파생·UNIQUE race 명명과 orthogonal.
- **qa/regression — 전부 REFUTED**: 강화 프롬프트가 "a file they ATTACHED" 로 정확 게이팅 → brand-new 채팅 SQL 미오발(QA-1) · 프런트 `_syncConversationAttachmentsToBucket` 가 이전 첨부 매턴 재포함 → "재첨부 요청" 경로 희소(QA-2) · 기존 테스트 old 프롬프트/`report_v2.csv` 수동명명 assert 없음(test_b3 만 parts-리터럴 갱신, 나머지 additive) · 칩/narration/strip 은 version_number·실제 저장명 기반이라 명명 변경과 정합(QA-4) · 프롬프트 주장(`<original>_v<n>.<ext>`)과 코드 산출 일치(QA-5). 타깃 36 테스트 PASS.
- **수용된 잔여(설계상 의도·NIT)**: 기본 base(비-override) 시 full 섹션 + condensed directive 중복(drift-seal floor — 두 카피 동기 유지 주석) · version = chain MAX+1(source+1 아님)·사용자 자작 `_vN` 재작성(코드-권위 versioning 의 의도된 귀결).
- **라이브 실측 필요분(Phase 11b)**: 코드/테스트는 "명시적 갱신요청 → attachment-edit 유도·명명 정합·확장자 안전" 증명. "실제 대화에서 붙여넣기 감소·버전 생성 비율 상승" 은 배포 후 corroboration 재측정분(미수행) → FRICTION_LEDGER `fixed:deployed:unverified-live`. **QA-2 MINOR watch**(text-inline count cap 초과 대화에서 메타엔 뜨나 content 미주입 시 "MUST" 가 fabrication 유도 가능)는 라이브-eval 관찰 항목으로 이월.
- Human Approval: Scope A(AskUserQuestion 2026-07-13) PLAN-APPROVED. Major(코어 LLM 경로) → PR/deploy 는 외부영향 confirm(override 불가).
- Cross-ref: CHG-20260713T185846-attach-update-versioned(MODIFY) · feature-0003 CHG-20260713T185846-attach-filename-consistency · FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · ANCHOR 0002 §1~§3 무충돌.

## REV-20260714T031500-attach-update-deploy [SKIPPED:post-deploy-doc-reconciliation] — 배포 완료 기록 + 원장 상태 정합
- Date: 2026-07-14. Related Change: CHG-20260714T031500-attach-update-deploy. 코드 변경 0(docs-only).
- SKIPPED 사유: 런타임 코드 무변경 — PR #771(REV-20260713T185846 검증 완료) 배포 후 상태 정합(FRICTION_LEDGER fixed:undeployed→fixed:deployed:unverified-live + TASK 체크박스). 배포 검증 결정적: 4서비스 GIT_COMMIT=ee4f8de6 running/healthy + ask-worker 런타임 실증(A1 attachment-edit 강화·A2 directive) + web-a 런타임 실증(A3 이중접미 방지·safe_ext) + web /healthz=ee4f8de6.
- Human Approval: 배포 사용자 confirm(AskUserQuestion 2026-07-13 "PR·머지·배포 전체"). 본 follow-up 은 그 배포의 정직-상태 기록(docs-only).

## REV-20260714T153113-sysvar-select-guard [AGENT-TEAM:security+backend+qa-adversarial] — MySQL 시스템 변수 읽기(@@) denylist 과차단 해소 (conversation_audit FR-sysvar-select-denylist-overblock)
- Date: 2026-07-14. Related Change: CHG-20260714T153113-sysvar-select-guard. cycle: ai/claude/feature-0002-sysvar-guard.
- Trigger (§18.8 dispatch): sql_guard 허용범위 code change(`query`/`schema` 키워드 매칭) → **security + backend + qa** 3렌즈 적대 패널. (backend+qa 서브에이전트가 세션 한도로 조기 종료 → 인라인 자기검증으로 완료 — 결정적 실증 확보.)
- **패널 결과: BLOCKER/MAJOR/MINOR 0 — 전건 REFUTED**(보안 회귀 0).
- **security(적대 서브에이전트 완주) — 5축 전건 REFUTED**: (1) write/priv-esc — `SET @@GLOBAL.x`=`\bSET\s+@` denylist 차단, `SET GLOBAL x`(무-@@)·`SET@@`(무공백)=shape 게이트 `exp.Set`/`exp.Command` 루트 거부(regex 무관 backstop), `:=`·`SET @a` 차단 유지 → 신규 write 경로 0. (2) 정보노출 델타 0 — `SELECT @@x` 는 이미 승인된 `SHOW GLOBAL VARIABLES/STATUS`(전체 시스템변수 덤프)의 **부분집합**(`secure_file_priv`/`datadir`/`version`/`hostname` 모두 SHOW 로 이미 노출). (3) subquery/UNION/CTE 분기 — forbidden-schema/lock/into/write-node/forbidden-func 전부 `find_all(Select)`/`root.find_all` 전수 순회라 `@@` regex 와 독립(`SELECT @@v UNION SELECT pw FROM agent_memory.users`·데이터수정CTE 차단 실증). (4) T-SQL `@@` denylist 유지 — `SELECT @@VERSION`/`@@SPID` dialect=tsql 차단 실증(MSSQL 메타 열거 태세 불변). (5) 주석/난독화 — 제거 regex 는 comment 역할 없음(별도 `/*+*/`·`--`·multi-stmt 방어 불변).
- **backend/correctness — 인라인 REFUTED**: `SELECT @@x`/`@@GLOBAL.x`/`@@sql_mode` 전부 root `exp.Select` shape 게이트 통과(ALLOW 실증) · `collect_schema_refs('SELECT @@version')`=zero refs(= `SHOW VARIABLES` 동일 — 제품 allowlist 오차단/오허용 없음) · `SET GLOBAL sql_mode=''` → shape 게이트 "got Set" 정확 거부.
- **qa/regression — 인라인 REFUTED**: 신규 테스트 §5b 6케이스가 옳은 이유로 통과(sysvar SELECT 3=ALLOW / `SET @@`·`SET @a`=`\bSET\s+@` / `:=`=`:=` denylist / tsql `@@`=tsql denylist). golden/immutability 테스트 부재(전체 스위트 green — `test_mysql_dialect_golden_unchanged` 는 SQL 생성 골든이지 `_DENYLIST_PATTERNS` 카운트 아님). 전체 회귀 신규 실패 0(4 실패는 stash 대조로 baseline test debt=routine_dbanalysis/runtime_settings/batch8/runtime_settings_api — 내 diff 무관 실증).
- **수용된 잔여(설계상 의도)**: `SET GLOBAL x`(무-@@)·`SELECT @@x/**/y`(무해 sysvar read) 는 shape 게이트/AST 계층이 각각 정확 처리 — pre-existing, 본 diff 무영향.
- Human Approval: AskUserQuestion 2026-07-14 "제거 진행". Critical §12.3(sql_guard 허용범위) → PR/deploy 는 외부영향 confirm(override 불가).
- Cross-ref: CHG-20260714T153113-sysvar-select-guard(MODIFY) · 선행 REV-20260713T171821-readonly-query-shapes · FRICTION_LEDGER FR-sysvar-select-denylist-overblock(머지·배포 후 docs-only 후속 생성) · ANCHOR 0002 §1~§3 무충돌.
