---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

> 이전 기록(109건): [MODIFY-archive-20260711T120311.md](./_archive/MODIFY-archive-20260711T120311.md)

## CHG-20260625T012217-kb-pg-superuser-host (deploy infra fix, Minor §12.3)
- Date: 2026-06-25. **deploy/infra** — 코드·런타임 동작 무변경. 별도 worktree `ai/claude/kb-pg-superuser-host-fix`.
- Reason: `make up`(배포) 의 memory-init 단계가 `KB Postgres schema 적용 실패: FATAL: bouncer config error` 로 exit 1. 근본 원인 — `_ensure_pg_schema`(memory.py:854) 의 superuser DDL 연결이 `AGENT_KB_PG_SUPERUSER_HOST` 미설정 시 `AGENT_KB_PG_HOST(=pgbouncer)` 를 상속하는데, pgbouncer userlist 엔 DML role `agent_kb_rw` 만 등록(auth_query 없음)되어 superuser `postgres` 인증 불가.
- 진단(연결 실측): superuser `postgres` 직결(host=postgres)=OK / pgbouncer 경유=`bouncer config error` 재현 / 런타임 `agent_kb_rw`@pgbouncer=OK. KB 스키마는 이미 적용됨(15 tables, vector·pg_trgm) — 재적용 connect 만 실패하던 것.
- 변경: `.env.example` `AGENT_KB_PG_SUPERUSER_HOST=` → `=postgres` + 사유 주석(DDL 은 superuser 직결, pgbouncer 우회). 코드(memory.py)는 이미 본 변수를 1순위로 지원(line 854) — 설정만 누락이었음.
- 런타임 적용: 배포 환경 `.env`(gitignore, 본 PR 외)에 동일 라인 추가 후 `make up` **exit 0** 검증 완료(memory-init KB role/권한 검증 통과). `.env.example` 은 신규 배포 재발 방지용.
- Rollback: `.env.example` 1줄 revert. 코드·스키마 영향 0.
- Deploy: 없음(설정 문서). 런타임은 `.env` 수정 + `make up`(이미 수행).
## CHG-20260625T020410-gc-member-kick-ban (TASK-20260625T020410-gc-member-kick-ban — 멤버 차단 데이터 계층 cross-feature. feature-0003 주관, **Critical §12.3 — 접근제어**)
- Date: 2026-06-25. 주 변경·정본 changelog 은 feature-0003 CHG-20260625T020410-gc-member-kick-ban. 본 항목은 feature-0002-agent-core 교차변경(멤버십 차단 코어/스키마/마이그)만 교차 기록(§13.2.7).
- 변경(feature-0002):
  - `src/scripts/agent_runtime_schema.sql`: 신규 테이블 `agent_runtime.conversation_member_bans`(PK conversation_id+account_id, banned_at/banned_by_account_id/reason, FK core_conversations ON DELETE CASCADE) — 멱등 CREATE.
  - `alembic/versions/20260625_0018_conversation_member_bans.py`(revision `0018_conversation_member_bans`, down_revision `0017_table_column_descriptions`): 위 테이블 + **명시 GRANT**(agent_kb_rw SELECT/INSERT/UPDATE/DELETE, agent_kb_ro SELECT — superuser 적용 deploy-trap 회피, 0012 동형). downgrade=DROP TABLE.
  - `src/modules/group_members.py`: 신규 `ban_member`(INSERT ON CONFLICT DO UPDATE — 재차단 시 banned_at/by/reason 갱신, 멱등, reason 512cap)·`unban_member`(DELETE, rowcount)·`is_banned`(빈 cid/account 단락, row 유무)·`list_bans`(banned_at isoformat dict). 전 SQL `agent_runtime.conversation_member_bans` schema-qualified + `%(...)s`(ADR-0027). 기존 add/remove/role/list 함수 무변경.
  - `tests/test_member_kick_ban.py`: ban 함수 8 케이스(schema-qualified·upsert·reason cap·rowcount·빈인자 단락·isoformat·정렬).
- Why: feature-0003 의 owner 전용 차단(ban) 엔드포인트가 소비할 차단 목록 데이터 계층. 추방(kick)은 기존 `remove_member` 재사용이라 코어 변경 없음 — ban(영구 재참여 차단)만 신규 저장이 필요.
- Impact: 멤버십 read/add/remove·backfill·열람 게이트 무변경(순수 additive). ban 후 메시지/첨부 잔존(remove_member tombstone 동일). conversation 삭제 시 FK CASCADE 로 ban 정리.
- Rollback: alembic downgrade(DROP TABLE) + group_members 4함수·테스트 제거. 기존 멤버십 경로 무영향.
- Deploy: **alembic 0018 적용 필수**(superuser + GRANT). web 가 소비(별도 코어 데몬 재빌드 불요 — group_members 는 web import).

## CHG-20260625T045450-limit-subject-msg (요청량 한도 주체 구분 + 서비스 한도 메시지 provider명 제거 — cross-feature, feature-0002 주관, Minor §12.3)
- Date: 2026-06-25. 별도 worktree `ai/claude/limit-subject-msg`(base main). cross-feature(feature-0002 서비스 메시지·정본 / feature-0003 계정 메시지 cross-ref).
- 사용자 요청(/_template:entry): ① 요청량 한도 도달 주체 구분(계정 당 / 서비스 자체), ② 서비스 한도 메시지의 AWS Bedrock 언급 제거(서비스 자체 한도 명시).
- 변경(feature-0002):
  - `src/modules/llm_provider_health.py` `_build_restriction` KIND_THROTTLED 분기: `f"{plabel} 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."` → `"서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."`. provider 라벨(AWS Bedrock/로컬 LLM/LLM 제공자) 비노출 + "서비스 자체" 주체 명시. 사유 주석 3줄. 나머지 kind(credential_expired/auth_invalid/unavailable/unknown)는 관리자 진단용 plabel 유지 — 범위 밖.
  - `tests/test_llm_provider_health.py`: `test_throttled_message_is_service_level_without_provider_name` 추가(message 에 "Bedrock" 부재 + "서비스" 포함). 기존 throttle 테스트는 kind/retryable 만 단언 → 무회귀.
- Why: 서비스 사용자에게 내부 backend(AWS Bedrock) 명칭 노출은 부적절하고, "요청량 한도"가 계정 한도인지 서비스 한도인지 모호. 주체를 명시해 사용자 혼선·문의 감소.
- Impact: 응답 dict shape(kind/provider/message/retryable/error_tag/confirmed)·HTTP 429·분류 로직 무변경. PG 영속(llm_provider_health.message)에 새 문구 저장(글로벌 banner — confirmed=True 인 ThrottlingException). 순수 사용자 노출 텍스트.
- Verification: py_compile + `pytest test_llm_provider_health.py` 19/19 PASS + 렌더 확인.
- Files: `src/modules/llm_provider_health.py`, `tests/test_llm_provider_health.py`, `docs/{TASK,MODIFY,REVIEW}.md`. (+ feature-0003 `src/app.py`·`docs/{TASK,MODIFY,REVIEW}.md` 계정 메시지)
- Rollback: 2파일 revert(메시지 문구·테스트). 로직·계약 영향 0.
- Deploy: web + ask-worker 재빌드·재시작(메시지는 web app.py probe 와 agent_core 양쪽에서 생성). 마이그/스키마 없음.
## CHG-20260625T035655-init-embedding-latency (init "준비" 4s→50s 회귀 해소, **Major §12.3** — LLM provider/인프라·성능, cross-feature 0002·0007)
- Date: 2026-06-25. 별도 브랜치 `ai/claude/fix-init-embedding-latency`(main 체크아웃 infra-integration — embed-ollama 가 라이브 `repo-` compose 프로젝트에 속해야 gateway 도달 가능 → §13.2.7 F0 carve-out, `--skip-repo-immutability`).
- Reason: 사용자 보고 — LLM 응답 "준비(init)" 단계만 4초→50초(대기·추론 정상). init="준비"=`_build_knowledge_context` grounding 임베딩 구간.
- 근본원인(라이브 실측 3축): ① 2026-06-23 `litellm_config.yaml` 이 `titan-embed` 를 Bedrock Titan→공유 Ollama bge-m3(`ollama-edge`)로 전환(chat 을 Anthropic-direct 로 옮기며 AWS 자격 제거 → 임베딩만 401 → 로컬 대체). ② 공유 Ollama(`local-llm-edge`, 별도 `local_llm` 프로젝트) `OLLAMA_MAX_LOADED_MODELS=1` → 타 서비스 chat 모델이 bge-m3 를 축출 → 매 임베딩 cold 재로딩 **실측 27~37초**(warm 0.13초). ③ init 이 동일 질문을 sample_queries(few-shot)+account_recall 에서 **2회 중복 임베딩**(run-level 캐싱 없음) → ~50초.
- 변경:
  - `docker-compose.yml`: 전용 `embed-ollama` 서비스(ollama/ollama, bge-m3 단독, `OLLAMA_MAX_LOADED_MODELS=1`+`KEEP_ALIVE=-1`, WSL `/dev/dxg`+wsl libs GPU 패스스루, 전용 named volume `embed_ollama_models`, dbnet) + `volumes:` 섹션.
  - `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`: `titan-embed` api_base `ollama-edge:11434`→`embed-ollama:11434`(차원 1024 동일 — 백필/검색 호환). Bedrock Titan 복구 시 토글 후 embed-ollama 비활성 가능.
  - `unit/feature-0007-bedrock-llm-provider/src/scripts/embed-ollama-init.sh`(신규): 데몬 기동 + bge-m3 부재 시 pull + /dev/tcp warm-up(영구 상주).
  - `shared/config.py`: `AGENT_KB_QUERY_EMBED_TIMEOUT_SEC=20`(상호작용 질의 임베딩 fast-fail) + `__all__`.
  - `src/modules/kb_retrieval.py`: `_embed_query_vector(text, timeout_sec=None)` — timeout_sec→`_get_llm_client(timeout_sec=)`. 미지정 시 기존 동작.
  - `src/agent_core.py` `_build_knowledge_context`: 질의 임베딩 **1회 계산(`_shared_qvec`)→sample_queries·account_recall 공유**(fast-fail timeout 적용). 두 기능 OFF 면 임베딩 skip. user_message whitespace-normalize 후 임베딩(cosine(raw,norm)=1.000000 — 품질 무변).
  - `src/modules/sample_queries.py`·`src/modules/account_recall.py`: `query_vector` 인자 + sentinel `_QVEC_UNSET`("미제공→자체임베딩" vs "None→skip" 구분, 백워드호환). sample 의 `_embed(timeout_sec=)` 전달.
  - `tests/test_sample_flywheel.py`·`tests/test_account_recall.py`: 임베딩 mock 시그니처 `**k` 수용(timeout_sec).
- Impact: 준비(init) 임베딩 **~50초→0.13초**(전용 warm). chat(추론)·DB·기타 grounding(schema/glossary/metadata/table_insight=substring·ILIKE) 무영향. few-shot·account recall 기능·ds-scope 격리 보존(임베딩=f(text)).
- 검증: GPU 실효성 실측(bge-m3 1.2GB·100% GPU·warm 0.13s) + 단위테스트(통과; attachment_idor 4건 사전존재·무관) + 적대 backend 패널 ACCEPT-WITH-NITS(REV-20260625T035655) + 라이브 e2e(titan-embed gateway 0.13s, chat 정상).
- Rollback: litellm api_base 를 `ollama-edge`(또는 Bedrock 토글)로 환원 + embed-ollama 서비스/volume 제거 + 코드 변경 revert(전부 backward-compatible — 인프라만 환원해도 동작).
- Deploy(라이브 수행됨): embed-ollama up + bge-m3 pull + bedrock-gateway 재시작 + ask-worker/insight-worker/web `--no-cache` 재빌드·재생성.

## CHG-20260625T164701-ds-conn-circuit-msg (datasource 회로차단 사용자 안내 문구 분리 — cross-feature, feature-0002 주관, Minor §12.3)
- Date: 2026-06-25. worktree `ai/claude/ds-conn-unstable-copy`(원본 세션 entry "WEB_QA 데이터소스 연결 불안정 메시지 개선" 이 검증 중 API Overloaded 로 중단 → resume 로 재개·완수). 재개 시 main drift(`df97f47`/TASK-0011-9 가 db import 를 `modules.db`→`shared.db` 마이그레이션·`modules/db.py` 삭제) 흡수 후 현재 main 기준 재적용.
- Reason: 사용자 보고(2026-06-25) — `DatasourceCircuitOpen` 회로차단(한 datasource 일시 지연을 격리하는 보호 동작·자동복구)이 "DB 연결 실패/불안정/차단" 프레이밍으로 노출돼 WEB_QA 사용자가 서비스 고장으로 오인. 사용자 결정: 톤=투명형(격리 이유 설명), 용어="데이터소스".
- 변경:
  - `shared/db.py` `DatasourceCircuitOpen.user_message()`(신규): 사용자 화면 전용 문구("현재 연결된 데이터소스의 응답이 일시적으로 지연…다른 작업에 영향이 가지 않도록 잠시 대기…약 N초 뒤 자동으로 재연결…잠시 후 다시 요청"). `int(retry_after)+1`초만 보간 — scope_key/좌표/비밀번호 비노출. 생성자 `str(e)`(기술/로그)는 **미변경**(주석만 추가 — insight.py scan_outcome 가 타입 분류하되 문자열을 로그로 읽으므로 안정 유지).
  - `unit/feature-0002-agent-core/src/agent_core.py`: `DatasourceCircuitOpen` import + 멀티 datasource primary except·단일 datasource fallback except 두 곳에서 `isinstance(e, DatasourceCircuitOpen)` 시 `e.user_message()`, 그 외만 "DB 연결 실패".
  - `unit/feature-0002-agent-core/src/modules/tools.py`: `DatasourceCircuitOpen` import + `execute_tool` `router.conn_for(label)` 에 `except DatasourceCircuitOpen` 선행 분기(label 접두어 생략, 안내 문구만 반환).
- 범위: circuit 외 모든 연결오류는 기존 문구 그대로. raise 거동·예외 타입·응답 dict shape·분류(kind) 무변경. eval datasource 경로(None-gated 테스트 전용·운영 미도달) 의도적 제외. 메모리/control-plane 경로는 `datasource=None`(게이트 미적용)이라 circuit 미발생.
- 검증: §18.8 적대 패널(general-purpose outside voice — e 바인딩·except 순서·누락 surface·비밀노출·str(e) 안정성·테스트 회귀 6축 REFUTE) **BLOCKING 0**(REV-20260625T164701-ds-conn-circuit-msg) + py_compile + ruff All passed + 회귀(conn_health 타입 단언·tool/insight/datasource 153 PASS).
- Rollback: 3파일 revert(순수 additive — `user_message()` 메서드·import·isinstance 분기 제거 시 기존 "DB 연결 실패" 거동으로 환원). 데이터/스키마/마이그 변경 0.
- Deploy: 코드만(스키마·마이그·env 0). ask-worker(agent_core/tools)·web 재빌드(surface 경로). deploy_scope: included.
- Cross-ref: REV-20260625T164701-ds-conn-circuit-msg / FUNCTION ds-conn-circuit-msg / TASK-20260625T164701-ds-conn-circuit-msg.

## CHG-20260629T114221-describe-table-overlay-mssql (cross-feature, feature-0003 주관 — metadata-bootstrap-mssql-db; describe_table 컬럼 오버레이 MSSQL read 축 정합, Major §12.3)
- Date: 2026-06-29. worktree `ai/claude/metadata-table-desc-fix`(feature-0003 `/_template:resume` cycle). feature-0003 §18.8 panel 이 적발한 MAJOR(+재검증 BLOCKING)의 read-축 수정.
- Reason: feature-0003 부트스트랩이 MSSQL 컬럼 설명을 `schema_name=database`(예 GunzGame, 사용자 결정)로 저장하도록 규약을 바꿨는데, describe_table 도구 오버레이(`_tool_describe_table`)는 SQL 스키마(dbo)로 조회 → 축 불일치로 부트스트랩 컬럼 설명이 describe_table 출력에 미주입.
- 변경:
  - `src/modules/tools.py` `_tool_describe_table`: KB 오버레이 조회 시 `_dialects.active().name=="mssql"` 이면 조회 schema 를 `_cfg.get_active_default_db()`(pin primary DB, `_mssql_pin_gate` 와 동일 좌표)로, None 시 도구 schema 인자(dbo) 폴백. SQL introspection(describe_columns)·MySQL 경로 무변경.
  - `src/modules/kb_metadata.py` `load_column_descriptions_for_table`: schema 매칭을 case-insensitive(`LOWER(schema_name)=LOWER(%s)`, ORDER BY 도 LOWER)로 — `get_active_default_db()`는 소문자 정규화(gunzgame)인데 저장값은 원본 케이스(GunzGame)라 PG `=`(case-sensitive)로 대문자 포함 DB명이 0행이 되던 회귀(panel 2차 BLOCKING) 해소. 이 함수는 describe_table 오버레이 전용(다른 호출처 0).
- 범위: MSSQL describe_table 오버레이 조회 키·매칭만. 질문-시점 grounding(`load_table_column_descriptions`, Path B)은 schema 무관(substring 매칭)이라 무영향. MySQL 정확매치 ⊂ LOWER매치(무회귀). graceful({}) 유지.
- 검증: py_compile(tools.py·kb_metadata.py) PASS · §18.8 panel(general-purpose 적대) Path A 정합 복구 재검증.
- Rollback: tools.py 오버레이 키 분기 1블록 + kb_metadata.py LOWER 매칭 revert(기존 case-sensitive·schema 인자 직접 사용으로 환원). 데이터/스키마/RBAC 0.
- Deploy: ask-worker(tools.py·kb_metadata.py) 재빌드(deploy_scope: included).
- Cross-ref: feature-0003 CHG/REV/TASK-20260629T114221-metadata-bootstrap-mssql-db / config.py `get_active_default_db`(소문자 정규화) / kb_metadata.py `load_column_descriptions_for_table`.

## CHG-20260701T163000-graphview-render (cross-cut — 관리콘솔 그래프 뷰 마커 렌더-타임 갱신 백엔드분, Major §12.3)
- 변경: `src/modules/node_analysis.py` — `get_scope_analysis_status(scope_key, node_keys=None)` 추가. `node_analysis_jobs` 를 node_key 로 group_by + `bool_or(status='done')`/`bool_or(status IN ('pending','running'))` 집계 → `{done_keys, running_keys}`. `node_keys` 지정 시 `ANY(%s)` 부분집합. PG 미가용/예외 → None(코어 비차단, sibling `get_node_analysis` 동형 연결/close). 스키마·마이그·기존 함수 무변경.
- 용도: feature-0003 관리콘솔 그래프 뷰가 그래프 로드/검색/확장 직후 `GET /api/admin/metadata/graph/analyze/status` 로 이 함수를 호출해 스코프의 분석완료/진행중 노드 마커를 **클릭 없이** 렌더-타임에 적용(항목①). 엔드포인트·프론트는 feature-0003.
- Verification: `py_compile` PASS. 실 KB PG 정합 실측(scope `mssql-06656002eda6`: done 335·active 183·distinct 826, `accountdb`/`accountdb.GMRIP` done=t). 적대 코드리뷰 SHIP(REV-20260701T163000-graphview-render, feature-0003).
- Deploy: web 이미지 재빌드(deploy_scope: included — node_analysis 는 web·insight-worker 공용 모듈).
- Cross-ref: feature-0003 CHG/TASK/FUNCTION/TEST/REV-20260701T163000-graphview-render / feature-0016-metadata-graph TASK T16.

## CHG-20260703T093000-insight-load-spread (insight/graph 부하 분산 — 실패 대상 격리·재시도 backoff·batched/incremental graph sync, Major §12.3, cross-feature 0002·0016)
- 변경: `relationships.py`(probe 실패 격리 — `unknown database` regex→negative 파단, `_backoff_validated` transient 재프로브 backoff, `fetch_probe_candidates` backoff-window 제외), `insight.py`(datasource 순회 circuit-open `should_fast_fail` skip), `metadata_graph.py`+`scripts/metadata_graph_sync.py`(`sync_graph` batched commit + `since` incremental + `get/set_sync_watermark`, CLI `--incremental`/`--full`), `bin/metadata-graph-sync.sh`(인자 pass-through), `bin/install-metadata-graph-sync-cron.sh`(30분 incremental + 04:17 full), `.env.example`(knob 3 + jitter 문서화).
- 근본원인: circuit-open/없는DB(dblog)/timeout edge 를 매 tick(8s)·cadence 반복 probe/scan(격리·backoff 부재) + graph sync 57,000+ 요소 autocommit 개별 MERGE(30분 cron 5.7만 WAL fsync). 결과 gemma 545%·postgres WALSync 대기·워커 unhealthy·swap 압박.
- 스키마·마이그 **무변경**(table_relationships 기존 컬럼 + agent_runtime.kv 재사용). env 신규 3(backoff/batch/incremental) — 기본값 안전(미설정 시 정상 동작).
- Verification: 신규 단위 10 + 회귀 0(test_relationships 57·metadata_graph units 10·insight datasource/health 66) + AST/`bash -n`. 적대 backend+qa 패널(REV-20260703T093000-insight-load-spread).
- Deploy(외부영향 — 사용자 confirm): agent 이미지 재빌드(insight-worker baked, 마이그 없음) + insight-worker/local-llm-edge 재기동 + `sudo bin/install-metadata-graph-sync-cron.sh` 재설치.
- Cross-ref: feature-0002 REPORT/TASK TASK-0308 · feature-0016 REPORT "graph sync 부하 분산" · ANCHOR 0002 §3 / 0016 §1 무충돌.

## CHG-20260703-insight-heartbeat-liveness (insight-worker healthcheck false-negative 해소 — 진행-중 heartbeat throttle 갱신, Minor §12.3)
- 변경: `insight.py` — 신규 `_touch_worker_heartbeat_progress(mem_conn, min_interval_sec=30)` + `_scan_instance_schema_insights` 의 스키마 순회(`for schema in candidates`)·테이블 순회(`for table in selected_tables`)에 호출 삽입. cycle 진행 중 `insight_worker_last_cycle_at` 을 30s throttle 로 갱신.
- 근본원인: healthcheck(healthcheck_insight_worker.py age≤180s)·_is_insight_worker_heartbeat_fresh(age≤30s)가 heartbeat 를 cycle **완료 시각**으로만 보던 탓에, TASK-0308 claude 전환 후 9.4분+ 긴 cycle 이 stale→unhealthy 오판(false-negative — worker 는 활발히 생산 중).
- 스키마·마이그·healthcheck 판정식 **무변경**(heartbeat 갱신 지점만 추가). status 미변경(cycle 완료 finally 확정). hang 탐지 의도 보존(생성 정지 시 호출 경로 멈춰 stale→unhealthy).
- Verification: 신규 test_insight_heartbeat_liveness.py 2 + insight 회귀 0(12 PASS) + AST OK. 경량 cycle(§18.4) — 적대 패널 SKIPPED.
- Deploy(외부영향 — 사용자 confirm): agent 이미지 재빌드(insight-worker baked) + insight-worker 재기동 → docker inspect healthy 확인.
- Cross-ref: feature-0002 REPORT/TASK insight-heartbeat-liveness · TASK-0308(원인 유발 claude 전환) · REV [SKIPPED:heartbeat-throttle-liveness].

## CHG-20260706T013532-reasoning-effort (대화 화면 사용자 지정 추론 강도 — agent-core 요청 단위 thinking 주입 배선, Major §12.3, cross-feature primary=feature-0003)
- 변경(cross-feature edit — 코드 거주 feature-0002, primary/문서 정본 = feature-0003-agent-web-ui): `agent_core.py` — `run_agent`/`_run_agent_core` 에 `reasoning_level` kwarg 추가(양쪽 kwonly 말미), `_call_llm` 에 `reasoning_level` 파라미터 + thinking 지원 모델(claude-*)일 때만 `kwargs["extra_body"]={"thinking":{"type":"enabled","budget_tokens":N}}` 주입. `modules/ask.py` `_payload_to_kwargs` 에 `reasoning_level` 복원(worker 경로 패리티).
- import: `shared.model_catalog` 에서 `model_supports_thinking`·`thinking_budget_for_level` 추가 import. budget=None(미지정/미상) 또는 비-claude 모델이면 주입 안 함(config 기본값 유지, 무해).
- 매핑(shared/model_catalog): 낮음=2000·높음=10000·매우높음=16000 override, **일반=override 없음**(모델 config 기본 유지, B1 회귀 방지). budget(≤16000) < agent max_tokens(20000, `_CLAUDE_MAX_TOKENS["agent"]`) — Anthropic 요구 만족(litellm 이 budget≥max_tokens 도 내부 보정하나 애초에 만족). thinking 활성 시 temperature 는 claude alias 에서 이미 미전달이라 정합. 주입은 메인 agent 경로(_call_llm)만 — 보조 호출(summary/topic/validate via `_openai_chat_completion_with_deadline`)은 무변경(의도).
- Verification: 신규 `tests/test_reasoning_effort.py` 12 PASS(매핑·정규화·B1 no-override 가드·주입 4분기·제약·worker parity) + 전체 스위트 회귀 0. B2 라이브 게이트웨이 프로브로 extra_body.thinking override 실증(budget 1024 vs 16000 → reasoning 2073자 vs 6914자, 동일 프롬프트).
- Files: `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/src/modules/ask.py`
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260706T013532-reasoning-effort(정본) · shared/docs/MODIFY.md CHG-20260706T013532-reasoning-effort · feature-0003 REVIEW.md REV-20260706T013532-reasoning-effort

## CHG-20260707T100640-no-edge-conversation-answer (대화 답변 경로 edge(gemma) 폴백 완전 차단 — 명백한 실패처리, Major §12.3, conversation_audit FR-edge-fallback-conversation-context-loss)
- Date: 2026-07-07. `/_dqa:conversation_audit` 진단(conv …9e0883bb "DB 설계 및 JSON 데이터 구성 검토", owner admin, 1:1). 사용자 명시 불만("? 맥락을 잃어버렸나요?") + 데이터 삼각측량으로 근본 확정.
- 근본원인: turn2~4 가 요청 모델 `claude-haiku-4` 인데 실제 서빙(llm_usage.resolved_model)이 `gemma4:e2b`(로컬 edge-fallback, ctx 4096)로 silent 강등. prompt_tokens 세 턴 모두 정확히 **4096**(turn1=29K)로 ~30K 토큰 대화 히스토리가 잘려 맥락 완전 소실 → assistant 가 방금 자기가 쓴 리뷰(4339)조차 모른 채 무관한 일반론 환각 + "기억한다"고 거짓 부인(I-FALSE). 원인 체인 = litellm fallback `claude-haiku-4 → root → edge-fallback(gemma)`, 두 claude 계정 429(오늘 rate-limit 버스트) 시 gemma 우회. 2026-07-04 "대화 무중단 안전망" 결정의 산물이나, gemma 는 대화를 유지가 아니라 **silent 파괴**. 재발경로 = infra capacity → degradation 정책.
- 사용자 결정(2026-07-07, AskUserQuestion): "assistant 답변에 edge/gemma 는 전혀 고려 대상이 아니며 fallback 도 구성돼선 안 된다 — 명백한 실패처리로 구성. gemma 개입을 완전히 끊어라." → 2026-07-04 무중단(gemma keep-alive) 결정을 **대화 답변 경로에 한해 override**(insight 배치·분석은 유지).
- 변경(cross-feature edit; 코드 거주 primary=feature-0002, config=feature-0007, 헬퍼=shared):
  1. `agent_core.py` `_call_llm`(정의상 task='agent' 답변 경로): litellm 에 보내는 `model` 을 `conversation_answer_model(model)` 로 치환 — `claude-haiku-4` → edge-free 대화 전용 alias `claude-haiku-4-chat`. 표시·저장·usage `model` 컬럼·max_tokens·thinking·vision 판정은 **원본** `model` 유지(무회귀), 실제 서빙은 resolved_model 로 추적. import 1줄 추가.
  2. `shared/model_catalog.py`: `conversation_answer_model()` + `_CONVERSATION_ANSWER_ALIAS`(claude-haiku-4→chat) + `__all__` 등록. 순수 additive. 매핑 밖 model(claude-sonnet-4 — 애초에 fallbacks 목록에 없어 edge 강등 無)은 identity.
  3. `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`: deployment `claude-haiku-4-chat`(claude-corp)·`claude-haiku-4-chat-root`(root) 신설(haiku-4-5·thinking 5000, 동일 OAuth). fallback `{"claude-haiku-4-chat": ["claude-haiku-4-chat-root"]}` — **edge 없음**, chat-root 는 fallback 미등록 → 양 계정 401/429 시 그 에러를 raise. 기존 `claude-haiku-4`·`-interactive`·`edge-fallback` 체인 **무변경**(insight 배치·분석 gemma 강등 유지).
- 깨끗한 실패 경로(기존 재사용): 두 계정 실패 → litellm raise → `_run_agent_core` LLM-error 핸들러가 `classify_llm_provider_error`(429→KIND_THROTTLED)로 "서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요." 로 치환 + provider health 기록 후 break. gemma 답변 원천 차단.
- Verification: 신규 `tests/test_conversation_answer_no_edge_alias.py` 4 PASS(헬퍼 매핑·identity·_call_llm→chat 라우팅·기록 원본 유지·sonnet 무변경) + feature-0002 전체 스위트 회귀 0(재사용 agent 이미지). py_compile·litellm YAML lint OK. ⚠ feature-0003 `test_route_parity_p5b` 는 재사용 이미지의 Starlette 버전 drift 로 실패하나 **clean main(repo/)에서도 동일 실패** 확인 → 환경 artifact(내 diff 에 웹 라우터·golden 무변경), 정본 `make test`(핀 deps) 에선 통과.
- 라이브 실측 필요분(§정직): 코드/테스트는 "대화 답변이 edge-free alias 로만 나가고 실패 시 깨끗이 안내" 증명. "실제 rate-limit 상황에서 gemma 미개입" 은 배포 후 corroboration 재측정(task='agent' resolved_model gemma 분포 0 유지)으로 확인.
- Files: `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/tests/test_conversation_answer_no_edge_alias.py`
- Deploy(외부영향 — 사용자 confirm, Major override 불가): ask-worker + web 재빌드(baked 코드) + bedrock-gateway 재생성(litellm_config bind-mount 반영). deploy-stage 격리 확인.
- Rollback: litellm_config 의 -chat/-chat-root deployment·fallback 제거 + `conversation_answer_model` 매핑을 identity 로(또는 _call_llm 치환 제거). insight/분석 무영향이라 부분 롤백 안전.
- Cross-ref: shared/docs/MODIFY.md CHG-20260707T100640-no-edge-conversation-answer · feature-0007 MODIFY.md CHG-20260707T100640-no-edge-conversation-answer · feature-0002 REVIEW.md REV-20260707T100640-no-edge-conversation-answer · FRICTION_LEDGER FR-edge-fallback-conversation-context-loss · ANCHOR 0002 §1~§3 / 0007 §1~§2 무충돌(가드·자격 경계 불변, 폴백 경로 축소만).
## CHG-20260706T094937-runtime-settings (TASK-20260706T094937-runtime-settings — 런타임 설정 live 타임아웃 getter + 모델별 thinking budget 주입, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-06 (worktree ai/claude-corp/feature-0018-runtime-settings). 문서 정본/전체 맥락은 feature-0003/docs (관리 콘솔 `시스템 > 설정`).
- `src/modules/llm.py`: AGENT_TIMEOUT_SEC 을 `_get_llm_client`/`_openai_request_timeout` 내부에서 `runtime_settings.get_int("AGENT_TIMEOUT_SEC")` 로 읽어 관리 콘솔 저장값을 **즉시 반영**(live). `_openai_request_timeout(AGENT_TIMEOUT_SEC)` 호출부 5곳은 인자 생략(→ live fallback, 무override 시 동치). AGENT_INSIGHT_TIMEOUT_SEC 등 restart-mode 는 기존 상수 유지(config.py 가 기동 시 스냅샷 반영).
- `src/modules/mcp_client.py`: MCP 요청 timeout 을 `runtime_settings.get_int("MCP_TIMEOUT_SEC")` 로 read(live).
- `src/agent_core.py` `_call_llm`: 사용자 지정 추론강도(reasoning_level)가 없을 때 `runtime_settings.model_thinking_budget_override(model)` 로 관리자 설정 모델별 budget 을 요청 단위 `extra_body.thinking` 주입. override 미설정이면 미주입 → 모델 config 기본 thinking 유지(**B1 무회귀**, reasoning-effort 정합). budget 은 `min(budget, max_tokens-1024)` 로 clamp(Anthropic budget<max_tokens 안전; 기존 reasoning-effort 값은 no-op).
- 무override 시 전 경로 기존 동작 동치(회귀 0). 상세·검증은 feature-0003/docs/TEST.md·REVIEW.md.

## CHG-20260707T130000-reasoning-budgets (TASK-20260707T130000-reasoning-budgets — _call_llm 추론 강도별 budget override, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-07. `src/agent_core.py` `_call_llm`: 요청 thinking budget precedence 를 확장 — 명시 추론강도(low/high/max)면 `runtime_settings.reasoning_budget_override(level)` 우선(없으면 `thinking_budget_for_level` 기본), '일반(normal)'/미지정이면 `model_thinking_budget_override(model)`(기존). '일반'은 thinking_budget_for_level 이 None 이라 레벨 예산 분기 미진입 → 레벨 예산이 절대 주입되지 않음(**B1 무회귀**). budget<max_tokens clamp 유지. 신규 `test_reasoning_effort.py` +3(precedence). 워커(ask/insight) 경로 동일 함수라 자동 적용.
- Cross-ref: feature-0003·shared MODIFY/REVIEW 동일 slug.

## CHG-20260707T134500-bedrock-chat-alias-probe-artifact (investigation, no-op — feature-0002/0007 cross-ref, CHG-20260707T100640 후속)
- Date: 2026-07-07. `bedrock-gateway` 로그의 `claude-haiku-4-chat`/`-root` 1회성 `max_tokens must be greater than thinking.budget_tokens`(400, 10:37:18 KST) 오류를 조사. 배포 타이밍 재구성(PR #600 머지 10:28:41 → gateway 재생성 10:31:02 → ask-worker/insight-worker 이미지 재빌드 10:32:18) + 실패 시각의 실행 이미지를 직접 열어 이미 수정 코드 보유 확인(stale-image 가설 기각) + 정적 코드 추적(`_call_llm` 이 유일 caller, claude-* 모델엔 항상 `max_tokens=20000` 주입 — 충돌 코드 경로 없음) + 게이트웨이 라이브 재현(`max_tokens<5000` 일 때만 동일 오류 재현, `≥5000`/미지정은 정상) 으로 **코드 결함 아님** 확인. FRICTION_LEDGER 의 "live probe(claude-haiku-4-chat→claude 확인)" 절차가 `max_tokens` 를 충분히 싣지 않고 보낸 **1회성 프로브 아티팩트**로 결론(재발 0, 실 사용자 트래픽 영향 없음).
- Files: 코드 변경 없음. Docs: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(FR-edge-fallback-conversation-context-loss addendum) · `unit/feature-0002-agent-core/docs/REPORT.md`(신규 절).
- Cross-ref: FR-edge-fallback-conversation-context-loss(CHG-20260707T100640) 후속 조사.

## CHG-20260710T232503-alembic-multihead-gate (parallel-work-structure ITEM-02 — 병렬 마이그레이션 번호 경합 머지 전 적발 + 해소 자동화)
- Date: 2026-07-10. 병렬 브랜치 동번호 마이그레이션(0036 실충돌, 6263e641 수동 re-parent)이 머지 후에야 발견되던 것을 3중 장치로 전환: ① `bin/migrate-lint.sh` 에 head 단일성/번호 중복/MAX 정합 정적 검사(`--heads` 신설 + 기존 diff/`--all` 모드 상시 편입 — versions/*.py AST 파싱, 라이브 DB 불필요) + self-test 4 케이스(총 10) ② `.github/workflows/ci.yml` test job "Migration gate" 스텝(머지 게이트) ③ `versions/MAX_MIGRATION.txt` 의도적 충돌 파일(최신 head 1줄 — 병렬 head 생성 시 git 머지에서 반드시 충돌 → CI 전 fail-fast, RESEARCH W-005 django-linear-migrations 패턴). 해소 자동화: `bin/alembic-reparent.sh <file> <새번호>`(파일명·revision·down_revision 3곳 원자 치환 + MAX 갱신 + lint 재검, guard: origin/main 미머지 파일만).
- Files: `bin/migrate-lint.sh`(+~180) · `bin/alembic-reparent.sh`(신설) · `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt`(신설, `0039_enum_feedback`) · `.github/workflows/ci.yml`(스텝 1) · `unit/feature-0002-agent-core/docs/MIGRATIONS.md`(규약 절).
- 검증: TEST.md §3 "alembic-multihead-gate" — self-test 10/10 · 현행 39체인 PASS · 중복 0040 재현 FAIL→reparent 1회 복원 · 병렬 브랜치 MAX 충돌 재현. DB 스키마 무변경(마이그레이션 0건 — 도구·게이트만).
- Cross-ref: `docs/improvements/parallel-work-structure/ROADMAP.md` ITEM-02 · REV-20260710T232503-alembic-multihead-gate.

## CHG-20260711T120311-docs-archive (MODIFY/REVIEW §5.5 아카이빙)
- Date: 2026-07-11. §5.5(20건 초과)·§5.6 임계 적용 — MODIFY 124건(109 이관)·REVIEW 109건(94 이관), verbatim·무손실 md5 증명·가역. feature-0003 선례 동일 스크립트.
- Files: docs/MODIFY.md·REVIEW.md·_archive/ 2파일·REPORT.md·TASK.md.

## CHG-20260713T140405-describe-routine-tool (저장 프로시저/함수 정의 조회 전용 도구 신설, Major §12.3, conversation_audit FR-show-create-routine-blocked)
- Date: 2026-07-13. `/_dqa:conversation_audit` (사용자 명시 호출). 대화 "재사용 쿼리의 PK 관리 문제 추가 리뷰" 에서 `SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence` 가 `execute_sql` sql_guard(SELECT/CTE-only)에 (의도대로) 차단돼 assistant 가 프로시저 로직 검토에 막힘.
- Reason(RC): **L2(거부 피드백 교정 힌트 부재) + capability gap** — 거부 메시지가 루틴 정의 조회 경로를 안내하지 않고, LLM 노출 도구(핵심 4개)에 루틴 본문 조회 수단이 없었다. sql_guard 의 SELECT/CTE-only 는 의도된 핵심 보안 기능(F4)이라 **불변 유지**; 정의 열람 접근 자체는 이미 `information_schema` always-allow 로 열려 있었으므로(막힌 것은 SHOW CREATE 구문형태) 신뢰경계 확장 없이 전용 도구로 봉인.
- 사용자 승인 방식: **Option 1**(전용 도구 + 유도) — AskUserQuestion(2026-07-13). Critical 취급 → 승인 후 구현.
- Changes:
  - `src/modules/dialects.py`: `Dialect.routine_definition/routine_parameters`(base) + MySQLDialect(information_schema.ROUTINES/PARAMETERS) + MSSQLDialect(INFORMATION_SCHEMA.ROUTINES + OBJECT_DEFINITION, 4000자 절단 회피). 엔진 무관 컬럼 계약. 파라미터 쿼리에 `ROUTINE_TYPE`(pr[4]) 포함(MySQL 동명 proc+func 파라미터 격리용·MSSQL NULL).
  - `src/modules/tools.py`: `_tool_describe_routine`(=`_safe_ident` 정제 + `_struct_schema_access_error` allowlist/내부스키마 게이트 + `_raw_execute_sql`, 다른 구조화 도구와 동일 신뢰경계, 다중 def_rows 시 ROUTINE_TYPE 로 파라미터 필터) · `_TOOL_HANDLERS["describe_routine"]` · **핵심 `TOOL_DEFINITIONS`(LLM 실노출) 에 도구 정의 추가(4→5)** · `_routine_introspection_redirect`(L2 힌트) + `_tool_execute_sql` 거부 메시지 append · `import re` · **`_safe_ident` 역슬래시(`\`) strip 추가**(§18.8 security 패널 MAJOR — pre-existing MySQL 리터럴 breakout 근본 봉인, 구조화 도구 전반 소급 방어).
  - `src/agent_core.py`: `_derive_step_work`/`_derive_step_reason` 에 describe_routine 케이스 추가(§18.8 qa 패널 MINOR — 런타임 narration fallback 일관성).
- Recurrence sealing: `model limit`(거부 피드백 교정 힌트) → 거부 시 describe_routine 유도 정형화 + capability gap → 전용 구조화 도구. sql_guard/allowlist/RBAC/PII 경계 불변(보안 회귀 0 — test_query_guard/test_sql_trust_boundary/test_mssql_security_boundary 재통과). 신뢰경계 방어선 강화: `_safe_ident` 역슬래시 봉인.
- §18.8 적대 패널(security+backend+qa) 결과: MAJOR 1(백슬래시 인젝션)·MINOR 2(파라미터 교차오염·narration fallback) 전건 **수정 완료**, 나머지 REFUTED(safe/correct). 상세 REV-20260713T140405-describe-routine-tool.
- 검증: `tests/test_describe_routine_tool.py`(신규, 백슬래시·파라미터격리 보강) + 보안 가드 3파일 재통과 + 전체 스위트 RC=0. py_compile clean.
- Cross-ref: feature-0003 `_conv_store.py` `_derive_step_work` narration 라벨(companion, graceful fallback) · FRICTION_LEDGER FR-show-create-routine-blocked · REVIEW REV-20260713T140405-describe-routine-tool · ANCHOR 0002 §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

## CHG-20260713T151500-describe-routine-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-13. CHG-20260713T140405 후속 — PR #749 merge(main `6841eba2`) 후 배포 완료.
- 배포: `make deploy-web`(web-a/web-b 무중단 롤링 → 6841eba2, soak 90s 통과) + `docker compose build`(GIT_COMMIT=6841eba2)·`up -d --force-recreate` ask-worker/insight-worker. **4서비스 GIT_COMMIT=6841eba2**(ask-worker/web-a/web-b healthy). **런타임 실증**(ask-worker 컨테이너 Python import): `describe_routine`∈TOOL_DEFINITIONS·`_TOOL_HANDLERS`·`_safe_ident("x\\")=="x"` 전부 확인. web `/healthz` git_commit=6841eba2·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(프로시저 정의 요청 재현)은 미수행 → 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-show-create-routine-blocked · REV-20260713T151500-describe-routine-deploy.

## CHG-20260713T171821-readonly-query-shapes (read-only 쿼리 shape 과차단 보정: 최상위 UNION + 읽기전용 SHOW, Critical §12.3, conversation_audit FR-readonly-query-shapes-overblock)
- Date: 2026-07-13. `/_dqa:conversation_audit "동적 쿼리 및 테이블 변경사항 추가 리뷰"` — "여전히 유사한 이슈… '보안 정책상 차단된 SQL'". describe_routine(FR-show-create-routine-blocked)이 봉인 못 한 같은 클래스의 넓은 재발.
- Reason(RC): **L5 — sql_guard SELECT/CTE-only shape 게이트가 read-only 패턴 과차단**. 대상 대화(PG agent_runtime `20260713074503-5cef7aa2`) 차단 = SHOW CREATE TABLE(테이블 DDL 리뷰)·SHOW VARIABLES(config). corroboration **structural**(최근 30일 9 distinct conv·14건: UNION 8·Show 5·parse 12·multi 4). 실질 보안(쓰기·allowlist·금지함수·multi-statement)은 shape 와 무관 — 정확히 read-only 패턴만 넓힘.
- 사용자 승인: **UNION + 읽기전용 SHOW**(AskUserQuestion 2026-07-13). Critical → 승인 후 구현.
- Changes:
  - `src/modules/sql_guard.py`: `_READONLY_SHOW_KINDS`(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS — **PROCEDURE/FUNCTION 제외=describe_routine 담당**) + `_show_kind`/`_show_target_db`/`_validate_readonly_show`. `validate_sql_for_sandbox`: (a) `exp.Show`→read-only 화이트리스트 검증(+대상 `.db` forbidden 차단) (b) `exp.SetOperation`(UNION/INTERSECT/EXCEPT) shape 허용 (c) lock/into 를 **모든 SELECT 분기**(`root.find_all(Select)`)에 적용. 기존 4-part/forbidden-schema/forbidden-function 검사는 이미 find_all 로 union 분기 전수 순회(불변). `collect_schema_refs`: SHOW `.db` 수집(제품 allowlist 강제 경로).
  - `src/modules/tools.py`: `_dialect_correction_hint` 의 stale "최상위 UNION 불가" tip 제거(오정보 방지).
  - `src/modules/sql_guard.py`(§18.8 security 패널 MAJOR 흡수): `_WRITE_NODE_TYPES`+`_find_write_node` — accepted shape 트리 전체(CTE 본체·서브쿼리·union 분기)에서 write/DDL/command 노드 스캔 거부. **데이터 수정 CTE**(`WITH c AS (DELETE/INSERT/UPDATE … RETURNING) SELECT … c`)가 With→Select shape 로 통과하던 pre-existing 잠복(RO GRANT·엔진 미지원 backstop 이나 guard authoritative 원칙)을 봉인. read-only 트리 false-positive 0 실측.
- Recurrence sealing: guard shape 가정 오류 → read-only allowlist 정확 확장 + write-node defense-in-depth. **보안 회귀 0**: UNION 분기별 forbidden-schema/lock/into/금지함수 차단 유지, 비-read-only SHOW(GRANTS/DATABASES/PROCESSLIST)·SHOW forbidden schema·DELETE/DDL/multi-statement/INTO·데이터수정CTE 계속/신규 차단. 계속 차단(의도, F4): multi-statement·parse-fail(별도 RC 이연)·db_id/db_name(MSSQL enum).
- 검증: `tests/test_readonly_query_shapes.py`(신규) + `test_gc_dialect_context.py`(UNION 교정 tip 제거 반영) + 전체 회귀 pytest. §18.8 적대 패널 REV-20260713T171821-readonly-query-shapes.
- Cross-ref: FRICTION_LEDGER FR-readonly-query-shapes-overblock(+ FR-show-create-routine-blocked 후속) · REVIEW REV-20260713T171821 · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260713T173000-readonly-query-shapes-deploy (배포 완료 기록 + 원장 생성, docs-only)
- Date: 2026-07-13. CHG-20260713T171821 후속 — PR #761 merge(main `9892fc3b`) 후 배포 완료.
- 배포: worker 이미지 `docker compose build`(GIT_COMMIT=9892fc3b) + `up -d --force-recreate` ask-worker/insight-worker + `make deploy-web`(web-a/b 무중단 → 9892fc3b, soak 통과). **4서비스 GIT_COMMIT=9892fc3b** running/healthy. **런타임 가드 실증**(ask-worker `import modules.sql_guard`): UNION·SHOW CREATE TABLE·SHOW VARIABLES 허용 / 데이터수정CTE·UNION-agent_memory분기·SHOW GRANTS 차단 확인. web `/healthz`=9892fc3b·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `FR-readonly-query-shapes-overblock` 엔트리 생성(fixed:deployed:unverified-live) + REPORT cross-ref + TASK 체크박스. 라이브 대화 실측은 다음 audit.
- Cross-ref: FRICTION_LEDGER FR-readonly-query-shapes-overblock · REV-20260713T173000-readonly-query-shapes-deploy.

## CHG-20260713T185846-attach-update-versioned (첨부 파일 갱신: 명시적 갱신요청 → 새 첨부 버전 전달 선호, Major §12.3, conversation_audit FR-attachment-update-pasted-not-versioned)
- Date: 2026-07-13. `/_dqa:conversation_audit "첨부파일 갱신"` — 사용자 지시: assistant 가 개선안 제안 후 명시적 갱신 요청이 있으면 쿼리를 답변으로 붙여넣지 말고 첨부 파일의 새 버전으로 전달하고, 갱신 파일명을 원본과 정합(버전 접미)하게.
- Reason(RC): **L1 프롬프트 (data/config drift + model limit)**. attachment-edit 전달 메커니즘(TASK-0275/0286, 2026-06-15/16 출하)은 이미 존재하나 프롬프트 지침이 (a) "corrected file back"으로 좁게 게이팅 (b) "brand-new SQL → ```sql 무방"([agent_core.py:152](../src/agent_core.py))·일반 SQL 출력 지침과 경쟁 (c) **코드 상수 안에** 있어 운영자 `WebSystemPrompts` global row 가 상수를 통째 대체할 때 프로덕션에서 약해짐. corroboration **structural**(PG core_messages/attachments 90일: text/csv 첨부 갱신요청 34대화 중 assistant 버전 생성 성공 3(~9%) vs ```sql 붙여넣기+버전無 27(~79%); assistant 버전 생성 전 기간 4건뿐; 기능 출하 후에도 7월 이후 7대화 지속 → F3 기각).
- 사용자 승인: **Scope A**(AskUserQuestion 2026-07-13). Major(코어 LLM 경로) → PLAN-APPROVED 후 구현.
- Changes(feature-0002 primary):
  - `src/agent_core.py` — SYSTEM_PROMPT "DELIVERING THE EDITED FILE" 섹션 강화(A1): 명시적 갱신요청(this turn OR earlier) → attachment-edit **필수**, "brand-new SQL" 예외가 편집을 삼키지 않음 명시, `filename` **생략** 유도(시스템 자동 버전명명), source 미첨부 시 재첨부 요청(붙여넣기 fallback 금지).
  - `src/agent_core.py` — `_ATTACHMENT_DELIVERY_DIRECTIVE` 신설 + `compose_system_prompt` `parts` 에 base 뒤 **항상 코드-주입**(A2, `_INJECTION_GUARD_NOTICE` 선례=AUTH-1a). 운영자 global row 가 코드 상수를 대체해도 강화 계약이 프로덕션 도달 → drift 봉인.
- Recurrence sealing: data/config drift → 코드 권위선(항상 주입) + model limit → 프롬프트 계약 정형화. 가드/RBAC/PII/데이터소스 불변(materialize 가드 미변경 — conv/account scope·ext 강제·size cap·text-only 그대로). **보안 회귀 0**.
- 검증: `tests/test_compose_system_prompt.py`(신규 케이스: directive 항상 주입·global override 시에도 존재) + 전체 회귀 pytest. §18.8 적대 패널 REV-20260713T185846-attach-update-versioned.
- Cross-ref: **feature-0003** `_conv_store.py` 파일명 코드-권위 정규화(secondary, CHG-20260713T185846-attach-filename-consistency) · FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · REVIEW REV-20260713T185846 · ANCHOR 0002 §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

## CHG-20260714T031500-attach-update-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-14. CHG-20260713T185846-attach-update-versioned 후속 — PR #771 merge(main `ee4f8de6`) 후 배포 완료.
- 배포: `make deploy-web`(web-a/web-b 무중단 롤링 → ee4f8de6, soak 90s 통과, 롤백 0) + `docker compose build`(GIT_COMMIT=ee4f8de6)·`up -d --no-deps --force-recreate` ask-worker/insight-worker. **4서비스 GIT_COMMIT=ee4f8de6**(전부 running/healthy). **런타임 실증**: ask-worker(A1 SYSTEM_PROMPT attachment-edit 강화·brand-new SQL 예외·filename 생략 True + A2 `_ATTACHMENT_DELIVERY_DIRECTIVE` FILE UPDATE REQUESTS True) / web-a(A3 `_next_version_filename('report_v2.csv',3)=='report_v3.csv'` 이중접미 방지·safe_ext×5·base_for_naming×3). web `/healthz` git_commit=ee4f8de6·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(갱신요청 대화 붙여넣기 감소·버전 생성 비율 상승)은 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · REV-20260714T031500-attach-update-deploy.

## CHG-20260714T153113-sysvar-select-guard (MySQL 시스템 변수 읽기 @@ denylist 과차단 해소, Critical §12.3, conversation_audit FR-sysvar-select-denylist-overblock)
- Date: 2026-07-14. `/_dqa:conversation_audit "초기화 쿼리 환경 옵션 검토"` — 사용자 보고: 쿼리 실행 중 "보안 정책상 차단..." 재발.
- Reason(RC): **L5 sql_guard 보조 denylist 가정 오류**. `_DENYLIST_PATTERNS`(MySQL)의 `@@` regex 가 read-only 시스템 변수 SELECT(`SELECT @@lower_case_table_names, @@version`)를 차단. CHG-20260713T171821 로 read-only `SHOW VARIABLES/STATUS`(동일 정보 클래스, 오히려 전체 변수 노출)가 사용자 승인 하에 허용된 뒤라 **태세 불일치 잔재**. 거부 힌트도 "단일 SELECT/CTE 만 허용"이라 오도(해당 쿼리는 단일 SELECT) — assistant 가 SHOW VARIABLES 재시도 없이 OS 기본값 추정으로 대체, 사용자의 "환경 옵션 직접 확인" 명시 요구 좌절.
- corroboration: 30일 차단 시그니처 집계(PG agent_runtime.core_messages) — `denylist:@@` 1건/1대화(2026-07-14, 어제 배포 후 유일한 차단). 빈도 idiosyncratic 이나 **근본이 코드 정본(file:line) confirmed(high) + 태세 불일치 명백 + 재발 경로 확실**(환경 옵션 점검은 초기화 쿼리 리뷰 workflow 의 상시 단계) → 명백한 구조결함 fix-now. Critical → 사용자 승인(AskUserQuestion 2026-07-14 "제거 진행").
- Changes:
  - `src/modules/sql_guard.py`: `_DENYLIST_PATTERNS`(MySQL)에서 `re.compile(r"@@")` 제거 + 사유 주석(read-only SHOW 화이트리스트와 동일 정보 클래스·쓰기는 SET @/:= + shape 게이트가 차단·T-SQL @@ 유지). MySQL 어휘 "골든: 무변경" 헤더 주석은 본 변경으로 무효화되어 문구 정리.
  - `tests/test_readonly_query_shapes.py` §5b: `SELECT @@x`/`@@GLOBAL.x`/`@@sql_mode` 허용 + `SET @@`/`SET @a`/`SELECT @a := 1` 차단 유지 + tsql `SELECT @@VERSION` 차단 유지.
- 보안 회귀 0 근거: (1) 노출 확대 0 — `SHOW VARIABLES/STATUS` 가 이미 전체 시스템 변수를 노출(승인된 태세), `SELECT @@x` 는 그 부분집합. (2) 쓰기/할당 전 경로 불변 — `SET`(shape 게이트: SELECT/CTE/SET_OP/SHOW 외 거부)·`SET @` denylist·`:=` denylist. (3) T-SQL(MSSQL) denylist `@@` 유지 — 메타 열거 차단 태세 불변(test_mssql_security_boundary.py:66 green). (4) 컨테이너 시뮬레이션 + 타깃 테스트 4파일(129 tests) PASS 실측.
- §13.1 동시수정 기록: feature-0002 표준 worktree 를 병렬 세션이 점유(FR-partial-evidence-false-verification, tools.py/agent_core.py) → 본 cycle 은 `ai/claude/feature-0002-sysvar-guard` worktree 로 격리(파일 교집합 0).
- Cross-ref: FRICTION_LEDGER FR-sysvar-select-denylist-overblock(머지·배포 후 docs-only 후속에서 생성) · 선행 CHG-20260713T171821-readonly-query-shapes · REVIEW REV(§18.8 패널, 본 cycle) · ANCHOR 0002 §1~§3 무충돌.
