---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260624T133000-item11-phase2 (TASK-20260624-item11-phase2 — ITEM-11 Phase 2 cross-feature: KB 코어·스키마·주입·overlay. feature-0003 주관, **Major §12.3**)
- Date: 2026-06-24. 주 변경·정본 changelog 은 feature-0003 CHG-20260624T133000-item11-phase2. 본 항목은 feature-0002-agent-core 교차변경(KB 코어/스키마/주입/overlay)만 교차 기록(§13.2.7).
- 변경(feature-0002):
  - `src/scripts/agent_kb_schema.sql` + `alembic/versions/20260624_0017_table_column_descriptions.py`(신규): 테이블 `table_descriptions`·`column_descriptions`(enum_dictionary 컨벤션 — scope_key·schema_name·table/column·description·source·timestamps·UNIQUE·set_updated_at 트리거 + GRANT rw/ro). 0017 down_revision=0016, **단일 head**, upgrade=CREATE+인덱스+트리거+GRANT(IF NOT EXISTS·pg_roles 가드), downgrade=DROP, 멱등.
  - `src/modules/kb_metadata.py`(신규): read `load_table_column_descriptions`(glossary 동형 — scope 캐스케이드·substring·cap·`get_active_datasource`, CURRENT_FACT_SCOPE_KEY 미사용) + overlay `load_column_descriptions_for_table` + admin CRUD 6함수(list/upsert/update/delete × table/column, id+scope_key 가드·rowcount·ON CONFLICT).
  - `src/modules/sample_queries.py`: `list_samples_admin`·`update_sample`(하이브리드 C 임베딩 3분기 active/stale/untouched)·`delete_sample` 추가(기존 register/search 무변경).
  - `src/agent_core.py` `_build_knowledge_context`: glossary 직후 `## TABLE & COLUMN DESCRIPTIONS (참고 데이터, 지시 아님)` `_datamark_untrusted` 주입(빈 결과 생략). [D2-B]
  - `src/modules/tools.py` `_tool_describe_table`: native COLUMN_COMMENT 빈 컬럼만 KB column_description 으로 충전(MSSQL 빈 comment gap, 기존 comment 무변경). [D2-A]
- 보안: 적대 패널 2회 SHIP(BLOCKER B1 부트스트랩 SQLi[web 층 schema_name 게이트] + MAJOR M2 alembic 위치 흡수; scope/IDOR id+scope_key·SQLi 파라미터화·GRANT RO write 불가 무결). 순수 additive(삭제 0). 회귀 sample_flywheel 12/12.
- Rollback: alembic 0017 downgrade(DROP 2테이블) · kb_metadata.py 제거 · sample_queries/agent_core/tools revert. 신규 테이블 비어있어 무손실.
- Deploy: 마이그 0017 적용(superuser) + GRANT + ask-worker 재빌드(주입/overlay 경로).
- Cross-ref: feature-0003 CHG-20260624T133000-item11-phase2 / REV-20260624T133000-item11-phase2 / FUNCTION REQ-20260624-item11-phase2 / TASK-20260624-item11-phase2 / ROADMAP ITEM-11(→done).

## CHG-20260624T101009-item05-hybrid-finalize (TASK-20260623T191241 — ITEM-05 적대 리뷰 fix 흡수 + 가치 입증 측정 + gated-OFF 마감)
- Date: 2026-06-24 (TASK-20260623T191241 ITEM-05 마감, **Major §12.3**). CHG-20260623T191241 초기 fusion 구현의 후속 — 적대 backend 리뷰 + 사용자 "가치 입증 후 마감" 지시 반영.
- 변경:
  - `modules/kb_retrieval.py` `_fuse_rag_documents` — **REV 적대 backend 리뷰 fix 흡수**: ① 병합키 `(conv,fact)`→`(conv,fact,content)` + 동일 키 max 누적(**MAJOR** — schema unique `(conversation_id,fact_key)` 와 어긋나 동일 factkey·다른 content 2 행 시 정답 유실) ② trigram sim 절대 하한 `AGENT_KB_HYBRID_TRIGRAM_FLOOR`(0.05) 미만→신호 0(**MINOR-1** — 무관 distractor 정규화 부풀림 차단) ③ 정규화 span-0(단일 후보)→raw 값 fallback(**MINOR-2** — ft_score 0 왜곡 제거).
  - `modules/config.py`: **`AGENT_KB_HYBRID_ENABLED` 기본 `1`(ON)→`0`(OFF)** — 가치 입증 측정 반증 결과 gated-OFF dormant(아래). `AGENT_KB_HYBRID_TRIGRAM_FLOOR`(0.05) 신규.
  - `tests/test_hybrid_search.py`: MAJOR 회귀 `test_fusion_same_factkey_different_content_not_merged`(len==2·distinct ft_score) +1(10→11), `test_fusion_normalize_off_vec_dominates` 기대값 0.41→0.40(floor 의도 동작) 갱신.
  - `tests/eval/kb_eval/{provision_kb_adv.py,golden_retrieval_adv.yaml,retrieval_eval_adv.py}`(신규) + `adv_artifacts/*.json`: **적대적 retrieval corpus**(evalkb_adv 격리, 24 docs/12 질문 = rare-token·opaque-code·검증된 vector-miss 3 tier, 정답에만 rare exact token + token-없는 의미-유사 distractor — fusion-favorable 의도 설계) + A/B·파라미터 sweep 러너.
- 측정(가치 입증 — 사용자 "가치 입증 후 마감"): 적대 corpus A/B(fusion ON vs 2-tier) + sweep(NORM on/off × α/β = 0.6/0.4·0.5/0.5·0.7/0.3·0.3/0.7·0.4/0.6) → **모든 지표 +0.0000(MRR 1.0 both), 12/12 정답 rank=1 — lift 반증(REFUTED)**. 근본 원인(격리 cosine 실측): bge-m3 가 subword/char 인지라 질문의 rare token 이 정답 doc cosine 도 함께 끌어올려(벡터·trigram 同방향 합의) fusion 이 바꿀 top rank 없음 — fusion-favorable 과 vector-miss 가 양립 불가. fusion 가치는 임베더-장애/미임베딩 폴백(이미 qvec None 폴백 커버)에 국한.
- 마감 결정(사용자 2026-06-24): **gated-OFF dormant + done**. 기본 OFF 라 운영 거동 불변(2-tier 유지). fusion 코드·eval 자산은 비회귀 안전 + 임베더-장애 폴백 보험으로 dormant 보존. 실가치 재측정은 라이브 운영 질의 로그 필요(ITEM-12 튜닝 근거 현 corpus 론 없음).
- 불변/보존: tuple shape(8-col)·`_normalize_rag_doc_rows`·scope 격리(evalkb/evalkb_adv, 운영 KB 무오염·측정 후 purge)·`_pg_connect_ro` least-priv. 코어/gateway/litellm 무변경.
- Verification: `tests/test_hybrid_search.py` 11/11 + `tests/test_kb_read_backend.py` 9/9(2-tier 회귀 0) + py_compile. 적대 backend 리뷰 REV-20260623T191241(下단 §) SHIP-WITH-FIXES.
- Files: src/modules/{kb_retrieval,config}.py, tests/test_hybrid_search.py, tests/eval/kb_eval/{provision_kb_adv.py,golden_retrieval_adv.yaml,retrieval_eval_adv.py,adv_artifacts/}, docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- 롤백: 기본 OFF 라 별도 롤백 불요(켜려면 `AGENT_KB_HYBRID_ENABLED=1`).
- Cross-ref: CHG-20260623T191241(초기 구현) / REV-20260623T191241 / ROADMAP ITEM-05(→done).

## CHG-20260623T191241-item05-hybrid-search (TASK-20260623T191241 — ITEM-05 하이브리드 검색 score fusion)
- Date: 2026-06-23 (TASK-20260623T191241, **Major §12.3** — 핵심 KB read 랭킹 경로 변경 + 측정 게이트)
- 변경:
  - `modules/kb_retrieval.py`: `_load_rag_documents_for_request_pg` 를 2-tier(vector-OR-trigram fallback) → **fusion** 으로. gate `AGENT_KB_HYBRID_ENABLED`(기본 ON) + qvec 존재 시 신규 `_fuse_rag_documents` 호출(vector+trigram 둘 다 → (conversation_id, fact_key) union 병합 → score=α·vec+β·trigram → 내림차순 → `_normalize_rag_doc_rows`). gate OFF 면 기존 2-tier 경로 그대로(롤백 안전). 폴백 보존: qvec None→trigram-only(기존), vec·trg 둘 다 0→None 반환 후 trigram-only fall-through.
  - 스케일 정규화: 측정상 vec(cosine)·trigram(pg_trgm) sim 의 분포 척도가 달라(한국어 trigram 은 ~0.01~0.2 低대역) raw 가중합이 vec 에 지배 → `AGENT_KB_HYBRID_NORMALIZE`(기본 ON)로 각 신호 query-단위 min-max([0,1]) 후 가중합. OFF=raw.
  - `modules/config.py`: `AGENT_KB_HYBRID_ENABLED`(ON) · `AGENT_KB_HYBRID_ALPHA`(0.6) · `AGENT_KB_HYBRID_BETA`(0.4) · `AGENT_KB_HYBRID_NORMALIZE`(ON) 추가. (__all__ 미등록 — 직접 import.)
  - `tests/test_hybrid_search.py`(신규, FakeConn/monkeypatch — 라이브 DB·임베딩 불요) 10 케이스.
  - `tests/eval/kb_eval/{provision_kb,golden_retrieval.yaml,retrieval_eval,__init__}`(신규): evalkb scope 격리 KB retrieval A/B eval set(ITEM-01 자산 인접). `Makefile` `kb-retrieval-eval` 타깃.
- 불변/보존: tuple shape(8-col …,ft_score)·`_normalize_rag_doc_rows`·병합키((conversation_id, fact_key))·scope 필터(blank/NULL 등가)·`_pg_connect_ro` least-priv read. feature-0002 외 코어·gateway/litellm·ROADMAP 무변경.
- 측정: 라이브 bge-m3 k=3 — fusion vs 2-tier Δ(precision/recall/f1/MRR) 전부 +0.0000(NEUTRAL, 회귀 없음). 강한 임베더가 깨끗한 합성 KB 를 포화 → headline 상승 헤드룸 없음(REPORT.md 상세, 은폐 없음).
- 롤백: `AGENT_KB_HYBRID_ENABLED=0`(2-tier 복귀) / `AGENT_KB_HYBRID_NORMALIZE=0`(raw 가중합).
- **후속**: 적대 backend 리뷰 fix 흡수 + 가치 입증 측정(반증) + gated-OFF 마감 → CHG-20260624T101009-item05-hybrid-finalize.

## CHG-20260618-0318 (TASK-0304 — 무거운 쿼리 사전 감지 + LLM 재작성 코칭)
- Date: 2026-06-18 (TASK-0304, **Major §12.3** — datasource 실행 거동 + LLM 행동(시스템 프롬프트))
- Scope: TASK-0299 SHOWPLAN/EXPLAIN 부하추정을 활용해, 무거운 쿼리를 실행 전 가로채고 LLM 이 더 가벼운 쿼리로 재작성해 목적을 달성하도록 거동 변경. 추정/게이트 *메커니즘*은 불변(TASK-0299), 메시지 프레이밍 + 시스템 프롬프트 + 운영 모드(gate)만 변경. 보안경계(allowlist/sql_guard/RBAC) 변경 0.
- 근본: gate=하드차단(막다른 길)·warn=사후경고(부하 이미 발생) 둘 다 "LLM 이 미리 감지해 가벼운 쿼리로 목적 달성" 의도와 불일치. 사용자 결정 "가로채고 LLM 재작성".
- 변경:
  - `agent_core.py` SYSTEM_PROMPT: "QUERY LOAD — STAY LIGHT, ACHIEVE THE GOAL WITH THE CHEAPEST QUERY" 섹션 추가 — 처음부터 효율적 쿼리(필요 컬럼만·WHERE·서버측 집계·표본 LIMIT/TOP), 큰 조회 전 explain_query 자가확인, 게이트 표시 시 confirm_heavy 강행 금지·더 가벼운 동등 쿼리로 재작성(tool 루프 내, 사용자엔 차단 미노출), confirm_heavy=최후수단.
  - `tools.py` gate 메시지: "차단합니다" → "실행하지 않았습니다 + 같은 목적 유지하며 더 가벼운 쿼리로 재구성해 다시 실행" 코칭(재작성 우선·confirm_heavy 후순위). execute_sql/confirm_heavy 도구 description 동반 정렬. 게이트 *로직*(가로채기·fail-closed·must_estimate)은 불변.
  - 토큰 보존: 기존 테스트 단언("무거운 쿼리"/"confirm_heavy=true") 유지 → 게이트 메커니즘 회귀 0.
- 운영: `AGENT_QUERY_GUARD_MODE=warn → gate` 승격(.env, 배포 시) — TASK-0299 검증으로 MSSQL 2개 모두 SHOWPLAN 보유 확인되어 fail-closed 위험 없음. 라이브 WebSystemPrompts global row 도 갱신(코드 상수=seed, DB row=라이브 truth).
- Files: src/agent_core.py, src/modules/tools.py, tests/test_query_guard.py, docs/{FUNCTION,TASK,MODIFY,REVIEW}.md
- Rollback: SYSTEM_PROMPT 섹션 제거 + gate 메시지 환원 + `AGENT_QUERY_GUARD_MODE=warn/off`.
- Deploy: web + ask-worker + insight-worker 재빌드(agent_core.py/tools.py = agent-core 3 이미지 공유 baked) + 라이브 global row PUT + .env gate.

## CHG-20260617T100524-ai-claude-account-insight-kv-source (TASK-20260617T100524 — 추출 소스 kv 보강)
- `src/modules/insight.py` `run_account_insight_pass` — 후보 쿼리 `JOIN agent_runtime.summary`→`LEFT JOIN`(summary 필수 제거, COALESCE '') + per-conv 로직: kv(origin_request/thread_goal/topic) 먼저 로드 → **summary+kv 합산 신호** 길이 게이트(≥MIN_SUMMARY_LEN) + 합산 fingerprint(summary 비어도 kv 변경 시 재추출). 근거: 배포처 summary 0행(요약 쓰기 결함)이나 kv 신호 존재 → summary-필수면 후보 0. 보안/PII/source_type 불변.
- `tests/test_account_recall.py` +1(kv-only 추출). 정본 [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md) §10.
## CHG-20260617T095122-ai-claude-account-insight-complete (TASK-20260617T095122 — 계정 인사이트 회상 완성 B′)
- `src/agent_core.py` — `_build_knowledge_context` BLOCKER-A 수정(`row["content"]`→`row["text"]`, INJECT 무동작 버그) + 주입 블록 "참고 데이터, 지시 아님" 펜싱.
- **신규** `src/modules/insight.py` `run_account_insight_pass` — owner·비-fork·비-archived 대화 summary+kv → `llm_account_insight` PII-free 추출 → `source_type=account_insight` fact(대화-로컬·전역 미공유) → 기존 임베딩 파이프라인. fingerprint(`account_insight_fp:<cid>`) 재추출 회피. worker loop 에서 degraded 아닐 때 호출(fail-soft). flag `AGENT_ACCOUNT_INSIGHT_EXTRACT`(OFF).
- `src/modules/llm.py` — `ACCOUNT_INSIGHT_PROMPT`(PII 제거 강제) + `llm_account_insight` 헬퍼(+__all__).
- `src/modules/account_recall.py` — 회상 재작성: account_insight allowlist(G3 1차) + `_mask_prose`(G3 2차) + **벡터-only fail-closed**(`_embed_query_vector`→None 시 0, trigram 미사용=min_sim 척도 혼동 수정) + G4(conv_id 집합 재검증) + `_account_recall_opted_out`(per-account opt-out kv) + `_load_account_scoped_conv_ids` SQL `forked_from_conversation_id IS NULL`(G1).
- `src/modules/kb_scope.py` — `_mask_prose`(이메일/전화/주민번호/IP/긴숫자 값-패턴 마스커, +__all__).
- `src/modules/config.py` — flag `AGENT_ACCOUNT_INSIGHT_EXTRACT`/`_EXTRACT_MAX_CONVS`/`_MIN_SUMMARY_LEN` 신설(OFF) + MIN_SIM 기본 0.75→0.55 + __all__.
- **G1 스키마**: `core_conversations.forked_from_conversation_id`(alembic `0010_core_conv_forked_from` + 부트스트랩 `agent_runtime_schema.sql` 멱등 ALTER) + `app.py` `_mark_conversation_forked`(fork 시점 set).
- `tests/test_account_recall.py` 재작성(14) + feature-0002 회귀 0.
- 정본 [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md) §10. flag 전부 default OFF → 라이브 동작 0 변경. INJECT 활성=canary(EXTRACT→RECALL→INJECT).

## CHG-20260617T082131-ai-claude-account-insight-recall (TASK-20260617T082131 — 계정 스코프 cross-conversation 인사이트 회상 Phase 1, shadow)
- **신규** `src/modules/account_recall.py` — `_load_account_scoped_conv_ids`(owner_account_id 로 계정 소유 과거 대화 conv_id 도출, G2 가드: NOT NULL·archived 제외·현재 대화 제외·`__global__` sentinel 제외, `_pg_connect_ro` least-priv, fail-soft) + `recall_account_conv_facts`(기존 `_load_rag_documents_for_request_pg` 벡터 회상 재사용 + min_sim/top_k, RECALL flag OFF=no-op).
- `src/modules/config.py` — flag 5종 신설 **전부 default OFF**: `AGENT_ACCOUNT_INSIGHT_RECALL`/`INJECT`/`MAX_CONVS`(20)/`TOP_K`(3)/`MIN_SIM`(0.75) + `__all__` 등록.
- `src/agent_core.py` — `_build_knowledge_context` 에 `account_id`/`conversation_id` optional 파라미터 + shadow 회상 호출(INJECT flag OFF 면 회상만, 컨텍스트 미주입; 예외 fail-soft). 호출부(run loop)에서 account_id/conversation_id 전파. **두 flag 기본 OFF → 기존 동작 0 변경.**
- `src/modules/kb_backend.py` — `search_rag_documents_vector` docstring stale 주석 정정(`vector(1024) Titan v2` → `vector(1536) text-embedding-3-small`).
- `tests/test_account_recall.py` (신규 10) — 계정 격리·owner NULL/sentinel/현재대화 제외·account 무효·PG 미가용·flag OFF no-op·min_sim/top_k·exclude 전파.
- 설계 정본 `docs/DESIGN-account-insight-recall.md`. **INJECT 활성화는 본 cycle 범위 밖**(G1 fork 표식·G3 PII 마스커 선행 필수).

## CHG-20260617-0310 (TASK-0299 — MSSQL 사전 부하추정 SET SHOWPLAN_ALL)
- Date: 2026-06-17 (TASK-0299, **Major §12.3** — datasource 실행/보안 경로)
- Scope: MSSQL datasource 부하 게이트를 EXPLAIN-미지원 일괄 차단(`supports_load_estimate=False`)에서 **SHOWPLAN_ALL 추정 기반**으로 전환. MySQL 동작 0 변경(골든). 보안경계(allowlist/sql_guard/RBAC/엔드포인트) 변경 0.
- 근본: MSSQL 은 EXPLAIN 구문이 없어 사전 부하추정 불가 → gate=무거운/가벼운 쿼리 무차별 fail-closed 차단(과보호), warn/off=무방어. MySQL 처럼 *추정* 으로 무거운 쿼리만 게이팅 필요(사용자 요청).
- 변경:
  - `dialects.py`: `MSSQLDialect.supports_load_estimate=True`, `gate_fail_closed_on_estimate_error=True`. `_showplan(run, sql)` = `SET SHOWPLAN_ALL ON` → sql(미실행, 추정 plan) → `finally` 로 `OFF` 보장(**세션 poison 방지 Codex-7**: 공유 conn 에 SHOWPLAN 잔존 시 이후 실쿼리가 데이터 대신 plan 반환=조용한 오염). `estimate_load_rows`=plan 의 `EstimateRows×EstimateExecutions` 최대 operator. `explain_plan`=plan result_sets. MySQL `estimate_load_rows`/`explain_plan` 은 기존 `EXPLAIN {sql}` 산식 그대로 이관(`_parse_explain_rows_product`). 구 `explain()` 메서드 제거(두 신규 메서드로 대체).
  - `tools.py`: `_estimate_explain_rows` 를 엔진무관 wrapper 로(dialect 에 `_run` 실행 콜백 주입 — dialects 가 db/tools 미import, 계층 보존). 게이트 `must_estimate` 재구조화 — confirm_heavy=true 면 추정 생략이 기본이나 **fail-closed 엔진(MSSQL)은 추정 강제 수행해 None 이면 confirm 무관 차단**(M-4/Codex-6 맹목 confirm 무력화), 추정 성공 known-heavy 만 confirm override 허용. `_tool_explain_query` 엔진별(`explain_plan`)+MSSQL SHOWPLAN 요약(`_format_mssql_showplan`). 게이트 메시지·도구 description 엔진중립화(예상 처리 행수).
  - `bin/datasource-mssql-ro-bootstrap.sql`/`-multidb.sql`: `GRANT SHOWPLAN` 추가(데이터 읽기 아님·추정 plan 생성만 → 최소권한 RO deny-by-default 양립) + 검증 라인. 미부여 시 gate=안전차단/warn·off=무경고 graceful degrade.
- 보안: SHOWPLAN 은 본 쿼리를 실행하지 않음(부하 0). 추정 실패 fail-closed(gate)로 현행 안전 보존, confirm_heavy 우회 차단(Codex-6). sql_guard/allowlist 가 SHOWPLAN 전 단계 게이트 유지.
- Files: src/modules/{dialects,tools}.py, bin/datasource-mssql-ro-bootstrap{,-multidb}.sql, tests/{test_mssql_load_estimate(신규),test_mssql_security_boundary,test_multi_datasource}.py, docs/{FUNCTION,TASK,MODIFY,REVIEW}.md, DESIGN-multi-datasource.md
- Rollback: `MSSQLDialect.supports_load_estimate=False` 복귀 시 구 일괄 fail-closed 동작(코드 단일 플래그). 또는 운영상 `AGENT_QUERY_GUARD_MODE=off`.
- Deploy: web + ask-worker + insight-worker 재빌드(dialects.py/tools.py = agent-core 3 이미지 공유 baked). RO 부트스트랩 SQL 은 운영자가 각 MSSQL 서버에서 재실행(SHOWPLAN 부여) — gate/warn 운영 시 필요.

## CHG-20260616-0300 (TASK-0290 evidence — 라이브 검증 기록, docs-only)
- Date: 2026-06-16 (TASK-0290 evidence, 코드 무변경)
- Scope: TEST.md 에 TASK-0290 배포·라이브 검증 결과 기록.
- 변경: 배포(web+ask-worker+insight-worker 재빌드 + up -d 콜드 스타트 재현) 후 HTTP `/api/admin/datasources` conn_status 실측 — mysql-mv-qa-* unstable(1744~1793ms, 콜드 스타트에도 빨강 유지)·mysql-kr-an2-* down(5s timeout errno=2003 진짜 도달불가)·gz-qa-kr healthy. 구 2000ms 의 콜드 down 오판 제거 실증.
- Files: docs/TEST.md
- Deploy: 없음(검증 기록만).

## CHG-20260616-0299 (TASK-0290 — conn-tristate TCP 선검사 timeout 상향)
- Date: 2026-06-16 (TASK-0290, Minor §12.3 — 연결 상태 분류 정확도)
- Scope: conn_health TCP 선검사 timeout 기본값 2000→5000ms. RBAC/스키마/엔드포인트/SQL추출 0.
- 근본(라이브 실측 repo-web-1): web 재시작 콜드 스타트 시 14개 datasource(10개 타-리전)를 워커 4개로 동시 probe(thundering herd) → 첫 TCP 핸드셰이크 spike 가 2000ms 를 살짝 초과(mysql-kr-an2-* 실측 2003~2237ms) → 2회 연속 실패 → down(회색) 오판. mysql-mv-qa-*(TCP 195ms+DB 1749ms, 본래 unstable=빨강)도 콜드 시 일시 down → 사용자가 "버튼이 연결 안 됨처럼" 인지.
- 변경: config.py `AGENT_CONN_TCP_TIMEOUT_MS` 기본 2000→5000(주석에 실측 근거 기록). 5s 면 콜드/원거리 RTT spike 흡수 → 연결 가능한 느린 서버를 unstable(빨강, "연결 불안정") 유지. 진짜 죽은 서버(errno=2003, 5s 도 timeout)는 down(회색) 정확 유지. 30s 는 죽은 서버가 워커 4개를 점유해 모니터 라운드를 지연시키는 성능 이슈 → 5s 채택(사용자 결정 "30초가 성능 이슈면 5초로").
- 검증: 라이브 probe 재현(docker exec) — mv-qa TCP 5s 통과+DB 1749ms→unstable, kr-an2 5s 도 timeout(errno=2003)→down. 배포 후 콜드 스타트 모니터 분류 확인(TEST.md).
- Files: src/modules/config.py, tests/test_conn_health.py(fixture·기본값 검증 2000→5000 정합), docs/{TASK,MODIFY,REVIEW,TEST}.md
- Rollback: AGENT_CONN_TCP_TIMEOUT_MS 기본 2000 복귀 (또는 .env `AGENT_CONN_TCP_TIMEOUT_MS=2000` override).
- Deploy: web + ask-worker + insight-worker 재빌드(config.py = agent-core 3 이미지 공유 baked). config 는 .env 우선이라 즉시 검증 시 .env override 후 재시작도 가능.

## CHG-20260616-0295 (TASK-0286 — SYSTEM_PROMPT attachment-edit 파일화 안내)
- Date: 2026-06-16 (TASK-0286, **Major §12.3** — feature-0003 주관, agent_core 는 SYSTEM_PROMPT 만 변경)
- 변경: `src/agent_core.py` SYSTEM_PROMPT 에 "DELIVERING THE EDITED FILE — ATTACH IT, NEVER PASTE THE WHOLE BODY" 섹션 추가 — assistant 가 첨부 파일 수정본을 전달할 때 ⓐ 변경점은 ```diff```, ⓑ 전체 수정본은 ```attachment-edit```(헤더 JSON + 본문, 사용자 미노출·첨부 새 버전 저장), ⓒ 전체 본문을 일반 코드블록으로 붙이지 말 것을 지시. 기존 "SHOWING CHANGES — diff" 섹션과 공존.
- 비변경: tool 정의·run 로직·실행 경로 0(프롬프트 텍스트만). **라이브 반영은 WebSystemPrompts global row 멱등 갱신 필수**(상수=seed/fallback).
- 검증: py_compile agent_core.py + make test 전체 회귀 0. 상세는 feature-0003 REPORT/REVIEW(REV-20260616-0295).
- Files: src/agent_core.py

## CHG-20260615-0255
- Date: 2026-06-15 (TASK-0255, **Major §12.3** — 공유 연결 인프라 db.py + 신규 PG 테이블. insight 연결 탄력성 R1/R2/R3)
- Scope: agent-core — `config.py`(신규 knob), `db.py`(control-plane bounded timeout), `insight.py`(R1 로그 edge-trigger + R2 PG 영속), `alembic/versions/20260615_0006_datasource_health.py`(신규), `agent_runtime_schema.sql`(§6c) + cross-feature web(feature-0003 app.py/admin.js/admin.html — 별도 CHG).
- 변경:
  - **R3**: `AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC`(기본 10) + `_controlplane_connect_timeout()`. db.py control-plane(datasource=None) MySQL params 의 `connection_timeout` 및 `_pg_connect`/`_pg_connect_ro` 의 `connect_timeout` 을 AGENT_TIMEOUT_SEC(300s)→bounded 10s. **breaker 미적용**(timeout 만 — MEMORY_DB fast-fail=전체 마비 차단). data-plane(_dataplane_connect_timeout) 불변.
  - **R1**: `_LAST_DS_SCAN_STATUS`(모듈 dict, 단일 insight-worker 프로세스) + `_ds_scan_status_changed()`. run_insight_cycle except 블록을 edge-trigger(상태 전이 시 WARNING, 지속 DEBUG)로 — 매-cycle 도배 제거. `DatasourceCircuitOpen` 을 `_is_perm` 보다 먼저 분기. 예외 로그 `err=%r,_ds_exc`→`%s,str()[:160]`(자격증명 비노출). registry 동기 prune(stale key 누수 차단).
  - **R2**: 신규 `agent_runtime.datasource_health`(scope_key PK, status/last_scan_outcome/fail_count/last_error_tag/host/port — **자격증명 비영속**). `_persist_datasource_health`(soft telemetry — PG 미가용/실패해도 cycle 무영향, registry prune) + `_record_ds_health`(conn_health.status_for 권위 status). alembic `0006`(down=`0005_core_conv_blocked`) + 부트스트랩 §6c + **명시 GRANT**(baseline GRANT 미포함·superuser 적용 trap — agent_kb_rw INSERT/agent_kb_ro SELECT).
- 위험/회귀: db.py control-plane 변경은 datasource=None 전 경로 영향(로컬·신뢰 호스트라 안전, 회귀 가드 테스트). R2 는 soft telemetry(격리). breaker 불변식 보존.
- 검증: `make test` GREEN(19 신규 + 회귀). adversarial 5-lens SHIP_WITH_FIXES → REV-20260615-0255.

## CHG-20260612-0248
- Date: 2026-06-12 (TASK-0248, **Major §12.3** — 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환; 주 변경은 web feature-0003 CHG-20260612-0248. 본 항목은 **스키마/마이그레이션 영향만**)
- Scope: agent-core — `agent_runtime.core_conversations` 에 차단 플래그 컬럼 2개 additive 추가(데이터 무손실 — 기존 행 blocked_at=NULL=미차단).
- 변경:
  - `src/scripts/agent_runtime_schema.sql`: `core_conversations` CREATE TABLE 에 `blocked_at timestamptz`/`blocked_reason varchar(256)` + 기존 테이블 self-heal 용 멱등 `ALTER ... ADD COLUMN IF NOT EXISTS`(alembic 미적용 환경).
  - `alembic/versions/20260612_0005_core_conv_blocked.py`: **신규 마이그레이션**. revision=`0005_core_conv_blocked`, down_revision=`0004_rag_objects_datasource`. UPGRADE=`ADD COLUMN IF NOT EXISTS blocked_at timestamptz`/`blocked_reason varchar(256)`, DOWNGRADE=DROP COLUMN IF EXISTS. **web 컨테이너는 DML-only role 이라 런타임 ALTER 불가 → 본 마이그레이션(superuser offline SQL)이 PG 정본 적용 경로**.
- 비변경: agent-core 런타임 코드(insight/ask/agent_core)·다른 스키마·index/trigger/FK 0. 차단 가드는 전부 web `/api/ask`(feature-0003)에서 enqueue 前 수행, PG upsert 는 blocked 컬럼 미참조.
- 검증: py_compile(alembic 0005) + make test 컨테이너 전체 회귀 0. Cross-ref: feature-0003 CHG-20260612-0248 / REV-20260612-0248 / TASK-0248. 배포 시 `make migrate`(alembic 0005) 를 web 재빌드 *전* 적용.

## CHG-20260612-0250
- Date: 2026-06-12 (TASK-0250, **Major §12.3** — 연결 health 모니터; 동시세션 0248·0249 선점→§13.1 재번호 0250)
- Scope: agent-core — TASK-0247 in-process breaker 를 **background Connection Health Monitor** 로 진화. 한 datasource 불안정이 단일 직렬 ask-worker(및 관리 콘솔 probe)를 점유해 정상 datasource 요청을 막던 잔여 경로를 background 사전판정으로 차단.
- 변경:
  - `src/modules/conn_health.py` **신규** — `_STATE`(scope_key→status, 좌표/비번 없음)+`_LOCK`; `_tcp_probe`(raw socket); `_is_blocked_target`(SSRF 상시차단: 메타데이터/loopback/link-local fail-closed); `_apply_result`/`_prune_state`; `should_fast_fail`(gate, monitor_running 가드); `record_foreground_result`(피드백); `register`/`status_for`/`snapshot`/`_reset_state`; `_Monitor`(daemon scheduler + daemon worker pool + queue, `_refresh_targets`/`_worker`/`_probe_target` **2단 probe**=TCP 선검사+실제 DB connect+SELECT 1); `start_monitor`/`stop_monitor`/`monitor_running`. 비밀번호는 `_Monitor._targets`에만 보유(상태/snapshot/로그 비노출).
  - `src/modules/config.py`: 신규 `AGENT_CONN_*` 9 env(HEALTH_ENABLED/PROBE_TIMEOUT_MS_BASE/_MAX/HEALTHY_RECHECK_SEC/UNSTABLE_RECHECK_SEC/_MAX_SEC/PROBE_WORKERS/HEALTH_TICK_SEC/STALE_GRACE_SEC). **dead `AGENT_DB_BREAKER_*` 3 제거**(TASK-0247 breaker 흡수).
  - `src/modules/db.py`: `connect_with_retry` 가 `conn_health.should_fast_fail` gate + `record_foreground_result` 피드백(`_record_health` 격리)으로 전환. 구 breaker 내부(`_breaker_admit`/`_BREAKER_STATE`/`_breaker_safe`/`_breaker_trial_timeout` 등) 제거, `_breaker_key`/`_is_connect_breaker_failure`/`_dataplane_connect_timeout`/`DatasourceCircuitOpen` 유지.
  - `src/modules/datasources.py`: `health_probe_provider`(memory 연결로 전체 ds dict[비번 포함] 반환, db lazy import). 구 `list_for_health_probe`(좌표만) 폐기.
  - `src/modules/ask.py`/`src/modules/insight.py`: worker 루프 시작 전 `conn_health.start_monitor`(insight 는 daemon, ask 는 종료 시 stop).
- 비변경: control-plane(memory DB, `datasource=None`) 게이트 미적용(동작 0 변경). 풀(TASK-0144)·replica·RBAC·스키마 무변경. probe_datasource 는 connect_with_retry 미경유(모니터 자기 gate 회피).
- 검증: 신규 `test_conn_health.py` 21 PASS(2단 probe·B1 회귀·SSRF 차단·gate·backoff·prune·비노출·db 통합) + make test 컨테이너 회귀 0 + ruff clean. outside-voice 2-pass 적대 리뷰(REV-20260612-0250) NOT-SHIP→SHIP-WITH-FIXES. 구 `test_db_circuit_breaker.py` 제거(breaker 흡수).

## CHG-20260612-0249
- Date: 2026-06-12 (TASK-0249, **Minor §12.3** — 제품 insight 완료율 대소문자 매칭; 주 변경은 feature-0003-agent-web-ui app.py, 본 항목은 db.py 단일 변경 교차 기록. 동시세션 `task0248-product-delete-blocked-conv` 가 TASK-0248 선점→§13.1 재번호 후 0249)
- Scope: agent-core — `information_schema.TABLES` 조회 시 DB명(TABLE_SCHEMA) 대소문자 무시 매칭.
- 진단: Linux MySQL `@@lower_case_table_names=0` 환경에서 DB명이 대소문자 구분이라, 등록명(소문자 `dbcommon`)이 실제 DB명(`dbCommon`)과 어긋나면 `WHERE TABLE_SCHEMA IN ('dbcommon')` 이 0행을 반환 → 제품 insight 완료율이 0/0 으로 잘못 표기됐다(TASK-0249 Bug B).
- 변경 (`src/modules/db.py`, `list_information_schema_tables` MySQL 분기):
  - `WHERE TABLE_SCHEMA IN ({placeholders})` → **`WHERE LOWER(TABLE_SCHEMA) IN ({placeholders})`**, 바인딩 파라미터 `wanted` → `[w.lower() for w in wanted]`.
  - 반환값은 실제 케이스 유지(SELECT 컬럼 무변경) → 호출측(app.py coverage)이 소문자로 grouping. 근거 주석에 TASK-0249 명시.
- 비변경: MSSQL 분기·결과 수집·풀·breaker(TASK-0247)·RBAC·스키마 0. 반환 row shape 불변이라 다른 호출처(insight-reset rag_objects 교집합 등) 무영향 — 매칭만 케이스-무관해지는 무해한 개선.
- 검증: make test 컨테이너 **전체 599 passed/2 skipped 회귀 0** + ruff clean + py_compile. (coverage 회귀 테스트는 web-ui `test_insight_coverage.py` C3 가 mixed-case 경로 커버.)
- Files: unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0002-agent-core/docs/MODIFY.md
- Rollback: `LOWER(TABLE_SCHEMA)` → `TABLE_SCHEMA`, 파라미터 소문자화 환원(단 0/0 버그 재발).

## CHG-20260612-0247
- Date: 2026-06-12 (TASK-0247, **Major §12.3** — 데이터플레인 연결 격리; 동시세션 `task0244-ds-picker-status` 가 TASK-0244 선점→§13.1 재번호 0244→0247 (동시세션이 0244·0245·0246 선점))
- Scope: agent-core — 한 datasource 의 연결 불안정이 단일 직렬 ask-worker 를 점유해 정상 datasource 제품 응답까지 지연시키던 직렬 starvation 을 연결별로 격리(bounded connect timeout + per-datasource circuit breaker).
- 변경:
  - `src/modules/config.py`: 신규 env — `AGENT_DB_CONNECT_TIMEOUT_SEC`(기본 10, 연결 수립 상한을 쿼리 예산과 분리), `AGENT_DB_BREAKER_ENABLED`(기본 1), `AGENT_DB_BREAKER_FAIL_THRESHOLD`(기본 3), `AGENT_DB_BREAKER_COOLDOWN_SEC`(기본 30). `__all__` 갱신.
  - `src/modules/db.py`: ① `_dataplane_connect_timeout()` — data-plane 연결 timeout(MySQL `connection_timeout`·MSSQL `login_timeout`)을 `AGENT_TIMEOUT_SEC`(쿼리 예산)에서 분리. MSSQL 쿼리 `timeout` 은 유지. ② per-datasource circuit breaker — `DatasourceCircuitOpen`, `_BREAKER_STATE`+`_BREAKER_LOCK`, `_breaker_key`(scope_key), `_is_connect_breaker_failure`(connect-stage 분류·deadlock/인증 제외), `_breaker_admit`(요청당 게이트 + 단일 half-open trial `half_open_at` 토큰 + stale 회수), `_breaker_record_success/failure`(요청당 1회), `_breaker_safe`(부기 예외 격리), `_breaker_trial_timeout`, `_reset_breaker_state`(테스트). ③ `connect_with_retry` 가 breaker 의 단일 경계 — admit(루프 전) + record(요청당 1회). `connect()` data-plane 분기는 bounded timeout 만 적용. ④ `_should_retry_db_error` 가 `DatasourceCircuitOpen` 을 비-재시도로 분류. `__all__` 에 `DatasourceCircuitOpen` 추가.
  - `tests/test_db_circuit_breaker.py`: 신규 22 테스트(8스레드 동시성 단일 trial 포함).
  - `.env.example`: 신규 4 env 문서화.
- 비변경: control-plane(memory DB, `datasource=None`) 연결 경로 — breaker 미적용, 동작 0 변경. 풀(TASK-0144)·replica 라우팅·probe_datasource·tools 라우터/allowlist·RBAC·스키마 무변경.
- 검증: 신규 22 PASS + make test 컨테이너 전체 회귀 0 + ruff clean + py_compile. outside-voice 2-pass 적대 리뷰(REV-20260612-0247) NOT-SHIP→SHIP-WITH-FIXES.

## CHG-20260612-0237
- Date: 2026-06-12 (TASK-0237, **Major §12.3** — OpenAI legacy 명명 정리; 동시세션 cycle 이 TASK-0231~0235 선점→§13.1 재번호 0233→0236)
- Scope: agent-core 측 — 실제 LLM 이 Bedrock Claude 전용이고 `openai` SDK 는 전송 규약 클라이언트로만 쓰이므로 GPT 시절 명명 잔재 정리(SDK 유지, 동작 무변경).
- 변경:
  - `src/modules/llm.py`: `_get_openai_client` → `_get_llm_client` rename + 내부 호출처 전부 변경 + `__all__` 갱신. 구이름 `_get_openai_client = _get_llm_client` deprecated alias 유지(kb_retrieval·app.py 외부 import + 앵커 불변식 테스트 호환).
  - `src/modules/config.py`: ① `OPENAI_MODEL` env 소스 `LLM_MODEL or OPENAI_MODEL or "claude-sonnet-4"`(새 이름 우선, 구이름 fallback — 심볼명 유지로 사용처 무변경). ② `AGENT_OPENAI_MAX_RETRIES` env 소스 `AGENT_LLM_MAX_RETRIES or AGENT_OPENAI_MAX_RETRIES or 0`. ③ dead env `OPENAI_API_BASE` 제거(정의 + `__all__`).
  - `src/agent_core.py`: 미사용 `OPENAI_API_BASE` import 제거.
  - `src/modules/kb_retrieval.py`: `_get_llm_client` 사용.
  - `src/modules/model_catalog.py`: `max_tokens_for_model` 의 "OpenAI direct legacy" 죽은 분기 주석 정정(`return None` 동작 보존 — 미등록 모델 fallback).
  - `tests/test_anchor_invariant_postgres.py`: LLM tripwire fn_name 튜플에 `_get_llm_client` 추가(신·구 둘 다).
- 비변경: `_resolve_tier_endpoint` 라우팅·Bedrock/Local 자격증명·max_tokens cap 값·"OpenAI Chat Completions spec" 주석(정확한 규약 서술). 동작 무변경.
- 검증: 신규 `tests/test_llm_env_naming.py` 6(LLM_MODEL 우선/OPENAI fallback/default/retries/OPENAI_API_BASE 제거) + 앵커 불변식 + agent-core 전체 회귀 0. py_compile + alias 정합(`_get_llm_client is _get_openai_client`).
- Files: src/modules/{llm,config,kb_retrieval,model_catalog}.py, src/agent_core.py, tests/{test_anchor_invariant_postgres,test_llm_env_naming}.py, docs/{MODIFY,REVIEW}.md
- Rollback: alias 유지로 호출처 무중단. env fallback 으로 운영 .env 무중단. 코드 환원 시 위 파일 revert.

## CHG-20260611-0232
- Date: 2026-06-11 (TASK-0232, **Major §12.3** — 외부 LLM 비용 영향: 제품 프롬프트 "자동 작성" 결과 중간 잘림 해소; 동시세션 insight-reset cycle 이 TASK-0231 선점→§13.1 재번호 0231→0232)
- Scope: agent-core 측 — `modules/model_catalog.py` 의 task 별 max_tokens cap 표에 긴 본문 전용 `"prompt_gen"` task 신설. feature-0003 의 `admin_generate_product_prompt`(제품 시스템 프롬프트 자동작성)가 이 cap 을 사용.
- 배경: 자동작성이 "완성된 시스템 프롬프트 본문"을 생성하면서 출력 상한을 짧은 요약용 `"summary"` cap(Claude 7000 / 로컬 512)으로 잡아 본문이 중간 잘림. 웹 기본 모델 `claude-haiku-4` 는 extended-thinking budget(≤5000)을 max_tokens 안에서 소비하므로 7000 cap 의 실본문 여유가 ~2000 토큰뿐.
- 변경:
  - `_CLAUDE_MAX_TOKENS["prompt_gen"] = 20000` (thinking 차감 후에도 ≥4000 본문 여유, 비용 폭주 차단 위해 명시 cap 유지 — CHG-0004 정합).
  - `_LOCAL_LLM_MAX_TOKENS["prompt_gen"] = 3072` (4K 컨텍스트 윈도 내 최대 출력, summary 512 대비 상향).
  - `max_tokens_for_model(model, task)` 라우팅 로직 무변경 — task 키만 추가(다른 task cap 영향 0).
- 검증: 신규 `tests/test_prompt_gen_max_tokens.py` 5 PASS(prompt_gen 양 tier 존재·summary 대비 단조성·Claude thinking 차감 여유≥4000·로컬 4K 한도·tier 라우팅) + 기존 `test_call_llm_records_agent_task.py` 회귀 0.
- Files: src/modules/model_catalog.py, tests/test_prompt_gen_max_tokens.py(신규), docs/{MODIFY}.md
- Rollback: prompt_gen 두 항목 삭제 시 자동작성이 default cap(Claude startswith 분기의 8192)으로 폴백 — 잘림 재발하나 동작 안전.

## CHG-20260611-0230
- Date: 2026-06-11 (TASK-0230, **Critical §12.3** — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조)
- Scope: agent-core 측 — 제품이 여러 datasource 에 바인딩될 때, 런타임이 tool 호출마다 datasource 를 선택해 그 datasource 의 (연결·스키마 allowlist·dialect) 격리 컨텍스트로 조회. 단일 바인딩(0~1)·flag OFF 는 기존 단일 경로 byte-identical(동작 0 변경).
- 배경: 기존 멀티 datasource(TASK-0185~0226)는 product↔datasource **1:1**(WebProducts.DatasourceKey 단일 컬럼). 사용자 요청 = 한 제품이 여러 datasource·DB 를 참조해 한 질문에서 교차 조회.
- Files:
  - unit/feature-0002-agent-core/src/agent_core.py (`_resolve_product_datasources`/`_product_datasource_keys`/`_datasource_allow_schemas`[fail-closed] + run-loop 라우터 등록·grounding·finally close_all/reset)
  - unit/feature-0002-agent-core/src/modules/tools.py (`_DatasourceRouter` + `execute_tool` datasource 라우팅 + `set/get/reset_active_ds_router` + `build_tool_definitions_for_datasources`)
  - unit/feature-0002-agent-core/src/modules/insight.py (`_discover_mssql_databases` datasource 차원 우선 + primary/join union 폴백)
  - unit/feature-0002-agent-core/tests/test_product_multi_datasource.py (신규 15 — 라우터 격리·lockstep·fail-closed·enum·단일경로 무변경)
- 보안: 격리 불변식 = 연결·allowlist·engine 을 단일 `label` 로 lockstep 활성화(불일치 창 없음) + tool 순차 실행 + 게이트는 항상 활성 datasource 의 것. `_datasource_allow_schemas` 차원 컬럼 부재 시 fail-closed([], 전체목록 broadcast 교차노출 차단). outside-voice REV-20260611-0230 BLOCKER 0, MAJOR-1/2/3 흡수.
- Rollback: flag `AGENT_MULTI_DATASOURCE_ENABLED=0` 또는 제품 바인딩을 1개로 축소 시 기존 단일 경로로 즉시 복귀(코드 환원 불요). 코드 환원 시 위 4파일 revert.

## CHG-20260611-0226
- Date: 2026-06-11 (TASK-0226, **Major §12.3** — MSSQL insight-worker per-DB 스캔 커버리지 + 권한 실패 가시화)
- Scope: insight-worker 가 MSSQL datasource 의 제품 접근가능 DB(`WebProductDatabases`) 마다 재연결 스캔할 때, RO 로그인 GRANT 누락으로 일부 DB 가 조용히 누락되던 것을 telemetry+status 로 가시화 + 멀티 DB RO 부트스트랩 템플릿 제공. MySQL 단일 datasource 무변경.
- 배경: `_discover_mssql_databases` 는 datasource 바인딩 제품들의 접근가능 DB union 을 올바르게 발견하나, 각 DB `connect_with_retry(database=db)` 재연결 시 RO 로그인이 단일 DB 에만 USER/GRANT 돼 있으면(`bin/datasource-mssql-ro-bootstrap.sql` 은 단일 `TARGET_DB`) 'Login failed'(18456)/'Cannot open database'(916) 로 막혀 per-DB `except` 가 조용히 skip → 등록 DB 일부만 인사이트 생성·운영자 미가시.
- 변경:
  - `src/modules/insight.py`: `run_insight_cycle` 의 `scan_report` 에 `db_targets`(MSSQL 발견 DB 수)/`db_failed`(연결·스캔 실패 수) 카운터 신규. MSSQL `_db_targets` 발견 직후 `db_targets += len`. per-DB `except` 에서 `_is_mssql_ds` 면 `db_failed += 1` + 권한거부 패턴(login failed/cannot open database/permission/denied/18456/916/229/297) 감지 시 진단 힌트(`datasource-mssql-ro-bootstrap.sql` DB별 실행 안내) 로깅. `db_failed>0` 면 status='degraded'(publish_failed 와 동일 정책). heartbeat KV `insight_worker_last_db_targets`/`insight_worker_last_db_failed` + payload 에 노출.
  - `bin/datasource-mssql-ro-bootstrap-multidb.sql`: 신규 — 한 공유 RO 로그인을 @target_dbs(제품 접근가능 DB) 전체에 커서 순회로 USER+db_datareader 멱등 부트스트랩. QUOTENAME 식별자 인젝션 차단, ONLINE+비-시스템 DB 만 대상, db_datawriter 제거 hardening, 0단계 서버 전역 prereq(xp_cmdshell/cross-db ownership/Ad Hoc) 검증. 기존 단일-DB 스키마 GRANT-only 템플릿과 상호 배타(보안 trade-off: DB 단위 db_datareader, 운영자 명시 승인).
  - `bin/datasource-mssql-ro-bootstrap.sql`: 멀티-DB 주의 주석 + multidb 변형 cross-ref 추가.
  - `tests/test_mssql_perdb_coverage.py`: 신규 8 테스트(발견 함수 union/default_db 폴백/빈목록/예외 graceful + status degrade 결정 로직 4).
- 비변경: 발견 로직(`_discover_mssql_databases` — 이미 제품 접근가능 DB 기준)·런타임 allowlist(tools.py `_freeform_sql_access_error` 3-part catalog 대조 — 이미 제품 접근가능 DB 전체 허용)·RBAC·시크릿·PG/MySQL 스키마.
- 검증: pytest 신규 8 + 회귀(three_tier/degraded_backoff/security_boundary/multi_datasource) 131 PASS, 회귀 0 + py_compile.
- Files: src/modules/insight.py, bin/datasource-mssql-ro-bootstrap-multidb.sql(신규), bin/datasource-mssql-ro-bootstrap.sql, tests/test_mssql_perdb_coverage.py(신규)
- Rollback: db_targets/db_failed 는 MSSQL engine 한정 누적(MySQL=0 → status 영향 없음). 멀티 DB 부트스트랩 SQL 은 운영자 수동 실행 템플릿이라 미실행 시 기존 동작 유지(단, 누락 DB 는 degraded 로 표시됨 — 이것이 본 cycle 의 의도된 가시화).

## CHG-20260611-0223
- Date: 2026-06-11 (TASK-0223, **Major §12.3** — MSSQL database-aware 3계층 insight [feature-0003 주관, agent-core 교차변경])
- Scope: MSSQL(database.schema.table 3계층) insight 파이프라인 — insight-worker 가 제품 등록 DB 별로 스캔하고 fact_key 에 database 를 포함, read-back/grounding 이 이를 정합 매칭. MySQL 2계층은 무변경(active_database 미설정 → 기존 동치).
- 배경: insight-worker 가 MSSQL 을 `dbo` 단일 DB 만 스캔 + fact_key 에 database 누락 → 제품 등록 DB(`dk_data_release` 등)와 매칭 불가. fact_key 가 `dbo.<table>` 2계층이라 여러 database 의 동일 테이블 구분 불가.
- 변경:
  - `src/modules/config.py`: `_ACTIVE_DATABASE` ContextVar + `set_active_database`/`get_active_database` + `ds_object_suffix(schema, table=None)` 신규(active database 있으면 `{db}.{schema}[.{table}]`, 없으면 `{schema}[.{table}]`). `set_active_datasource` 가 전환 시 active_database None 리셋. `__all__` 등재. **`ds_fact_key` 시그니처 불변**(3자 정합 보존).
  - `src/modules/insight.py`: datasource 순회 루프에 MSSQL multi-database inner-loop(`_discover_mssql_databases` — `WebProductDatabases` 제품 등록 DB 합집합 + default_db; DB별 `connect_with_retry(database=db)` 재연결 + `set_active_database`; 연결실패 격리). suffix 조립부 전수 `ds_object_suffix` 치환(table_insight/schema_insight/table_fp/schema_fp/table_insight_refresh_at/schema_insight_refresh_at). `_build_insight_object_maps` + read-back(PG/MySQL 경로 쿼리)을 `object_key` 키로 전환(`(schema,table)` 튜플 → cross-DB 충돌 livelock 제거).
  - `src/modules/utils.py`: `_infer_rag_object_from_fact` 3계층(`database.schema.table`) 파싱 — schema_name/table_name 은 schema/table 단위 유지(grounding 정합), object_key 에 database 접두(cross-DB 유일성). 2계층 입력은 기존과 동치.
  - `src/modules/schema.py`: bootstrap 2곳(`_record_schema_insight_from_search`/`_record_table_usage_insight`) `ds_object_suffix` 치환(스캐너와 키 정합).
  - `src/agent_core.py`: `_insight_object_group` 신규 — grounding `_load_schema_list` 의 grouping 을 테이블명 제외 prefix(MySQL=schema, MSSQL=database.schema)로 정규화해 table_insight↔schema_insight desc 매칭. `rfind` 사용(2계층은 `find` 와 동일).
  - `tests/test_mssql_three_tier_insight.py`: 신규 13 테스트(ds_object_suffix 2/3계층·시그니처 불변·datasource 전환 리셋·3계층 파싱·cross-DB object_key 유일·grouping 정합).
- 비변경: RBAC·시크릿·PG/MySQL 스키마(rag_objects.object_key 기존 컬럼 재사용)·`ds_fact_key`/`ds_fact_like`/`ds_strip_prefix` 시그니처 무변경.
- 검증: pytest 444 passed/2 skipped(회귀 0) + py_compile + 라이브(MSSQL 제품 60테이블 grounded·권한밖 DB 격리·ask-worker grounding database.schema grouping 정상).
- Files: src/modules/{config,insight,utils,schema}.py, src/agent_core.py, tests/test_mssql_three_tier_insight.py
- Rollback: ds_object_suffix 가 active_database 미설정 시 2계층(MySQL 동치)이라 MSSQL 미사용 환경 무영향. multi-DB 루프는 MSSQL engine 한정 분기(MySQL `[None]` 1회=종전).

## CHG-20260611-0208
- Date: 2026-06-11 (TASK-0208, **Minor §12.3** — 답변 후처리 미리보기 링크 정확도)
- Scope: `_collapse_large_tables` 의 표↔CSV 매칭(`_match_csv_for_table`) 컬럼수 폴백을 좁혀, LLM 이 손으로 쓴 비-결과 분석/요약 표에 "전체 N행 미리보기" 오링크가 붙지 않게 한다.
- 배경(재현·스크린샷): 답변에 SQL 분석용 쿼리 CSV(들)가 있고 본문엔 쿼리 결과가 아닌 "재정정된 이슈 우선순위" 분석표(5열)가 있을 때, 값 토큰 매칭(1순위)은 실패하지만 컬럼수 폴백(2순위)이 컬럼수만 우연히 같은 무관 CSV 를 붙였다. 클릭 시 frontend 값 가드([app.js](../../feature-0003-agent-web-ui/src/static/app.js) `loadCsvAsInlineTable`)가 preview↔CSV 토큰 불일치를 감지해 "결과 파일이 미리보기와 일치하지 않아 전체 데이터를 표시할 수 없습니다." 토스트로 거부 → 사용자에게 깨진 링크 노출.
- 변경 ([src/agent_core.py](../src/agent_core.py) `_match_csv_for_table`):
  - 1순위(값 토큰 overlap ≥1) 실패 후, `table_tokens` 가 **비어있지 않으면** 즉시 `None` 반환(폴백 미적용·링크 생략). 식별 토큰이 존재하는데 어느 CSV 와도 안 겹친다 = "이 표는 그 쿼리 결과가 아니다" 의 음성 증거.
  - 컬럼수 폴백은 식별 토큰이 **아예 없는** 측정값(%·소수)-전용 표(`not table_tokens`)에만 한정(TASK-0174 `test_collapse_shape_fallback_for_measure_only_table` 회귀 보존).
  - docstring 에 trade-off 명시: 진짜 결과표를 과격 재포맷해 overlap 0 으로 떨어지면 링크 recall 손실 — "없는 링크"(degraded)가 "깨진 링크"(클릭 422)보다 낫다는 판단.
- 비변경: `_distinctive_tokens`/`_collapse_large_tables` 본체·threshold(5)·`used[]` 마킹·CSV 시그니처 무변경. frontend 값 가드는 defense-in-depth 로 유지(과거 저장된 오링크 graceful 처리). web/app.js 무수정 → 새 응답만 교정, 역사 메시지의 기존 오링크는 frontend 가드가 계속 처리.
- 검증: `tests/test_collapse_table_csv_match.py` 2 추가(분석표 토큰有·overlap0→링크 생략 / 다중표 분석표가 진짜 결과표 CSV 슬롯 미소모). 수정 전 원본 코드에서 신규 테스트 FAIL(오링크 부착 확인)→수정 후 6/6 PASS. 인접 순수함수 33 테스트 회귀 0. outside-voice 적대 리뷰 REV-20260611-0208 SHIP-WITH-NITS(BLOCKER 0).
- Files: unit/feature-0002-agent-core/src/agent_core.py, unit/feature-0002-agent-core/tests/test_collapse_table_csv_match.py, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: `_match_csv_for_table` 의 `if table_tokens: return None` 가드 제거(컬럼수 폴백이 토큰 유무 무관 적용 — 오링크 재발).
- Cross-ref: TASK-0174(값 매칭+컬럼수 폴백 도입) / TASK-0155·0154(미리보기 링크 두 면) / feature-0003 app.js 값 가드(#118).

## CHG-20260610-0200
- Date: 2026-06-10 (TASK-0200, **Minor §12.3** — 도구 읽기경로 하드닝)
- Scope: REV-20260610-0196 이 지적한 MINOR 잔존 실행 — `convo_search` LIKE/ILIKE 메타문자 이스케이프. (#2 발췌 정렬은 feature-0003 CHG-20260610-0200.)
- 배경: `convo_search` 가 `like_pattern = f"%{pattern}%"` 로 사용자 질의를 LIKE 패턴에 직접 끼워 `%`/`_` 가 와일드카드로 처리 — "100%"/"table_name" 같은 질의가 과다매칭/오작동. `_collect_matched_excerpts` 는 `_escape_like_for_search`+`ESCAPE '!'` 로 이미 이스케이프했으나 convo_search 만 누락(parity gap).
- 변경 ([src/modules/file_ops.py](../src/modules/file_ops.py) `convo_search`):
  - `like_pattern` 구성 시 비어있지 않은 질의는 메타문자 이스케이프 — `pattern.replace("!","!!").replace("%","!%").replace("_","!_")`(escape char `!` 를 **먼저** 치환해 이중이스케이프 회피) + `like_escape = " ESCAPE '!'"`. 빈 질의는 `%`(전체 매칭)+`like_escape=""`.
  - PG 분기(content/summary/value ILIKE) + MySQL legacy 분기(Content/Summary/`Value` LIKE) 6 LIKE 절 모두 `f"… %s{like_escape}"`. like_pattern·like_escape 는 분기 전 1회 계산해 공유.
- 비변경: 도구 RBAC/등록·스키마·결과 shape·case-insensitive(ILIKE) 무변경. 파라미터화 유지(SQLi 표면 무관 — 와일드카드 의미 정정만).
- 검증: `tests/test_convo_search_pg_routing.py` 2 추가(`"100%_x!"`→param `%100!%!_x!!%`+ESCAPE / 빈 질의→`%`+ESCAPE 없음). make test exit=0. outside-voice [SKIPPED:minor-escaping-implements-REV-0196] (REV-20260610-0200).
- Files: unit/feature-0002-agent-core/src/modules/file_ops.py, unit/feature-0002-agent-core/tests/test_convo_search_pg_routing.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: like_pattern 을 `f"%{pattern}%"` 로 환원 + 6절의 `{like_escape}` 제거.

## CHG-20260610-0196
- Date: 2026-06-10 (TASK-0196, **Minor §12.3** — 에이전트 도구 읽기경로 라우팅)
- Scope: `convo_search`(LOCAL agent tool) AR-M5 cutover 라우팅 누락 복구. web 3건은 feature-0003 CHG-20260610-0196.
- 배경: cutover 로 `AgentMemoryMessages`/`AgentMemorySummary`/`AgentMemoryKv` MySQL 테이블 DROP. `modules/file_ops.py` 의 `convo_search` 는 PG 경로 전무(파일이 `_pg_connect`/`agent_runtime`/`AGENT_RUNTIME_READ_BACKEND` 미import)한 채 3개 삭제 테이블을 `try/finally`(except 없음)로 조회 → 에이전트가 "다른 대화 검색" 도구 호출 시 첫 `cur.execute(FROM AgentMemoryMessages)`에서 throw(도구 사망). 전 서비스 스윕으로 확정된 4건 중 유일한 agent-core 면.
- 변경 ([src/modules/file_ops.py](../src/modules/file_ops.py) `convo_search`):
  - `os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres"` 분기 추가 → `from .db import _pg_connect` 로 PG 연결, 3개 쿼리를 PG `agent_runtime.messages`/`agent_runtime.summary`/`agent_runtime.kv` 로 실행. `ILIKE`(MySQL utf8mb4_unicode_ci case-insensitive 패리티), PG `kv.key`/`kv.value`(비예약어) unquoted, `'message'`/`'summary'`/`'topic'` source 라벨·`_format_row`(conv_id,role,content,created_at,source) 컬럼순서 동일, `include_current=False` 시 `conversation_id != %s` 제외 동일.
  - legacy MySQL 경로는 else 로 보존(backtick `` `Key` ``/`` `Value` `` 등 원본 유지).
- 비변경: 도구 RBAC/등록(LOCAL_TOOLS)·스키마·결과 shape 무변경. error 전파 동작 유지(except 미추가 — 도구 호출 에러는 에이전트 루프가 처리).
- 검증: 신규 `tests/test_convo_search_pg_routing.py`(PG 라우팅 + MySQL conn 미사용 가드 + 3 소스 + current 제외). make test exit=0. outside-voice REV-20260610-0196 SHIP(MAJOR 0).
- Files: unit/feature-0002-agent-core/src/modules/file_ops.py, unit/feature-0002-agent-core/tests/test_convo_search_pg_routing.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 본 변경 revert — convo_search 가 다시 삭제된 MySQL 테이블 조회(도구 throw).
- Cross-ref: feature-0003 CHG-20260610-0196(web 3건) / TASK-0189(동일 class 선행).

## CHG-20260610-0178
- Date: 2026-06-10 (TASK-0178, **Major §12.3** — agent-core; TASK-0177 의 전달 메커니즘 수정)
- Scope: 단계 근거(work/reason)를 LLM 이 **tool 호출 인자**로 채우게 전환. content 동시 방출(0177)은 라이브에서 무력했음.
- 배경(라이브 확정): 0177 배포·global row 갱신 후 카나리아에서 **모든 step `reason_source=derived`**. core_messages 검사 결과 tool-call 턴 content 가 `{"tool_notes":[{"work":"","reason":""}]}`(파서 빈 결과) — **Bedrock gateway 가 tool_use 턴의 text content 를 strip**. outside-voice REV-20260610-0177 의 M2("코드는 맞는데 모델이 그 경로를 안 탄다", 이 repo 반복 실패모드) 실현.
- 변경:
  - [src/modules/tools.py](../src/modules/tools.py): 모든 도구 스키마(`TOOL_DEFINITIONS_FULL` 9개, 공유 core 4 포함)에 optional `reason`/`work` string 파라미터 주입(`_inject_step_narration_params`, properties **맨 앞**=think-first, required 에는 미추가). `reason` 설명에 "사용자 질문 맥락의 구체 근거(generic 금지)" 명시.
  - [src/agent_core.py](../src/agent_core.py): 루프에서 `tool_args.pop("work"/"reason")` 로 추출 — **실제 도구 실행/args 저장 전에 제거**(narration 은 실행 무관, 핸들러는 named-get 이라 무해하나 명시 pop). 우선순위 `arg → content tool_notes(타 provider) → derived(0175)`. SYSTEM_PROMPT STEP NARRATION 을 "content 에 JSON 방출" → "tool 인자 reason/work 를 채워라"로 교체.
- 안정성: tool 호출 인자(arguments)는 SQL 처럼 게이트웨이 무관하게 전달되므로 reason 이 안정 도달. 핸들러는 `args.get(특정키)` 라 추가 인자 무해(테스트 단언).
- 비변경: 쿼리 실행/결과/RBAC/스키마/엔드포인트/회계 무변경. B1 sanitizer(0177)·derived fallback(0175) 유지(층상 안전망). reason 은 표시 메타데이터.
- 게이트: make test(컨테이너) **282 passed / 2 skipped**(신규 `test_step_narration_params.py` 4 + `test_tool_notes_prompt.py` 프롬프트 테스트 갱신, 회귀 0). py_compile OK.
- **라이브 카나리아 PASS(머지 전 probe, REV-20260610-0178)**: worktree 코드 배포 + global row 0178 프롬프트 갱신 후 2 ask(다단계) → **5 step 전부 `reason_source='llm'`·`work_source='llm'`**, 근거가 질문 맥락 직결("ResRace 컬럼을 포함한 아이템 마스터 테이블을 찾기 위해…", "캐릭터 정보가 담긴 dbgame.hero 테이블의 전체 행 수를 조회합니다") + 최종답변 JSON 누수 0 + 답변 정확. M2 게이트 충족.
- 라이브 반영: GLOBAL `WebSystemPrompts` row 를 0178 프롬프트로 갱신(probe 시 이미 적용). 머지 후 재배포는 동일 코드.

## CHG-20260610-0177
- Date: 2026-06-10 (TASK-0177, **Major §12.3** — agent-core, base SYSTEM_PROMPT 변경)
- Scope: 실행 단계 근거를 **LLM 이 실제 맥락에 맞게 생성**하도록 SYSTEM_PROMPT 에 tool_notes 방출 지시 추가(TASK-0175 derived fallback 은 안전망으로 유지). 사용자 원의도("템플릿 근거가 아니라 실제 맥락 근거").
- 배경: TASK-0175 가 reason 빈값을 derived(tool명 템플릿)로 메웠으나, 사용자는 **LLM 이 질문 맥락에 맞춘 근거**를 원함. 근본 공백(SYSTEM_PROMPT 가 tool_notes 미지시)을 메움.
- 변경 ([src/agent_core.py](../src/agent_core.py)):
  - `SYSTEM_PROMPT` 에 `## STEP NARRATION — EXPLAIN EACH TOOL CALL (tool_notes)` 섹션 추가 — tool 호출 턴마다 content 에 `{"tool_notes":[{work,reason}]}` 방출(tool call 당 1 entry, 동순서), 한국어, reason 은 **사용자 목표에 비춘 구체 근거**(generic tool 설명 금지). 유효 JSON·따옴표 escape 권고. tool call 없는 턴(최종답변/반문)엔 JSON 금지. `## OUTPUT` 에 "최종 답변엔 tool_notes/JSON envelope 금지" 1문장 보강.
  - **B1 sanitizer** `_strip_leaked_tool_notes(answer)` 신규 + 최종답변 경로(`raw_answer` 직후) 배선 — 누수된 tool_notes JSON envelope 를 결정적 제거(산문만 남김, 통째 envelope 면 빈문자열→기존 빈답변 재요청 루프). 프롬프트 문구는 통계적 억제일 뿐이라 백엔드 fail-closed 가드 추가(outside-voice REV-20260610 BLOCKER 1).
- 파서/호출부 무변경: 기존 `_parse_tool_notes`(content 에서 tool_notes 추출, 산문 속 임베디드 JSON·펜스 raw_decode) + 호출부 `reason_source='llm' if reason_text else 'derived'(fallback)` 그대로 동작. 이제 LLM 이 tool_notes 를 채우면 work/reason 둘 다 `llm` source.
- 비변경: 쿼리 실행/결과/RBAC/스키마/엔드포인트/회계 무변경. provider reasoning_content 직접 노출 금지(REQ-20260527-0120) 유효 — tool_notes 는 별도 공개용 trace.
- 라이브 반영: GLOBAL `WebSystemPrompts` row 가 코드 상수를 대체하므로(compose_system_prompt), **배포 후 global row 를 새 상수로 1회 갱신**(idempotent seed 는 기존 row 미덮어씀). 기존 라이브 row == 직전 코드 상수(검증), operator 편집 없음.
- 게이트: make test(컨테이너) **278 passed / 2 skipped**(신규 `test_tool_notes_prompt.py` 9 — 프롬프트 지시·파서 라운드트립·sanitizer, 회귀 0). py_compile OK. outside-voice 적대적 리뷰 NEEDS-TWEAK→FIXED, BLOCKER 1(B1 sanitizer) 흡수 + MAJOR 3(M1 순서·M2 효과검증·M3 over-call) 반영/카나리아 위임 (REV-20260610-0177).
- **카나리아 필수(M2)**: 라이브 ask 후 `reason_source='llm'` 비율 실측(모델이 content 에 tool_notes 실재 방출하는지 — Bedrock 정규화로 no-op 될 위험) + 최종답변 JSON 누수 0 확인.

## CHG-20260609-0175
- Date: 2026-06-09 (TASK-0175, **Minor §12.3** — agent-core)
- Scope: 실행 단계 `reason`(왜) derived fallback 추가 — 표시 메타데이터만.
- 문제: 사용자가 "각 단계 근거가 화면에 안 보인다" 재보고. 라이브 진단(PG `agent_runtime.steps`)에서 **모든 최근 step 이 `work_source='derived'`, `reason_text=''`**. 근본: ① base SYSTEM_PROMPT 가 LLM 에게 `tool_notes`(work/reason JSON) 방출을 **지시하지 않음**(TASK-0061 파싱 인프라는 있으나 TASK-0151 프롬프트 개편에 지시 미포함) → LLM 이 tool_notes 미생성 → `_parse_tool_notes` 빈 결과. ② work 는 `_derive_step_work` fallback 으로 복구되나 **reason 은 derived fallback 부재** → 항상 빈 값. (CHG-0173 프런트는 `step.reason` 이 비면 미표시 → 표시할 데이터 자체가 없었음.)
- 변경 ([src/agent_core.py](../src/agent_core.py)):
  - `_derive_step_reason(tool_name, args)` 신규 — `_derive_step_work`(무엇을)의 대칭(왜). tool 목적별 결정적 근거 문자열(list_schemas/describe_schema/describe_table/search_tables/get_sample_rows/get_table_indexes/get_foreign_keys/explain_query/execute_sql[집계/조회 분기]). 미지원 tool 은 `""`(무의미 근거 노출 방지 — 프런트가 빈 reason 미표시).
  - 호출부(루프): work 파생 직후 `if not reason_text: reason_text = _derive_step_reason(...); reason_source = "derived" if reason_text else ""`. **LLM 참값(tool_notes.reason)이 있으면 덮어쓰지 않음**(work 와 동일 가드).
- 비변경: 쿼리 실행·결과·RBAC·스키마·엔드포인트·프롬프트 무변경. reason_text 는 step 표시 메타데이터일 뿐 agent 동작/answer 에 무영향. 회계(`_record_llm_usage`)·tool 분기 등 다른 경로 무관.
- 게이트: make test(컨테이너) **269 passed / 2 skipped**(신규 `test_derive_step_reason.py` 4, 회귀 0). py_compile OK. outside-voice [SKIPPED:display-metadata-no-rbac-no-schema-no-behavior-change] (REV-20260609-0175).
- 후속(이월): LLM 생성 근거(richer)는 SYSTEM_PROMPT 에 tool_notes 지시 추가 + 라이브 `WebSystemPrompts` global row 갱신 + 카나리아 필요(별 cycle — 프롬프트 변경 리스크, TASK-0151 패턴). 본 cycle 은 결정적 derived 로 즉시·전건 가시화.

## CHG-20260609-0172
- Date: 2026-06-09 (TASK-0172, **Major §12.3** — agent-core)
- Scope: 무거운 쿼리 자가규제 — EXPLAIN 사전 게이팅 + per-query 시간 cap. (라이브 인시던트 "분기 대화 처리중 단계 안 진행" = 5~6분 대용량 집계 쿼리 근본 대응. self-interrupt(mid-query KILL)는 outside-voice RECONSIDER 로 보류 — DESIGN-self-interrupt.md §10 참조.)
- 변경:
  - `modules/tools.py`: `_estimate_explain_rows`(EXPLAIN 으로 테이블별 `rows × filtered/100` 곱 = 예상 카디널리티 추정, fail-open) + `_apply_query_cap`(`SET SESSION max_execution_time`, SELECT 한정 session-scoped backstop) 신규. `_tool_execute_sql` 에 게이트 분기: `AGENT_QUERY_GUARD_MODE=gate` 시 추정 rows > 임계 + `confirm_heavy` 미설정이면 실행 대신 좁히기 유도, `warn` 시 비용 경고 prepend 후 실행, `off`(기본) 무변경. execute_sql tool 스키마에 `confirm_heavy: bool` 추가(LLM override — "무거운 쿼리는 감수").
  - `modules/config.py`: `AGENT_QUERY_GUARD_MODE`(off|warn|gate, 미지원값→off 정규화) + `AGENT_QUERY_EXPLAIN_ROWS_WARN`(기본 1,000,000) + `AGENT_QUERY_MAX_EXECUTION_MS`(기본 0=비활성, generous backstop).
- outside-voice 적대적 리뷰 2회: 설계 RECONSIDER(self-interrupt→사전게이팅 전환) + diff FIX-BEFORE-ENABLING-GATE(M1 confirm_heavy 문자열 truthy 우회 / M2 cap session-scoped 정정 / m3 filtered 반영 / m4 mode clamp 흡수). REV-20260609-0172.
- 게이트: make test 회귀 0(신규 `test_query_guard.py` 15) + ruff + py_compile. **flag 기본 off 라 배포 자체 동작 무변경** — canary 는 off→warn→gate env 전환.
- 미해결(이월): 정상 5~6분 쿼리의 UX(frozen step)·collateral 포화는 replica 라우팅(인프라) 영역 — 본 cycle 범위 밖.

## CHG-20260609-0168
- Date: 2026-06-09 (TASK-0169)
- Scope: out-of-process ask-worker 실행모델 — agent-core 측(feature-0002). 짝: feature-0003 CHG-20260609-0168.
- 신규 파일:
  - `alembic/versions/20260609_0003_ask_jobs.py`: `agent_runtime.ask_jobs` 큐 테이블(status/claim/lease_epoch/heartbeat/attempts/payload/result_json + 인덱스 4). FK 없음(큐 decoupled).
  - `src/modules/ask_jobs.py`: 큐 헬퍼 — `claim_ask_job`(단일문 FOR UPDATE SKIP LOCKED, B2), `enqueue_ask_job`(단일문 slot enforce, M5), `heartbeat_ask_job`/`finish_ask_job`/`set_job_run_id`(lease 가드, B3), `sweep_stale_jobs`(requeue<cap / error≥cap), `cancel_pending_jobs`(2g), `has_active_job_for_conversation`/`active_inline_paths`(B1/M6), `reclaim_worker_jobs_on_boot`, 멱등 `_ensure_ask_jobs`.
  - `src/modules/ask.py`: `run_ask_worker_loop` — atomic claim → `run_agent` → terminal(result_json)·KV. 시간기반 heartbeat 스레드(lease 박탈 시 KV cancel 마킹 → agent 루프 무수정 fencing). stale sweeper·고아 inline reaper(활성 job 제외)·boot self-reclaim·SIGTERM graceful.
  - `src/scripts/healthcheck_ask_worker.py`: KV `ask_worker_last_cycle_at` 신선도 healthcheck(insight 클론).
- 변경:
  - `src/agent_core.py`: `run_agent`/`_run_agent_core` 에 optional `run_id` 추가(worker 가 claim 별 run_id 주입). `main()` `--ask-worker` dispatch → `run_ask_worker_loop`.
  - `src/modules/config.py`: `AGENT_ASK_EXECUTION_MODE`(기본 inprocess) + `AGENT_ASK_WORKER_*`. stale 기본값을 run_timeout(max(AGENT_TIMEOUT_SEC*3, EARLY_FINALIZE/1000)) + 180 로 **동적 산출**(make test 가 AGENT_TIMEOUT_SEC=300 환경에서 정적 300 의 false-positive requeue 위험을 잡아 수정).
  - `src/modules/memory.py`: `set_run_status` run_id→status 순서(M4). `_clear_cancel_request` run_id-scoped(MJ-2).
- 게이트: make test 회귀 0(244 pass) + py_compile + ruff clean. outside-voice 적대적 리뷰 흡수(REV-20260609-0168).

## CHG-20260609-0163
- Date: 2026-06-09
- TASK-Cycle: TASK-0163, **Major §12.3** — LLM 사용량 회계 복구 (메인 추론 계측 + resolved_model + 계정별/역할별)
- Summary: 관리 콘솔 > 감사 > LLM 사용량이 `edge`·`시스템`만 보이던 근본 원인을 라이브 진단으로 규명·수정. PG `agent_runtime.llm_usage` 19,602행이 전부 insight worker(`__insight_worker__`, owner 없음) 의 별칭 `edge` 였고, **사용자 대화 메인 추론은 0건 기록**. (RC1) 메인 agentic loop 호출 `_call_llm` 이 `client.chat.completions.create()` 의 message 만 반환하고 `response.usage` 를 버려 `_record_llm_usage` chokepoint 를 우회 → 계측. (RC2) 요청 별칭만 기록하고 실제 서빙 모델(`resp.model`) 미기록 → `resolved_model` 컬럼 도입. RC3(엔드포인트/프론트)는 feature-0003. **outside-voice B1 흡수**: `/api/ask` 는 in-process(`asyncio.to_thread`) 실행이라 cfg 전역(conv/run)이 동시 ask 간 race → 메인 추론은 명시 인자로 race-free 귀속.
- Files:
  - `unit/feature-0002-agent-core/src/modules/llm.py`: `_record_llm_usage` 에 `conversation_id`/`run_id` optional 인자 추가(미전달=cfg 전역 fallback) + `resolved_model`(=`getattr(resp,"model")`) 컬럼 INSERT.
  - `unit/feature-0002-agent-core/src/agent_core.py`: import 에 `_record_llm_usage` 추가; `_call_llm` 에 `conversation_id`/`run_id` 인자 추가 + 응답 직후 `_record_llm_usage(model,"agent",response,conversation_id,run_id)` 호출(self-guard 위 try/except); 메인 loop 호출부가 `cid`/`run_id` 전달. (초안의 `cfg.MEMORY_CONVERSATION_ID=cid` 직접 set 은 race window 확대로 제거.)
  - `unit/feature-0002-agent-core/alembic/versions/20260608_0002_llm_usage_resolved_model.py`: 신규 — `ADD COLUMN IF NOT EXISTS resolved_model varchar(128)` (down_revision 0001_baseline, 멱등 offline SQL).
  - `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql`: 부트스트랩 parity — llm_usage 정의에 `resolved_model VARCHAR(128)` 추가.
  - `unit/feature-0002-agent-core/tests/test_llm_usage_record.py` + `test_call_llm_records_agent_task.py`: 신규 9 test.
- Note(배포 순서, S1): `_record_llm_usage` 의 best-effort except 가 "컬럼 없음" 을 삼키므로 **make migrate(컬럼 추가)를 web/insight-worker 재배포보다 먼저** 적용해야 RC1 이 silent 0행이 되지 않음.
- Review: REV-20260609-0163 [SUBAGENT 적대적 diff 리뷰] NEEDS-TWEAK→PASS, BLOCKER 1 흡수.

## CHG-20260608-0160
- Date: 2026-06-08
- TASK-Cycle: TASK-0160, **Major §12.3** — 중단 run 의 고아 tool_use → LLM payload 400 방지
- Summary: 웹 DBA 챗 재질의 시 `BedrockException ... tool_use ids ... without tool_result` 400 으로 대화가 영구 막히던 결함 수정. `/api/ask` 의 in-process(`asyncio.to_thread`) 실행([[TASK-0159]])이 web 재배포로 `execute_sql` 도중 죽으면 assistant 의 tool_use 만 저장되고 tool_result 전에 종료 → 재생성 시 고아 tool_use 가 LLM payload 에 실려 Anthropic/Bedrock 거부. `_normalize_history_rows` 의 미완성 페어링 가드(assistant 를 먼저 append 후 회수 못함)를 버퍼링 방식으로 재작성.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py`: `_normalize_history_rows` 재작성 — assistant(tool_calls) 턴을 버퍼(`pending_assistant`/`pending_tool_ids`/`pending_tool_rows`)링하고, 턴 종료 시 `_flush()` 가 모든 tool_use id 해소 시에만 commit·미해소면 턴 전체 drop. 매칭 없는 고아 tool 행 drop 유지. 윈도우 경계 절단 고아도 무해화.
  - `unit/feature-0002-agent-core/tests/test_history_tooluse_sanitize.py`: 신규 6 case.
- Note(즉시 해소, 코드 외): 라이브 PG `agent_runtime.core_messages` 의 대화 `20260608025216-3014b095` 고아 msg 1147(orphan tool_use) + 1184(에러 버블) 삭제. 전수 점검 결과 해당 대화 잔존 고아 0. (배포 후엔 query-time 정합화로 모든 대화의 동류 고아가 자동 무해화되어 별도 DB 정리 불요.)

## CHG-20260605-0151
- Date: 2026-06-05
- TASK-Cycle: TASK-0151, **Major §12.3** — DB 조회 사용자 경험 개선 (환각·반복질문·첨부무시·사고미확장 해소)
- Summary: 사용자 보고 6건의 root cause 를 라이브로 규명·수정. (1) 05-27 cutover 로 DROP 된 MySQL 을 조회하던 스키마 grounding 을 PG 정본으로 전환해 "KNOWN SCHEMAS" 섹션을 복구(환각 차단). (2) base SYSTEM_PROMPT 을 "answer-not-explore" 철학에서 "grounding 없으면 발견·검증, 추측 금지, 0-rows 환각 가드, 첨부 리뷰 우선, 애매하면 가정명시 후 되묻기"로 전면 개편. (3) 멀티턴 윈도우에서 초기 user 의도가 tool 결과에 밀려 탈락하던 것을 user 메시지 보존으로 완화 + 인사/메타가 origin 으로 고정되는 버그 차단. (4) 첨부 text cap 초과 시 최신 파일이 무음 누락되던 정렬 버그 수정 + 리뷰 우선순위 INSTRUCTION 강화.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py`: `_extract_schema_desc`/`_global_insight_rows_pg`/`_kb_read_is_pg` 신규; `_load_schema_list`·`_load_relevant_table_insights` PG 정본 분기(+MySQL fallback 보존); base `SYSTEM_PROMPT` 전면 개편; `_build_knowledge_context` 헤더 과신 문구 완화; `_format_core_messages` 추출 + `_assemble_core_messages` user-turn 보존(`_USER_TURN_KEEP=8`); `_build_attachment_context_section` text INSTRUCTION 리뷰 우선순위 명시; run_agent origin 설정에 저정보 가드.
  - `unit/feature-0002-agent-core/src/modules/domain.py`: `_is_low_information_request` 신규 + `_should_refresh_origin_request` 의 "빈 origin=무조건 shift"를 "저정보면 보류(continue)"로 보정.
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_prepare_text_inline_attachments` 의 `ORDER BY Id ASC`→`DESC`(+표시 reverse) — count cap 초과 시 최신 첨부 보존.
  - `unit/feature-0002-agent-core/tests/test_db_query_ux.py`: 신규 회귀 테스트 12건.
- 라이브 운영 변경(코드 외): `WebSystemPrompts` scope=global Content 를 새 SYSTEM_PROMPT 으로 갱신(백업 보관) — 기존 row 가 있으면 startup seed 가 덮어쓰지 않으므로 배포 시 1회 수동 갱신 필요.

## CHG-20260604-0147
- Date: 2026-06-04
- TASK-Cycle: TASK-0147, **Major §12.3** — insight worker degraded read-back backoff (livelock 재발 방지)
- Summary: TASK-0145/0146 이 read-back 2경로를 PG 로 고친 뒤에도, PG 가 다운되면 두 경로가 빈 MySQL fallback 으로 떨어져 livelock 이 재발할 수 있는 잔여 위험을 차단. read backend 가 postgres 인데 PG 가 닿지 않으면 cycle 이 생성을 skip 하고 loop 가 짧은 tick(8s) 대신 긴 backoff(기본 300s)로 PG 복구를 기다린다.
- Files:
  - `unit/feature-0002-agent-core/src/modules/insight.py`: `_insight_readback_degraded()` 신규(postgres 모드 + `_pg_available()`/`_pg_connect_ro()+SELECT 1` probe) + `run_insight_cycle` 에 degraded 시 scan skip + status=`degraded_readback` + `run_insight_worker_loop` 이 status 기반 backoff(`degraded_readback`/`error`→degraded_backoff_sec, else tick_sec).
  - `unit/feature-0002-agent-core/src/modules/config.py`: `AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC`(기본 300) 추가 + `__all__`.
  - `unit/feature-0002-agent-core/tests/test_insight_degraded_backoff.py`: 신규 4건(mysql 모드 False / pg 미가용 True / probe 실패 True / probe 정상 False).
- 검증: ruff PASS + pytest 177 passed/2 skipped + 라이브 functional(PG up→False, 미가용→True).
- Backend/DB schema/RBAC/endpoint/secret: 무변경(read 경로 방어 가드 + loop 타이밍 only).

## CHG-20260604-0145b
- Date: 2026-06-04
- TASK-Cycle: TASK-0145 (후속 — 동일 livelock 의 두 번째 read-back 불일치), **Major §12.3**
- Summary: CHG-0145 의 artifact-verify PG read-back 수정 후 라이브 관찰에서, insight 재생성 reason 이 `artifact_missing`(해소됨)에서 `fingerprint_changed`로 전환되며 **재생성·ollama CPU 점유가 지속**됨을 발견. 원인은 동일 cutover 잔재의 두 번째 면: fingerprint/refresh_at 맵을 읽는 `_load_kv_prefix_map` 이 (DROP 된) MySQL `AgentMemoryKv` 를 조회 → 항상 빈 맵 → 저장 fingerprint 없음 → 매 사이클 `fingerprint_changed` 오탐. fingerprint 정본은 PG `agent_runtime.kv`(table_fp 765·schema_fp 15·refresh_at 780). `load_memory_kv` 와 동형으로 PG 분기 추가해 해소.
- Files:
  - `unit/feature-0002-agent-core/src/modules/kb_scope.py`: `_load_kv_prefix_map` 에 `AGENT_RUNTIME_READ_BACKEND=postgres` 분기 추가 — `runtime_backend._read_runtime_pg("load_kv_all", …)` 로 PG `agent_runtime.kv` 읽고 prefix 필터(미가용 시 MySQL fallback).
- 검증: ruff PASS + pytest 173 passed/2 skipped + 라이브 functional(`_load_kv_prefix_map("__global__","table_fp:")` → 765 entries) + 재배포 후 generate_insight 수렴·ollama CPU 급감(라이브).

## CHG-20260604-0145
- Date: 2026-06-04
- TASK-Cycle: TASK-0145, **Major §12.3** — insight worker livelock 근본 수정 + 운영 하드닝
- Summary: insight worker 의 영속 검증 read-back 이 05-27 cutover 로 DROP 된 MySQL `AgentMemory*` 테이블을 조회(예외 silent swallow)해 매 8s 동일 객체를 무한 재생성하던 livelock 을, 쓰기 정본인 Postgres 에서 read-back 하도록 라우팅해 해소. 부수로 docker 로그 로테이션·리소스 제한·앱 로그 위생(회전+retention)을 추가해 장기 실행 시 WSL2 vmmem/디스크 무한 팽창을 상한.
- Files:
  - `unit/feature-0002-agent-core/src/modules/insight.py`: `_load_insight_artifact_states_pg()` 신규(PG `public.fact_entries`/`rag_documents`/`rag_objects` + `texts` join, `_pg_connect_ro()`) + `_load_insight_artifact_states` 가 `AGENT_KB_READ_BACKEND=postgres` 시 PG 분기(미가용 시 MySQL fallback) + row-처리 공유 헬퍼 5종(`_apply_insight_fact_rows`/`_apply_insight_doc_rows`/`_apply_insight_schema_object_rows`/`_apply_insight_table_object_rows`/`_build_insight_object_maps`) 추출 + `_warn_insight_readback_failed`(삼켜지던 예외 1회 surface).
  - `unit/feature-0002-agent-core/src/modules/kb_scope.py`: `_scope_filter_sql_pg` 신규(snake_case `scope_key` — `_scope_filter_sql` 의 PG 방언) + `__all__` 등재.
  - `unit/feature-0002-agent-core/src/modules/config.py`: `AGENT_LOG_MAX_BYTES`(기본 50MB) 추가 + `__all__` 등재.
  - `unit/feature-0002-agent-core/src/modules/utils.py`: `_rotate_log_if_oversized()` + `append_log_line` 가 회전 호출(단일 앱 로그 파일 상한).
  - `docker-compose.yml`: `x-logging` 앵커(json-file max-size 20m/max-file 5) — 15개 서비스 전부 적용 + 서비스별 `mem_limit`/`pids_limit`(현재 사용량 대비 넉넉한 상한, WSL2 vmmem 억제 겸용; web/insight/agent 는 `x-agent-common` 앵커로 상속).
  - `bin/gc.sh`: 로그 day-dir(`logs/<YYYY-MM-DD>`) retention 단계 추가(`GC_LOG_RETENTION_DAYS`, 기본 14d).
- 검증: py_compile + ruff(All checks passed) + pytest 173 passed/2 skipped + 라이브 functional(재생성 반복 3키 `complete=True`) + 라이브 SQL(4파트 PG 실재).
- Backend/DB schema/RBAC/endpoint/secret: 무변경(읽기 경로 backend 라우팅 + infra limits only).

## CHG-20260528-T1T5
- Date: 2026-05-28
- TASK-Cycle: TASK-0123, **Major §12.3** — Postgres KB 성능 최적화 T1~T5 + PgBouncer/Replica 전체 활성화
- Summary: T1~T5 Postgres 성능 최적화 로드맵 전체 구현 및 활성화. DISTINCT ON/ANY N+1 제거 + MATERIALIZED VIEW + JSONB GIN + pg_stat_statements + PgBouncer scram-sha-256 + kb_invalidations + streaming replica. pgbouncer AUTH_TYPE md5→scram-sha-256 수정 (pg_hba.conf IP 우회 규칙 제거), GIN 인덱스 순서 버그 수정, memory.py MV 감지 버그 수정.
- Files:
  - `unit/feature-0002-agent-core/src/modules/knowledge.py`: `_load_top_facts_pg()` 신규 + `_build_knowledge_payload()` PG fast path + advisory lock PG 분기.
  - `unit/feature-0002-agent-core/src/modules/db.py`: `_pg_connect_ro()` replica 라우팅 + `_pg_mark_kb_invalidation()` + `_pg_check_kb_invalidation()`.
  - `unit/feature-0002-agent-core/src/modules/config.py`: `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 추가.
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py`: `_mirror()` fact write 후 kb_invalidations 호출.
  - `unit/feature-0002-agent-core/src/modules/memory.py`: `_ensure_pg_schema()` pg_matviews UNION 추가.
  - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql`: MV + JSONB + GIN + autovacuum + kb_invalidations + kb_slow_queries + partial ivfflat + pg_stat_statements. GIN 인덱스 DO block 이후 배치 수정.
  - `docker-compose.yml`: pgbouncer (AUTH_TYPE=scram-sha-256) + PostgreSQL command 파라미터 + postgres-replica (max_connections=100) + postgres-replica-init (entrypoint list 형식).
  - `.env`: `AGENT_KB_PG_HOST=pgbouncer` + RO 환경변수 블록 추가.
  - `docs/ARCHITECTURE.md`: §7 KB Postgres 성능 최적화 레이어 신규.
  - `wiki/Architecture/Data-Flow.md`: pgbouncer + replica mermaid 다이어그램 갱신.
  - `wiki/concepts/kb-postgres-pgvector.md`: T1~T5 최적화 전면 갱신.
  - `wiki/hot.md` / `wiki/Log.md`: 세션 컨텍스트 갱신.

## CHG-20260527-0120
- Date: 2026-05-27
- TASK-Cycle: TASK-0120, **Minor §12.3** — reasoning fallback 노출 차단
- Summary: `agent_core.py` 가 최종 답변 `content` 공백 시 `reasoning` / `reasoning_content` 를 사용자 답변으로 fallback 하던 경로를 제거했다. 내부 추론은 공개하지 않고, 공개 가능한 한국어 Markdown 답변 재요청으로 전환한다.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py`: reasoning fallback 제거 + empty content 재요청 경로 보강.
  - `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: REQ/TASK/CHG/REV/REPORT 기록.

## CHG-20260527-AR-M5
- Date: 2026-05-27
- TASK-Cycle: TASK-0119, **Major §12.3** — MySQL agent_runtime 6 테이블 cleanup (outside-voice 필수)
- Summary: Phase 2 AR-M5 MySQL cleanup. `bin/runtime-cleanup-mysql.sh` 신규 — 4 gate (AGENT_RUNTIME_READ_BACKEND=postgres + dual-write 종료 sentinel + 14-day window + TTY double-confirm) + mysqldump backup (gzip+sha256+integrity) + 6 테이블 DROP FK 역순. ADR-0028 신규 (Stage A/B/C 3단계 정책). test_runtime_m5_cleanup.py 16 test.
- Worktree: `ai/claude/agent-runtime/m5` (base = main HEAD a213d9f (AR-M4 merge)).
- Files:
  - `bin/runtime-cleanup-mysql.sh` (신규): --dry-run/--backup-only/--confirm 3 mode + 4 precondition gate + mysqldump+gzip backup + 6 테이블 DROP FK 역순 + 검증 Stage 5.
  - `unit/feature-0002-agent-core/tests/test_runtime_m5_cleanup.py` (신규, 16 tests): script 존재/syntax/dry-run 출력/DROP 순서/confirm 거부/mode 중복/4 gate 검증/ADR-0028 문서화.
  - `docs/DECISIONS.md` (수정): ADR-0028 신규 (Stage A/B/C 정책 + DROP 순서 + confirm string + 대안 폐기).

## CHG-20260527-AR-M4
- Date: 2026-05-27
- TASK-Cycle: TASK-0118, **Major §12.3** — cutover read path (outside-voice 필수)
- Summary: Phase 2 AR-M4 PG read path 전환. `AGENT_RUNTIME_READ_BACKEND` env + `_read_runtime_pg` dispatcher + `PgRuntimeBackend` 9 read method + memory.py 7 분기 + agent_core.py 3 분기 + 23 test + cutover readiness script + ADR-0027 addendum. web UI app.py 는 cross-DB JOIN 의존으로 별도 cycle.
- Worktree: `ai/claude/agent-runtime/m4` (base = main HEAD 335a5b8 (AR-M3 merge)).
- Files:
  - `unit/feature-0002-agent-core/src/modules/runtime_backend.py` (수정): `AGENT_RUNTIME_READ_BACKEND` env var + `_PG_GET_CONV_MESSAGES_FULL` SQL 상수 추가 + `PgRuntimeBackend` 9 read method 추가 (load_kv/all/by_key_value/summary/messages/steps/core_messages/list_conversations/get_conv_messages_full) + `_get_pg_runtime_conn_ro()` + `_read_runtime_pg(method_name, **kwargs)` dispatcher.
  - `unit/feature-0002-agent-core/src/modules/memory.py` (수정): 7 read 함수 PG 분기 + `_assemble_steps()` helper 추출.
  - `unit/feature-0002-agent-core/src/agent_core.py` (수정): `_assemble_core_messages()` helper 추출 + `_load_conversation_messages` / `list_all_conversations` / `get_conversation_messages` PG 분기.
  - `unit/feature-0002-agent-core/tests/test_runtime_read_backend.py` (신규, 23 tests): _read_runtime_pg routing 5건 / PgRuntimeBackend 9 method SQL 검증 / memory.py 4건 / agent_core.py 4건.
  - `bin/runtime-cutover-readiness.sh` (신규): 7 gate cutover readiness check (dual-write 활성/row count/ANCHOR/unit test/PG read test/env 정합/backfill state).
  - `docs/DECISIONS.md` (수정): ADR-0027 addendum — AR-M4 read path cutover 결정 (fail-soft 패턴 / JSONB 역직렬화 / web UI 제외 rationale).
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md`: TASK-0118 등록 + CHG-20260527-AR-M4 + REV-20260527-0008 + FUNCTION REQ append.

## CHG-20260527-AR-M3
- Date: 2026-05-27
- TASK-Cycle: TASK-0117, **Minor §12.3** — backfill ETL (신규 파일만)
- Summary: Phase 2 AR-M3 backfill ETL. `scripts/runtime_backfill.py` 신규 (~280 LOC) — TABLE_ORDER(FK 순서) + TABLE_MAPPING(6 entry, id_col/offset_pk/since_col/jsonb_indices) + _iter_mysql_rows + _build_insert_sql + _insert_pg_batch + backfill_table + main. `bin/runtime-backfill.sh` wrapper 신규. `tests/test_runtime_backfill.py` 신규 (19 test). outside-voice 생략 (신규 파일만, caller 수정 0건, RBAC 무변경). pytest 19/19 PASS (신규) + 101/103 PASS (전체, pre-existing 2 제외).
- Worktree: `ai/claude/agent-runtime/m3` (base = main HEAD 0048c10).
- Files:
  - `unit/feature-0002-agent-core/src/scripts/runtime_backfill.py` (신규, ~280 LOC): 6 테이블 MySQL→Postgres backfill. TABLE_ORDER FK 순서 (core_conversations 선행). offset_pk=True→OFFSET pagination (conversations/kv/summary). id_col→Id>last_id pagination (core_messages/messages/steps). `%s::jsonb` cast (tool_calls index=3, meta_json index=3). append-only 테이블은 ON CONFLICT 없음 (state file checkpoint 재개 기반). `--since AGENT_RUNTIME_DUAL_WRITE_START_TS` filter. AGENT_RUNTIME_BACKFILL_STATE_DIR env.
  - `bin/runtime-backfill.sh` (신규): docker exec wrapper. `python -m scripts.runtime_backfill "$@"`. state dir=/shared.
  - `unit/feature-0002-agent-core/tests/test_runtime_backfill.py` (신규, 19 tests): TABLE_ORDER/MAPPING 정합 + state round-trip + SQL 검증 + dry-run no-op + id skip + jsonb cast 확인 + main smoke.
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md`: TASK-0117 등록 + CHG-20260527-AR-M3 + REV-20260527-0007 + FUNCTION REQ append.

## CHG-20260527-AR-M2-cd
- Date: 2026-05-27
- TASK-Cycle: TASK-0115 (AR-M2-c) + TASK-0116 (AR-M2-d), **Minor §12.3** — audit helper + verify/stress scripts + xmax tagging
- Summary: Phase 2 AR-M2-c/d cycle. `_log_runtime_write_audit()` + `_build_runtime_audit_resource_id()` + `_RT_AUDIT_ACTION_MAP` + `_rt_pg_op_local` thread-local + `_execute_upsert_with_branch()` (xmax pg_branch tagging) + 3 upsert SQL에 `RETURNING (xmax = 0) AS pg_inserted` 절 추가 + `bin/runtime-dual-write-verify.sh` + `bin/runtime-dual-write-stress.sh`. outside-voice review (general-purpose subagent) Verdict PASS (minor note 3개 non-blocking). pytest 82/82 PASS. verify.sh --counts PASS.
- Worktree: `ai/claude/agent-runtime/m2cd` (base = main HEAD 5719e21).
- Files:
  - `unit/feature-0002-agent-core/src/modules/runtime_backend.py` (수정): `AGENT_RUNTIME_AUDIT_ENABLED` + `_rt_pg_op_local` thread-local + `_RT_AUDIT_ACTION_MAP` + `_RT_AUDIT_SENSITIVE_KEYS` + `_CHANGE_JSON_MAX` + `_build_runtime_audit_resource_id()` + `_log_runtime_write_audit()` + `PgRuntimeBackend._execute_upsert_with_branch()` + 3 upsert SQL에 `RETURNING (xmax = 0) AS pg_inserted` 절 + `_dual_write_runtime_mirror` 내 pg_branch 수집 + audit 호출 (mirror 성공 후 `else` 절).
  - `bin/runtime-dual-write-verify.sh` (신규, ~155 LOC): --counts/--audit-sla/--all 3 mode. 6 테이블 MySQL↔PG count 비교 + audit miss_rate SLA (≤0.1% target). ISO 8601 timezone offset 허용. SINCE auto-load from AGENT_RUNTIME_DUAL_WRITE_START_TS.
  - `bin/runtime-dual-write-stress.sh` (신규, ~80 LOC): 5 scenario × N iterations. --dry-run mode. docker compose run.
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REVIEW,FUNCTION,REPORT}.md`: TASK-0115/0116 등록 + CHG-20260527-AR-M2-cd + REV-20260527-0006 + FUNCTION REQ append.
- 검증: pytest 82/82 PASS (pre-existing 2 제외). bash -n PASS. verify.sh --counts PASS (PG=0 정상, dual-write 비활성).
- Outside-voice rationale: **실행** (`REV-20260527-0006 [SUBAGENT:general-purpose]`) — AR-M2-c Minor 이지만 cross-DB audit SQL (MySQL webauditevents INSERT) + 2 bash script 신규. Verdict: PASS.

## CHG-20260527-AR-M2-b
- Date: 2026-05-27
- TASK-Cycle: TASK-0114 (REQ-20260527-AR-M2-b, **Major §12.3** — PgRuntimeBackend 구현 + caller mirror callsite 추가)
- Summary: Phase 2 AR-M2-b cycle. `PgRuntimeBackend` 6 method body 실제 구현 + `_dual_write_runtime_mirror` connection 내부화 + `memory.py` / `agent_core.py` 7개 caller mirror callsite 추가 + `test_dual_write_runtime.py` 13 test 신규 + `test_anchor_invariant_runtime.py` M2-b API 반영 수정. outside-voice review (general-purpose subagent): tool_calls::jsonb 캐스트 누락 발견 → 본 cycle 내 반영 완료. pytest 23/23 PASS (runtime test files) + 전체 suite 82/82 PASS.
- Worktree: `ai/claude/agent-runtime/m2b` (base = main HEAD AR-M2-a commit).
- Files:
  - `unit/feature-0002-agent-core/src/modules/runtime_backend.py` (수정, +~185 LOC): 6 SQL 상수 신규 (schema-qualified, named params %(name)s) + `PgRuntimeBackend` 6 method body + `_get_pg_runtime_conn()` 신규 + `_dual_write_runtime_mirror` 시그니처 변경 (pg_conn_factory 제거 → connection 내부화) + conn open 단계 try/except (PG_REQUIRED 분기) + tool_calls::jsonb 캐스트 (outside-voice C1 반영).
  - `unit/feature-0002-agent-core/src/modules/memory.py` (수정, +4 mirror callsite): `save_memory_message` / `save_memory_kv` / `save_memory_summary` / `save_memory_step` — MySQL write 후 `_dual_write_runtime_mirror()` 호출.
  - `unit/feature-0002-agent-core/src/agent_core.py` (수정, +3 mirror callsite): `_save_message` / `_ensure_conversation` / `_update_conversation_topic` — MySQL write 후 `_dual_write_runtime_mirror()` 호출.
  - `unit/feature-0002-agent-core/tests/test_dual_write_runtime.py` (신규, 13 test): FakeConn/FakeCursor 패턴. 12개 검증 항목 (no-op / pg unavailable / SQL 정합 / conn lifecycle / memory.py caller 연동).
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_runtime.py` (수정): `test_pg_backend_all_methods_raise_not_implemented` → `test_pg_backend_all_methods_implemented` (M2-b 구현 완료 반영). 3개 mirror 테스트 monkeypatch 패턴 업데이트 (`_get_pg_runtime_conn` 직접 패치).
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md`: TASK-0114 등록 + CHG-20260527-AR-M2-b + REV-20260527-0005 + FUNCTION REQ append.
- 검증: pytest 23/23 PASS (runtime test files) + 전체 suite 82/82 PASS (pre-existing 2 failure: test_kb_backfill.py, main 브랜치 동일). bash -n PASS.
- Outside-voice rationale: **실행** (`REV-20260527-0005 [SUBAGENT:general-purpose]`) — AGENTS.md §18.3 Major 분류 (caller 수정 7건 포함). Verdict: NEEDS-FIX → tool_calls::jsonb 캐스트 추가로 해소.

## CHG-20260527-AR-M2-a
- Date: 2026-05-27
- TASK-Cycle: TASK-0113 (REQ-20260527-AR-M2-a, **Minor §12.3** — ABC + skeleton, code mutation 비파괴)
- Summary: Phase 2 AR-M2-a cycle. `RuntimeBackend` ABC + `MysqlRuntimeBackend` / `PgRuntimeBackend` skeleton + `_dual_write_runtime_mirror` entry point (no-op) + `test_anchor_invariant_runtime.py` 시나리오 카탈로그 (10 test). AGENT_RUNTIME_DUAL_WRITE default False — 기존 MySQL callsites 전혀 무영향. outside-voice 불요 (신규 파일만, 기존 caller 0 수정).
- Worktree: `ai/claude/agent-runtime/m2b` (연속).
- Files:
  - `unit/feature-0002-agent-core/src/modules/runtime_backend.py` (신규, ~220 LOC)
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_runtime.py` (신규, 10 test)

## CHG-20260527-AR-M0
- Date: 2026-05-27
- TASK-Cycle: TASK-0111 (REQ-20260527-AR-M0, **Minor §12.3** — Postgres 인프라 도입, 비파괴 추가)
- Summary: Phase 2 AR-M0 cycle. `agent_kb` DB 안 `agent_runtime` schema 신설 + agent_kb_rw/ro role 에 USAGE + DEFAULT PRIVILEGES grant. schema 설계 원칙: schema-qualified SQL (`agent_runtime.*`) 사용 — search_path 전역 변경 없음. 실제 적용 결과: has_schema_privilege(agent_kb_rw, agent_runtime, USAGE)=t / agent_kb_ro=t. docs/SECURITY.md §10 신규 (agent_runtime schema RBAC 정책). outside-voice 불요 (기존 role 재사용, 신규 role 신설 없음, 비파괴 추가).
- Worktree: `ai/claude/agent-runtime/m0` (base = main HEAD 67a853b).
- Files:
  - `bin/agent-runtime-bootstrap.sh` (신규, ~110 LOC): agent_runtime schema CREATE IF NOT EXISTS + role USAGE grant + DEFAULT PRIVILEGES. 멱등 + --check mode. kb-pg-role-bootstrap.sh 패턴 답습.
  - `docs/SECURITY.md`: §10 신규 — agent_runtime Postgres schema RBAC 정책.
  - `docs/MIGRATION_AGENT_MEMORY_TO_PG.md`: §7 진행 기록 AR-M0 entry + AR-M0 task 완료 마킹.
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REPORT,REVIEW}.md`: TASK-0111 등록 + CHG-20260527-AR-M0 + REPORT Summary append + REVIEW SKIPPED entry.
- 검증: bash -n PASS + `bash bin/agent-runtime-bootstrap.sh` PASS (schema=t, rw_usage=t, ro_usage=t). code/RBAC mutation 0건 (신규 role 신설 없음).
- Outside-voice rationale: **SKIPPED** (`REV-20260527-0002 [SKIPPED:infra-schema-only-no-new-role]`) — 기존 role 재사용 + schema CREATE 만. ARR-M1 (DDL + RBAC, outside-voice 필수) 에서 outside-voice 호출.

## CHG-20260527-AR-M-1
- Date: 2026-05-27
- TASK-Cycle: TASK-0110 (REQ-20260527-AR-M-1, **Minor §12.3** — read-only baseline 측정)
- Summary: Phase 2 AR-M-1 cycle. 6 agent runtime 테이블 (AgentCoreConversations / AgentCoreMessages / AgentMemoryKv / AgentMemoryMessages / AgentMemorySteps / AgentMemorySummary) 의 사전 baseline 측정 실행. 총 2676 row (Conversations 33 / Messages 392 / Kv 1987 / MemoryMessages 123 / Steps 141 / Summary 0). insert rate 측정: AgentCoreMessages ~9.5 row/day, AgentMemoryMessages ~3.0/day, AgentMemorySteps ~3.4/day. callsite 인벤토리: feature-0002-agent-core/src 54건 + feature-0003-agent-web-ui/src 105건. explicit FK constraint 0건 (application-level implicit FK 확인). AgentMemoryKv PK = (ConversationId, Key) composite — __global__ scope 1588건 + conversation-scoped 399건. outside-voice 불요 (read-only, code/schema/RBAC mutation 0건).
- Worktree: `ai/claude/agent-runtime/m-1` (base = main HEAD 9a0610a).
- Files:
  - `bin/agent-runtime-measure-baseline.sh` (신규, ~190 LOC): Phase 2 AR-M-1 baseline 측정 스크립트. kb-measure-baseline.sh 패턴 답습. wrapper path auto-detect + docker exec repo-mysql-1 + 5 mode (--rows/--schema/--callsites/--fk/--kv/--all). JSON artifact 생성.
  - `unit/feature-0002-agent-core/docs/{TASK,MODIFY,REPORT}.md`: TASK-0110 등록 + CHG-20260527-AR-M-1 + REPORT Summary append.
  - `docs/MIGRATION_AGENT_MEMORY_TO_PG.md`: §7 진행 기록 TASK-0110 entry append.
- 검증: 실 code 변경 0 → py_compile 불요. bash -n agent-runtime-measure-baseline.sh PASS. baseline script --all 실행 PASS (artifacts/shared/agent-runtime-baseline-2026-05-27.json 생성).
- Outside-voice rationale: **SKIPPED** — read-only baseline 측정. code/schema/RBAC mutation 0건. 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합.

## CHG-20260526-0109
- Date: 2026-05-26
- TASK-Cycle: TASK-0109 (REQ-20260526-0109, **Minor §12.3** — plan-only, project-level cross-cutting migration plan 등록)
- Summary: 사용자 결정 (2026-05-26): agent_memory MySQL DB 의 모든 테이블 (agent\* 11개 + web\* 18개) 을 PostgreSQL 로 이관 + 최종 agent_memory MySQL DB 자체 deprecation. agent\* 11개 → agent_kb DB 안 새 schema `agent_runtime` 신설. 본 cycle 은 **plan-only** (실 code/schema/RBAC mutation 0건). 정본 plan 문서 신규 작성 + 신규 세션 진입 자료 정착.
- Worktree: `ai/claude/agent-memory-pg-plan` (base = main HEAD 12b06b2).
- Files:
  - `docs/MIGRATION_AGENT_MEMORY_TO_PG.md` (신규, ~280 LOC): project-level cross-cutting plan 정본. Phase 1 (KB 5 정본 cleanup 마무리 — 기존 TASK-0015 §2.1 의 M5 마무리) + Phase 2 (6 agent runtime 테이블 신규 이관 cycle, AR-M-1~M5 7-phase 답습) + Phase 3 (18 web\* 별 DB 분리 outline) + Phase 4 (agent_memory MySQL DB 자체 deprecation). 각 Phase 의 Detailed Task List + Acceptance Criteria + 정책 정합 + 진행 기록 append-only.
  - `unit/feature-0002-agent-core/docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`: cycle 등록 + REQ-20260526-0109 + CHG-20260526-0109 + REV-20260526-0003 (SKIPPED) + Summary append.
- 검증: 실 code 변경 0 → py_compile / node check 불요. plan 문서 markdown lint 만.
- Runtime 검증 deferral: 본 cycle 은 plan 문서 등록 — runtime 변경 0. 신규 세션이 Phase 2 AR-M-1 (baseline 측정) 부터 진입 시 실 작업 시작.
- 사용자 결정: AGENTS.md §16.3 Step 2 조건표 (BLOCKED 없음 + Critical/Major 승인 대기 없음) 충족 → 자동 commit + push + PR + squash merge 진행.
- Outside-voice rationale: **SKIPPED** — `REV-20260526-0003 [SKIPPED:plan-only-no-code-no-rbac-no-schema]`. 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합 — 본 cycle 은 RBAC catalog 변경 0, code path 변경 0, schema mutation 0. 단지 markdown plan 문서 1개 신규 + docs append. 실 design 결정 (Phase 2 의 schema 선택 `agent_runtime` vs 별 DB) 은 본 plan 의 결과이지만 implementation cycle 별로 outside-voice 호출 (AR-M1 DDL+RBAC, AR-M4 cutover, AR-M5 cleanup 시점).

## CHG-20260526-0001
- Date: 2026-05-26
- TASK-Cycle: TASK-0026 (KB Postgres bootstrap fix, **Major §12.3** — RBAC role 분리 인지 변경 + DDL credential path 도입)
- Summary: 직전 main 배포 (f03c270) 검증 중 `repo-memory-init-1` exit 1 (`KB Postgres schema 적용 실패 (AGENT_KB_PG_REQUIRED=1): attempted relative import with no known parent package`) 증상 정식 fix. **Outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0001`) Verdict BLOCK → PASS 전환 (Critical 3 본 cycle 내 흡수)**: (B-1) memory.py 의 superuser env (`AGENT_KB_PG_SUPERUSER` / `_SUPERPASSWORD`) 가 bootstrap.sh 의 `AGENT_KB_PG_USER` / `_PASSWORD` 와 이름 갈라짐 → unset 시 legacy fallback / (B-2) schema 검증이 fail-loud 아님 → missing_tables / missing_extensions / view_present 검사 후 RuntimeError + actionable hint / (B-3) `except ImportError` 가 `.db` 내부 실제 ImportError (psycopg 부재 등) 까지 덮음 → `e.name` 검사로 fallback 좁힘. Nice-to-have 2 동반 흡수 (.env.example 3 변수 + kb_backfill.py frozen 가정 주석).
- Worktree: `ai/claude/kb-postgres-bootstrap-fix`, base f03c270 (main HEAD). 분리 배경: 이전 세션에서 main worktree `repo/` 직접 수정 (§13.2.7 F0 위반) → stash 로 본 worktree 분리 + main drop 완료, 본 cycle 은 정식 cycle.
- Files:
  - `unit/feature-0002-agent-core/src/Dockerfile` (+1 LOC): `COPY .../src/scripts /app/scripts` 추가 — agent image 가 kb_backfill.py 등 ship.
  - `unit/feature-0002-agent-core/src/agent_core.py` (+/- 2 LOC, line 2016/2018): `from .modules.db import _pg_available` → `from modules.db import _pg_available`, `.modules.memory` → `modules.memory`. entry point `python /app/agent_core.py` 가 `__package__ = None` 라 relative import 실패 — absolute 로 정정.
  - `unit/feature-0002-agent-core/src/modules/memory.py` (+45 LOC, 1410-1467 + 1564-1582): `_ensure_pg_schema()` 의 DDL 을 별 superuser connection 으로 분리. agent_kb_rw 는 DML 전용 (CREATE TABLE / EXTENSION 권한 없음). `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` 1순위 + `AGENT_KB_PG_USER` / `AGENT_KB_PG_PASSWORD` legacy fallback (B-1). `try/except ImportError` 의 `e.name is None or e.name == __package__` 검사로 fallback 범위 좁힘 (B-3). schema 누락 시 RuntimeError + actionable hint (B-2).
  - `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (+45 LOC): `AgentMemoryTexts` PK = `TextHash` (char 64) 반영. texts 만 OFFSET pagination (~800 행 frozen 가정 + 주석 명시) + 다른 테이블 (fact_entries / rag_documents / rag_objects) Id-based cursor pagination 유지 (회귀 0). `_insert_pg_batch()` 의 `row[1:]` slicing 도 `text_hash_pk` flag 분기.
  - `.env.example` (+11 LOC): `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` / `AGENT_KB_PG_SUPERUSER_HOST` 3 변수 + bootstrap.sh 와의 정합 주석.
  - `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: REQ-20260526-0001 + TASK-0026 + CHG-20260526-0001 + REV-20260526-0001 + REPORT Summary append.
- 검증 (본 cycle):
  - `python3 -m py_compile` — memory.py + agent_core.py + kb_backfill.py 3 파일 모두 PASS (SyntaxWarning 은 pre-existing, 본 fix 무관).
  - codex `--sandbox read-only` 로 outside-voice review 호출 → 3 Critical 본 cycle 내 흡수 → Verdict BLOCK → PASS 전환.
- Runtime 검증 deferral (사용자 운영 turn 책임):
  - PR squash merge + main pull --ff-only.
  - production stack `docker compose build memory-init` 또는 `agent` (공유 image).
  - `docker compose up -d memory-init` → exit 0 + 로그에 `KB Postgres schema 적용 완료: tables=[fact_entries, rag_documents, rag_objects, texts], view=True, extensions=[pg_trgm, vector], grants=...` 확인.
  - 만약 production schema 가 부재이면 (history 검증 필요) RuntimeError + actionable hint 출력 → `bin/kb-pg-role-bootstrap.sh --apply-schema` 사전 실행 후 재시도.
- 사용자 결정: AGENTS.md §16.3 Step 2 조건표 (BLOCKED 없음 + Critical/Major 승인 대기 없음) 충족 → 자동 commit + push + PR + squash merge 진행. PLAN-APPROVED 범위는 §2.1 의 M2 phase 의 KB Postgres bootstrap path 가 사전 승인 — 본 fix 는 그 path 의 implementation defect 정정.
- Outside-voice rationale: 호출 ✓ — `REV-20260526-0001` (Codex). RBAC role 분리 인지 변경 = 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합 (정적 catalog blindspot 대응).

## CHG-20260522-0009
- Date: 2026-05-22
- TASK-Cycle: TASK-0025 (M5 cleanup script + ADR-0025 + dual-write deprecation note, **Major §12.3** — RBAC 영향 + 데이터 손실 boundary)
- Summary: §2.1 PLAN-APPROVED 의 **M5 phase (Cleanup — MySQL KB 5 정본 deprecation)** — M4 cutover 후 MySQL KB 5 정본 의 deprecation 절차 명문화 + cleanup script + ADR-0025. **Outside-voice review (Plan subagent, `REV-20260522-0013`) Verdict FAIL + Blocker 5 + Critical 4 본 cycle 내 반영** (B-1 mysqldump VIEW DDL 포함 / B-2 backup integrity verify / B-3 AGENT_KB_DUAL_WRITE=0 sentinel / B-4 14-day window runtime enforce / B-5 mode 중복 + missing arg 거부 / B-6 TTY interactive confirm / B-7 env fallback / B-8 chmod + SHA256). C-2 + C-7 동반 흡수.
- Worktree: `ai/claude/0002/kb-pg-m5`. 사용자 결정: "이번 세션에서 남은 cycle을 모두 완수해주세요".
- Files:
  - `bin/kb-cleanup-mysql.sh` (신규 ~250 LOC): 3 mode + integrity verify + 14-day window + DUAL_WRITE=0 sentinel + TTY confirm + env fallback + chmod/SHA256.
  - `docs/DECISIONS.md`: ADR-0025 추가 (M5 cleanup 정책 + 14-day window + Stage A/B/C 정량화).
  - `modules/kb_backend.py`: `_DualWriteMirror` DEPRECATION NOTICE docstring.
  - `tests/test_m5_cleanup.py` (신규 ~180 LOC): 11 unit test.
- 검증: pytest 51 PASS / 2 SKIP + bash -n + dry-run.
- Runtime 검증 deferral: M5-implementation cycle 의 caller 코드 삭제 → AGENT_KB_DUAL_WRITE=0 → mysqldump backup → DROP 실행 (TTY typed confirm 추가).
- 사용자 결정: 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: 호출 ✓ — `REV-20260522-0013`. FAIL → PASS 전환.

## CHG-20260522-0008
- Date: 2026-05-22
- TASK-Cycle: TASK-0024 (M4 cutover — FULLTEXT → pg_trgm + AGENT_KB_READ_BACKEND routing + cutover readiness, **Major §12.3** — RBAC 영향 cycle)
- Summary: §2.1 PLAN-APPROVED 의 **M4 phase (Cutover — read path 전환)** — `knowledge.py:1438` 의 MySQL FULLTEXT `MATCH AGAINST NATURAL LANGUAGE MODE` 를 PG pg_trgm `similarity()` 로 routing (AGENT_KB_READ_BACKEND env 분기) + cutover readiness 10-gate script + `agent_kb_ro` role 분리. **Outside-voice review (Plan subagent, `REV-20260522-0012`) Verdict FAIL + Critical 4 본 cycle 내 반영** (B-1 logger 미정의 / B-2 scope NULL/'' 매치 누락 / B-3 RW user RBAC 회귀 / B-4 fail-soft regression test 부재). B-5 (REQUIRED=1 fail-loud 모순) 는 M4-tweak follow-up.
- Worktree: `ai/claude/0002/kb-pg-m4` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m4/`. 사용자 결정 (2026-05-22): "이번 세션에서 남은 cycle을 모두 완수해주세요" → 본 cycle 진행.
- Files (read backend + cutover gate + test):
  - `modules/kb_backend.py` (+~85 LOC): 4 PG SQL constants (`_PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_INCL_NULL` + `_STRICT` + `_NO_TEXT_INCL_NULL` + `_STRICT`) — pg_trgm `similarity(COALESCE(t.text_content, ''), %(query_text)s)` + `_INCL_NULL` 분기 (NULL/'' 매치 동반). `PgKbBackend.search_rag_documents()` method — scope_keys 의 blank/None 검출 → 4 variant SQL 분기.
  - `modules/db.py` (+~45 LOC): `_pg_connect_ro()` 신규 — `AGENT_KB_PG_USER_RO` / `_PASSWORD_RO` 사용. 미설정 시 RW fallback + warning log.
  - `modules/config.py` (+~6 LOC): `AGENT_KB_PG_USER_RO` / `AGENT_KB_PG_PASSWORD_RO` binding + EXPORT_VARS 등록.
  - `modules/knowledge.py` (+~50 LOC): `import logging` + module-level `logger` 정의 (REV-20260522-0012 B-1) + `_load_rag_documents_for_request()` 안에 `AGENT_KB_READ_BACKEND=postgres` 분기 + fail-soft except + MySQL fallback. `_normalize_rag_doc_rows()` 추출 (MySQL + PG 공통). `_load_rag_documents_for_request_pg()` 신규 — `_pg_connect_ro()` 사용 + `PgKbBackend.search_rag_documents()` 호출.
  - `bin/kb-cutover-readiness.sh` (신규 ~190 LOC): 10-gate readiness 검증 (dual-write SLA + pg_branch coverage + invariant test + unit test + backfill row count + embedding NULL=0 + p99 latency + TRUNCATE denied + ask 5종 회귀 + env 변수). Gate 7/9 INCONCLUSIVE (운영자 책임). `--skip-ask-regression` / `--skip-latency` / `--since` options. exit code 0=PASS / 1=FAIL / 2=INCONCLUSIVE.
  - `tests/test_kb_read_backend.py` (신규 ~250 LOC): 9 unit test (pg_trgm SQL emit + NO_TEXT 분기 + empty conv_ids + scope_keys None + _pg_available False → None + backend 호출 spy + B-4 fail-soft regression + B-2 blank scope INCL_NULL + strict scope no NULL).
  - `docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + `REV-20260522-0012` + 본 entry.
- Outside-voice review (Plan subagent) Critical 4 본 cycle 내 반영:
  1. **Critical/Blocker B-1**: `knowledge.py` 의 `import logging` + module-level `logger` 정의 ✓
  2. **Critical/Blocker B-2**: PG `_INCL_NULL` SQL variant + scope candidate 분기 ✓
  3. **Critical/Blocker B-3**: `_pg_connect_ro()` + `AGENT_KB_PG_USER_RO/PASSWORD_RO` env + read path 사용 ✓
  4. **Critical B-4**: `test_pg_read_failure_falls_back_to_mysql` + B-2 blank scope test ✓
- 검증 (본 cycle):
  - `pytest tests/test_kb_read_backend.py -v` — 9 PASS
  - `pytest tests/` 전체 — 40 PASS, 2 SKIPPED (회귀 없음)
  - `bash -n bin/kb-cutover-readiness.sh` — syntax PASS
- Runtime 검증 deferral (사용자 / M5 별 cycle 책임):
  - `bin/kb-cutover-readiness.sh --since <ISO>` 운영 환경 실 실행 — Gate 1~10 모두 PASS 확인
  - production-like 환경에서 p99 latency 측정 (Gate 7)
  - `make ask` 5종 회귀 시나리오 실 실행 (Gate 9)
  - `.env` 의 `AGENT_KB_READ_BACKEND=postgres` 전환 → agent 재기동
  - canary 1 주일 monitoring
- 사용자 결정 (2026-05-22): 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: 호출 ✓ — `REV-20260522-0012 [SUBAGENT:Plan-subagent]`. M4 cutover 가 read backend switch + RBAC 영향 cycle. FAIL Verdict + Critical 4 본 cycle 흡수 → PASS 전환. B-5 (M4-tweak) + Nice-to-have C-1/C-2/C-3/C-5 (M4-tweak/M5) 위임.

## CHG-20260522-0007
- Date: 2026-05-22
- TASK-Cycle: TASK-0023 (M3 backfill ETL + embedding worker, **Minor §12.3** — RBAC 무변경)
- Summary: §2.1 PLAN-APPROVED 의 **M3 phase** — M2 dual-write 시작 시점 이전의 MySQL 4 KB table row 를 Postgres 의 4 등가 table 로 backfill + `texts.embedding` 일괄 생성. **본 cycle 산출 6건**: (a) `scripts/kb_backfill.py` (~280 LOC), (b) `scripts/kb_embedding_worker.py` (~190 LOC), (c) `bin/kb-backfill.sh` wrapper, (d) `bin/kb-embedding-worker.sh` wrapper, (e) `modules/config.py` 의 AGENT_KB_EMBEDDING_* 5 env binding, (f) `tests/test_kb_backfill.py` (4 test) + `tests/test_kb_embedding_worker.py` (6 test). outside-voice review **SKIPPED** (`REV-20260522-0011`) — RBAC 변경 없음.
- Worktree: `ai/claude/0002/kb-pg-m3` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m3/`. 사용자 결정 (2026-05-22): "이번 세션에서 남은 cycle을 모두 완수해주세요" → 본 cycle 진행.
- Files (ETL + embedding + test):
  - `scripts/kb_backfill.py` (신규 ~280 LOC): TABLE_MAPPING (4 table) + load_state/save_state (artifacts/shared/kb-backfill-state.json) + open_mysql_conn/open_pg_conn 재사용 + _iter_mysql_rows paginate + _insert_pg_batch ON CONFLICT DO NOTHING + backfill_table progress logging + main() argparse.
  - `scripts/kb_embedding_worker.py` (신규 ~190 LOC): get_settings + open_pg_conn + call_openai_embeddings (retry + timeout) + count_pending/fetch_pending_batch/update_embeddings + estimate_cost_usd + main() argparse + dry-run cost estimation.
  - `bin/kb-backfill.sh` (신규 ~45 LOC): docker exec agent + AGENT_KB_BACKFILL_STATE_DIR=/shared.
  - `bin/kb-embedding-worker.sh` (신규 ~25 LOC): docker exec agent.
  - `modules/config.py` (+~15 LOC): AGENT_KB_EMBEDDING_MODEL/DIM/BATCH_SIZE/TIMEOUT_SEC/MAX_ATTEMPTS binding + EXPORT_VARS 등록.
  - `tests/test_kb_backfill.py` (신규 ~125 LOC): 4 unit test.
  - `tests/test_kb_embedding_worker.py` (신규 ~140 LOC): 6 unit test.
  - `docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록.
- 검증 (본 cycle): pytest 31 PASS / 2 SKIPPED + bash -n PASS.
- Runtime 검증 deferral (사용자 / M4 별 cycle): backfill 실 ETL + embedding 실 OpenAI 호출.
- 사용자 결정 (2026-05-22): 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: SKIPPED ✓ — `REV-20260522-0011 [SKIPPED:rbac-unchanged-data-migration]`.

## CHG-20260522-0006
- Date: 2026-05-22
- TASK-Cycle: TASK-0022 (M2-d pg_branch xmax + S2/S4/S5/S6 + tagging coverage gate + Nice-to-have 7, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 4차 (M2-d)** — M2-c (TASK-0021) 의 audit infrastructure 위에 outside-voice REV-20260521-0009 Nice-to-have 8건 中 7건 (C-1~C-7 — C-8 은 M2-c 흡수) + pg_branch xmax tagging (B-1 follow-up) + S2/S4/S5/S6 mock-pattern 실 구현 + tagging coverage gate + latency instrumentation 흡수. **Outside-voice review (Plan subagent, `REV-20260522-0010`) Verdict NEEDS-TWEAK + Blocker 2 + Critical 4 본 cycle 내 반영** (B-1 stress `--keep-agent-container` agent CLI 정정 / B-2 SLA → tagging coverage rename + 한계 명시 / B-3+B-4 `_clear_pg_branch()` 위치 mirror 첫 줄 / C-5 truncate 시 pg_branch 보존 / C-1 xmax docstring / C-2-3-4 metrics+regex docstring). **본 turn 의 deliverable 은 6 산출 + Critical 6 흡수까지**. M3 backfill ETL + embedding worker 는 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2d` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2d/`. 사용자 결정 (2026-05-22): "이번 세션에서 남은 cycle을 모두 완수해주세요" → 본 cycle 진행.
- Files (instrumentation + tooling + test):
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~150 LOC): 3 UPSERT SQL 에 `RETURNING id, (xmax = 0) AS pg_inserted` + `_pg_op_local = threading.local()` + `_get_last_pg_branch()` / `_clear_pg_branch()` helpers (`_mirror()` 첫 줄 clear, REV-20260522-0010 B-3/B-4 흡수) + `_execute_returning_id()` branch 캡쳐 + delete/prune/upsert_text branch 라벨 + `_log_kb_write_audit(pg_branch=...)` 시그니처 + ChangeJson `pg_branch` 필드 + truncate 의 `pg_branch`/`pg_op_kind` 보존 (REV-20260522-0010 C-5) + `_MIRROR_METRICS` + `get_mirror_metrics()` / `reset_mirror_metrics()` API + `_record_mirror_latency()` + `_record_audit_event()` + `_DualWriteMirror._mirror()` 의 `time.monotonic()` based timing 모든 path.
  - `bin/kb-dual-write-verify.sh` (+~85 LOC): `verify_pg_branch_tag_coverage()` 신규 (REV-20260522-0010 B-2 흡수, NOT a cross-DB SLA 명시) + `--pg-branch-tag-coverage` mode + `--since` ISO 8601 정규식 보강 (C-4) + stderr suppress 일부 제거 (C-7) + `--all` worst exit code propagation (C-9).
  - `bin/kb-dual-write-stress.sh` (+~50 LOC): `--keep-agent-container` mode (REV-20260522-0010 B-1 — agent CLI positional `python /app/agent_core.py "$question"` 정정) + `--log-dir` per-step log (C-3).
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~150 LOC): `_setup_mock_mirror_env()` 공통 fixture + S2/S4/S5/S6 mock-pattern 실 구현 + S3 SQL 정합 assertion.
  - `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (+~80 LOC): Test 11 (pg_branch insert/update) + Test 12 (metrics counter).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + `REV-20260522-0010` + 본 entry + Summary + risk log.
- 검증: pytest 21 PASS / 2 SKIPPED + bash -n + dry-run + verify-completion 10/10 PASS.
- Runtime 검증 deferral (M3 별 cycle): `--pg-branch-tag-coverage --since <ISO>` 실 측정 + `--keep-agent-container` latency 정량 + `get_mirror_metrics()` production sampling.
- 사용자 결정 (2026-05-22): 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: `REV-20260522-0010 [SUBAGENT:Plan-subagent]` — RBAC 동반 audit instrumentation 변경. Blocker 2 + Critical 4 본 cycle 내 흡수 + Nice-to-have 5 동반 흡수, 3건 M3 위임.

## CHG-20260522-0005
- Date: 2026-05-22
- Summary: TASK-0101 (REQ-20260522-0004, **Minor §12.3** — backlog closure batch, cross-feature docs). 본 세션의 잔여 backlog 항목 일괄 closure: feature-0002 의 TASK-0010/0011 + feature-0001/0004/0005/0006 의 TASK-0004 (시나리오 정의 placeholder) + feature-0005 의 TASK-0005 (MCP 서비스 기동 검증, 본 cycle 실 환경 검증) + TASK-0072 (이미 main 에서 closure 확인). 환경 의존 / 활발한 진행 cycle (TASK-0034/0044/0020/0021) 은 deferral 명시.
- Files:
  - `unit/feature-0001-platform-runtime/docs/TASK.md`: TASK-0004 [x] 마킹.
  - `unit/feature-0002-agent-core/docs/TASK.md`: TASK-0010 + TASK-0011 [x] 마킹 + TASK-0101 queue entry + Current Status 갱신.
  - `unit/feature-0002-agent-core/docs/FUNCTION.md`: REQ-20260522-0004 + AC-0010~0013 신규.
  - `unit/feature-0002-agent-core/docs/MODIFY.md`: CHG-20260522-0005 (본 entry).
  - `unit/feature-0002-agent-core/docs/REVIEW.md`: REV-20260522-0005 [SKIPPED:docs-only-batch-closure].
  - `unit/feature-0002-agent-core/docs/REPORT.md`: §1 Summary 갱신 + deferral 명시 (TASK-0034/0044/0020/0021).
  - `unit/feature-0004-browser-automation/docs/TASK.md`: TASK-0004 [x] 마킹.
  - `unit/feature-0005-qa-mcp/docs/TASK.md`: TASK-0004 + TASK-0005 [x] 마킹.
  - `unit/feature-0006-lan-proxy-access/docs/TASK.md`: TASK-0004 [x] 마킹.
  - `docs/STATUS.md`: TASK-0101 closure entry prepend + 5 feature 의 last-updated 갱신 (선택 — 본 cycle 의 scope 는 feature-0002 ownership 으로 minimal).
- 검증: docs / 마킹만, 코드 / RBAC / DB / endpoint / audit 무변경. TASK-0005 (MCP) 의 실 환경 검증 결과: `docker ps repo-mcp-1` = `Up 23 hours`, `curl http://localhost:28000/healthz` HTTP 200, Workbench gated UI 응답 정상.
- 위험도: §12.3 **Minor** — closure 마킹 + docs 명시만, 동작 변경 0. outside voice / plan-eng-review 불필요.

## CHG-20260522-0004
- Date: 2026-05-22
- Summary: TASK-0100 (REQ-20260522-0003, **Minor** §12.3 — multipart UploadFile 의존성 hot-fix). TASK-0098 (PR #49) ship 후 사용자 검증 단계에서 발견된 main 의 build 회귀 차단. PR #66 (TASK-0094 Sprint 1 Phase 5) 가 도입한 `POST /api/conversations/{cid}/attachments` 의 `file: UploadFile` 이 `python-multipart` 의존성을 필요로 하나 `unit/feature-0002-agent-core/src/requirements.txt` 에 추가되지 않아 web container `Restarting` + `RuntimeError: Form data requires "python-multipart" to be installed.` 발생.
- Files:
  - `unit/feature-0002-agent-core/src/requirements.txt`: `python-multipart>=0.0.9` 한 줄 + 4 줄 annotation (TASK-0100 / REQ-20260522-0003 / 발견 시점 / REV-20260522-0004).
  - `unit/feature-0002-agent-core/docs/FUNCTION.md`: REQ-20260522-0003 + AC-0008 + AC-0009 신규.
  - `unit/feature-0002-agent-core/docs/TASK.md`: TASK-0100 queue entry [x] + Current Status 갱신.
  - `unit/feature-0002-agent-core/docs/REVIEW.md`: REV-20260522-0004 [SKIPPED:hot-fix-dependency-only].
  - `unit/feature-0002-agent-core/docs/REPORT.md`: §1 Summary 갱신.
- 검증: `docker compose build web` PASS + `force-recreate` 후 web container `Up` 안정 (TASK-0098 사용자 검증 단계에서 본 fix 위에서 HTTP smoke 5/5 + UI dogfood 4 스크린샷 PASS 확인).
- 위험도: §12.3 **Minor** — 의존성 추가만, 동작 변경 0. outside voice / plan-eng-review 불필요.

## CHG-20260522-0003
- Date: 2026-05-22
- TASK-Cycle: TASK-0021 (M2-c cross-DB audit explicit call + SLA verify body + stress.sh body + ANCHOR §3 invariant test S1/N1/N2, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 3차 (M2-c)** — M2-b (TASK-0020) 의 dual-write 위에 ADR-0021 §Consequences M2-c 책임 5건 흡수. **Outside-voice review (Plan subagent, `REV-20260521-0009`) Verdict NEEDS-TWEAK + Critical 6 본 cycle 내 반영** (B-1 audit SLA 분모/분자 정정 / B-2 N1 LLM tripwire `modules.llm` 정정 + smoke assertion / B-3 prune signature `keep_limit=` + DELETE SQL assertion / B-4 `connect_with_retry(attempts=1)` / B-5 ResourceId composite builder / B-6 ChangeJson 16KB 캡). **본 turn 의 deliverable 은 5 산출 + Critical 6 흡수까지**. S2-S6 invariant fixture + delete/prune SLA 별 metric (pg_branch xmax tagging) + latency baseline production-like 측정 + Nice-to-have 8건은 M2-d 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2c` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2c/`. 사용자 결정 (2026-05-22): "확인했습니다. 다음 Phase도 진행해주세요" → 본 cycle 진행 + "(1) 방향으로 진행" → Critical 5 본 cycle 흡수.
- Files (audit + tooling + test):
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~157 LOC, 762 → ~919 → ~1085 LOC): `import threading` + `_BACKENDS_LOCK` double-checked locking (`get_backends()`) + `_KB_AUDIT_ACTION_MAP` (6 method → ActionCode/ResourceType) + `_KB_AUDIT_SENSITIVE_KEYS` (`text_content`, `source_sql` 제외) + `_build_audit_resource_id()` composite (REV-20260521-0009 B-5 — conv|scope|key|... 식별 정밀화) + `_log_kb_write_audit()` helper (`connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1)`, REV-20260521-0009 B-4 — best-effort; ChangeJson 16KB 캡, REV-20260521-0009 B-6; `pg_op_kind` 태깅 write/delete/prune, REV-20260521-0009 B-1) + `_DualWriteMirror._mirror()` 의 audit explicit call 통합 (mirror 성공 후 try/except 격리).
  - `bin/kb-dual-write-verify.sh` (+~125 LOC): `verify_counts()` 본문 (4 table pair count diff) + `verify_content_hash()` 본문 (rag_documents content_hash CONCAT identity diff) + `verify_audit_sla()` 본문 (GREATEST(created_at, updated_at) PG denominator + `kb.write.mirror` only audit numerator + `audit > 2 × pg` fail-loud + zero-denom INCONCLUSIVE exit 2 + methodology limitation 명시, REV-20260521-0009 B-1/C-8 흡수).
  - `bin/kb-dual-write-stress.sh` (+~40 LOC): `trigger_insight_cycles()` (docker exec insight-worker `python -c "from agent_core import run_insight_cycle; print(run_insight_cycle(...))"` + container 미가동 시 docker compose run fallback) + `trigger_ask_iterations()` (docker compose run --rm --remove-orphans agent) + FAILURES counter + exit 1 on any failure.
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~290 LOC, 147 → ~440 LOC): S1 (RagDocuments missing) 실 구현 (FakeConn + FakeCursor SQL 캡쳐 + monkeypatch `_log_kb_write_audit` 우회 + RETURNING id mock + LLM tripwire 동반) + N1 (LLM call zero) 실 구현 (`modules.llm._get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix 전체 + `modules.llm.OpenAI` 직접 monkeypatch + smoke assertion 1 patch 미설치 시 즉시 fail, REV-20260521-0009 B-2 흡수; 6 mirror method invocation + prune `keep_limit=` 정정 + DELETE SQL assertion, REV-20260521-0009 B-3 흡수) + N2 (TRUNCATE denied) env-gated (`AGENT_KB_PG_INTEGRATION_TEST=1` 시 실 psycopg connect → `pytest.raises(InsufficientPrivilege)`) + S2-S6 skip 유지 (M2-d 위임).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + `REV-20260521-0009` + 본 entry + Summary + risk log 갱신.
- Outside-voice review (Plan subagent) Critical 6 본 cycle 내 반영:
  1. **Critical B-1 (audit SLA mismatch)**: verify_audit_sla() 분모 GREATEST(created_at, updated_at) + numerator write-only + over-count fail-loud + zero-denom INCONCLUSIVE + `pg_op_kind` tagging ✓
  2. **Critical B-2 (N1 LLM tripwire 모듈 오인)**: `modules.llm` 정정 + entry point 전수 patch + smoke assertion ✓
  3. **Critical B-3 (prune signature swallow)**: `keep_limit=` 정정 + 6 method SQL assertion ✓
  4. **Critical B-4 (attempts cap 부재)**: `connect_with_retry(attempts=1)` best-effort ✓
  5. **Critical B-5 (ResourceId 평탄화)**: `_build_audit_resource_id()` composite builder 6 method layout 명시 ✓
  6. **Critical B-6 (ChangeJson 길이 캡 부재)**: 16KB 캡 + truncate metadata ✓
- 검증 (본 cycle):
  - `pytest tests/test_anchor_invariant_postgres.py -v` — S1 + N1 PASS, S2-S6/N2 SKIPPED
  - `pytest tests/` 전체 — 15 PASS, 6 SKIPPED (회귀 없음)
  - `bash -n bin/kb-dual-write-verify.sh` / `bin/kb-dual-write-stress.sh` — syntax PASS
  - `bash bin/kb-dual-write-stress.sh --dry-run --insight-cycles 2 --ask-iterations 1` — 모든 command 정상 echo
- Runtime 검증 deferral (M2-d 별 cycle 책임):
  - `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 5` 실 실행
  - `bin/kb-dual-write-verify.sh audit-sla --since <ISO>` → miss_ppm ≤ 1000 검증
  - S2-S6 invariant fixture 실 구현 (실 Postgres + insight worker 통합)
  - delete/prune SLA 별 metric (`pg_branch` xmax tagging + RETURNING (id, xmax=0) 보강)
  - Latency baseline production-like 측정
- 사용자 결정 (2026-05-22): 즉시 자동 commit + push + main 동기화. Critical 5 본 cycle 흡수 후 진행.
- Outside-voice rationale: 호출 ✓ — `REV-20260521-0009 [SUBAGENT:Plan-subagent]`. RBAC role audit ActionCode 신설 + N2 (TRUNCATE denied) check → 메모리 정책 정합. NEEDS-TWEAK + Critical 6 본 cycle 내 반영 + Nice-to-have 8건 M2-d 위임.

## CHG-20260521-0002
- Date: 2026-05-21
- TASK-Cycle: TASK-0020 (M2-b dual-write 본 구현, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 2차 (M2-b)** — M2-a (TASK-0019) 의 ABC + skeleton 위에 method body + caller 5 위치 mirror 호출 + unit test 10. **Outside-voice review (Plan subagent, `REV-20260520-0008`) Verdict NEEDS-TWEAK + Critical 6 + Blocker 2 본 cycle 내 반영**: caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead wrapper 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리) / conftest.py + Test 9 (caller integration) / Test 10 (caplog) / REPORT.md §4 risk log 0번 entry (latency M2-c) / ADR-0021 §Consequences cross-DB audit M2-c 책임. **본 turn 의 deliverable 은 method body + caller 5 + 10 unit test + Critical 6 + Blocker 2 본 cycle 내 반영까지**. cross-DB audit explicit call + 7-day SLA + invariant test fixture/assertion 실 구현은 M2-c 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2b` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2b/`. 사용자 결정 (2026-05-21): "M2-b cycle 또한 진행해주세요" → 본 cycle 진행 + "작업을 이어서 진행해주세요" → Critical/Blocker 반영 + commit/push/sync.
- Files (method body + caller + test):
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (rewrite ~780 LOC): ABC 의 `prune_fact_entries_keep_top` 추가 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper (`_get_pg_conn` + `_mirror` + 6 public method) + module singleton `_dual_write_kb` + `_BACKENDS_CACHE` process-level cache + 6 Postgres SQL 템플릿 (`_PG_PRUNE_FACT_ENTRIES` 추가 + GREATEST(weight) MySQL 정합).
  - `unit/feature-0002-agent-core/src/modules/utils.py` (+50 LOC): caller 3 위치 mirror 호출 (`_text_store_insert` line 977 + `_upsert_rag_memory_from_fact` 의 RagDocuments line 1223-1235 + RagObjects line 1310-1329).
  - `unit/feature-0002-agent-core/src/modules/knowledge.py` (+30 LOC, -20 LOC): caller 2 위치 (`_publish_fact` line 670-693 — dead try/except wrapper 제거 + `_prune_fact_entries_for_key` line 586-643 — MySQL DELETE 광역 swallow 한정 + mirror 호출 외부).
  - `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (신규 ~310 LOC): 10 unit test.
  - `unit/feature-0002-agent-core/tests/conftest.py` (신규 ~15 LOC): sys.path 통합.
  - `docs/DECISIONS.md` ADR-0021 §Consequences (+1 항목): Cross-DB audit explicit call M2-c cycle 책임 명시.
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md`: cycle 등록 + `REV-20260520-0008` + 본 entry + Summary + risk log 0번.
- Outside-voice review (Plan subagent) Critical 6 + Blocker 2 본 cycle 내 반영:
  1. **Critical (Caller pattern 통일)**: knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리 ✓
  2. **Critical (Test isolation)**: conftest.py 신규 + sys.path 통합 + dual import path 제거 ✓
  3. **Critical (Caller actual call test)**: Test 9 — `_text_store_insert` + mock cursor + spy mirror ✓
  4. **Critical (silent log verification)**: Test 10 — caplog `kb_pg_mirror: connection failed` ✓
  5. **Critical (Latency baseline)**: REPORT.md §4 risk log 0번 entry — M2-c production-like 측정 책임 ✓
  6. **Blocker (Cross-DB audit explicit call)**: ADR-0021 §Consequences M2-c 책임 명시 (ActionCode `kb.write.mirror` INSERT) ✓
  7. **Blocker (SLA 측정 도구 cycle 책임)**: `bin/kb-dual-write-verify.sh --audit-sla` M2-c 책임 명시 ✓
- 검증 (본 cycle):
  - `python3 -m py_compile kb_backend.py + knowledge.py + utils.py + test_dual_write_mirror.py + conftest.py` — PASS
  - ABC instantiation manual verify (MysqlKbBackend / PgKbBackend 6 method callable) — PASS
- Runtime 검증 deferral (M2-c 별 cycle 책임):
  - main worktree `git pull --ff-only` + `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS=<ISO>`
  - `make start` 재기동 → agent 의 fact write 시 `_DualWriteMirror` 가 양쪽 INSERT
  - `_DualWriteMirror._mirror()` 안에 cross-DB audit explicit call (M2-c 추가)
  - `bin/kb-dual-write-verify.sh --audit-sla --window-days 7` 본문 + 7-day stress run
  - test_anchor_invariant_postgres.py 의 6 시나리오 + 2 negative assertion fixture 실 구현 (S1-S6 + N1 LLM 0건 + N2 TRUNCATE)
- 사용자 결정 (2026-05-21): 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0008 [SUBAGENT:Plan-subagent]`. RBAC role `agent_kb_rw` 활성 cycle + 메모리 정책 정합. NEEDS-TWEAK + Critical 6 + Blocker 2 본 cycle 내 반영 + Nice-to-have 5건 M2-c 위임.

## CHG-20260521-0001
- Date: 2026-05-21
- TASK-Cycle: TASK-0019 (M2-a dual-write 준비, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 1차 (M2-a)** — M1 outside-voice review (`REV-20260520-0005`) 의 4 Blocker (FULLTEXT / `_ensure_pg_schema()` trigger / `has_table_privilege()` / `agent_drag` namespace) 모두 해소 + KbBackend ABC + Postgres SQL 템플릿 + dual-write verify/stress skeleton + ANCHOR §3 invariant 6 시나리오 catalog. **Outside-voice review (Plan subagent, `REV-20260520-0007`) Verdict NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영**: memory.py grants 확장 (USAGE + sequence + TRUNCATE_denied) / docker-compose memory-init postgres depends_on (required: false) / init_memory `AGENT_KB_PG_REQUIRED` 환경 분기 / FUNCTION.md §10 갱신 / .env.example 2 변수 / verify.sh --since default / REPORT.md §4 risk log 7건. **본 turn 의 deliverable 은 ABC + skeleton + Blocker 해소 + Critical/Blocker 반영까지**. 실 write path 침습은 M2-b 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2/`. 사용자 결정 (2026-05-21): "네, 다음 cycle 또한 이어서 진행해주세요" → 본 cycle 진행 + "이어서 진행해주세요" → Critical/Blocker 반영 + commit/push/sync.
- Files (신규 + 기존 보강):
  - `docs/KB_PG_DIALECT_NOTES.md` (신규, ~200 LOC): Blocker 1 — MySQL → Postgres dialect catalog. FULLTEXT `knowledge.py:1434` rewrite 3 옵션 (pg_trgm `similarity()` / tsvector / pgvector embedding `<=>`). 명명 매핑 30+ 컬럼. LC_COLLATE / IDENTITY 정책. cursor.execute(multi=True) 차이.
  - `docs/DECISIONS.md` ADR-0024 (신규, ~45 LOC): Blocker 4 — Sprint 4 namespace 격리 (별 database `agent_drag`). Alternatives 폐기 (schema 분리, 별 인스턴스, KB-DRAG schema 공유). superseded path 명시.
  - `unit/feature-0002-agent-core/src/agent_core.py:init_memory()` (+30 LOC): Blocker 2 — `_pg_available()` 게이트 하 `_ensure_pg_schema()` 자동 호출. `AGENT_KB_PG_REQUIRED` 환경 분기 (Critical #3 반영, default 0 optional / M2-b 1 fail-loud).
  - `unit/feature-0002-agent-core/src/modules/memory.py:_ensure_pg_schema()` (+45 LOC): Blocker 3 + Critical #1 — grants 검증 확장. role_exists + `has_schema_privilege('public', 'USAGE')` + 4 테이블 × SELECT + RW mutate + sequence USAGE + TRUNCATE_denied + VIEW SELECT.
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (신규, ~250 LOC): KbBackend ABC + MysqlKbBackend / PgKbBackend skeleton + Postgres SQL 템플릿 (_PG_UPSERT_TEXT / _PG_UPSERT_FACT_ENTRY / _PG_DELETE_FACT_ENTRIES / _PG_UPSERT_RAG_DOCUMENT / _PG_UPSERT_RAG_OBJECT / _PG_SET_TEXT_EMBEDDING) + `get_backends()` factory.
  - `bin/kb-dual-write-verify.sh` (신규, ~150 LOC, skeleton): 4 mode (counts / content-hash / audit-sla / all). Blocker — `--since` default 가 `.env` `KB_DUAL_WRITE_START_TS` 자동 읽기 + 7-day fallback.
  - `bin/kb-dual-write-stress.sh` (신규, ~95 LOC, skeleton): insight 3 cycle + 5 시나리오 × 5 iter. synthetic load.
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (신규, ~140 LOC): 6 scenario catalog + 2 negative assertion stub.
  - `docker-compose.yml` (+13 LOC): Critical #2 — `memory-init.depends_on` 에 `postgres: { condition: service_healthy, required: false }`. race condition mitigation.
  - `.env.example` (+13 LOC): `AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS` 2 변수 추가.
  - `unit/feature-0002-agent-core/docs/FUNCTION.md §10` (+20 LOC): Critical #4 — Schema 적용 entry point 의 자동 호출 trigger + grants_present 필드 + KbBackend ABC + invariant test catalog 반영.
  - `unit/feature-0002-agent-core/docs/REPORT.md` §1 + §4 (+~50 LOC): M2-a Summary + Blocker risk log 7건 (audit SLA / FULLTEXT 비등가 / agent_drag 잔존 / depends_on required:false / except graceful / VIEW tie-breaker / psycopg autocommit).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY}.md`: cycle 등록 + outside-voice review entry + 본 entry.
- Outside-voice review (Plan subagent) Critical 4 + Blocker 3 본 cycle 내 반영:
  1. **Critical**: memory.py grants 검증 확장 (USAGE + sequence + TRUNCATE_denied)
  2. **Critical**: docker-compose memory-init.depends_on postgres
  3. **Critical**: agent_core.py init_memory AGENT_KB_PG_REQUIRED 환경 분기
  4. **Critical**: FUNCTION.md §10 갱신
  5. **Blocker**: KB_DUAL_WRITE_START_TS .env.example 변수 + verify.sh --since default
  6. **Blocker**: AGENT_KB_PG_REQUIRED .env.example 변수
  7. **Blocker**: REPORT.md §4 risk log entry 7건
- 검증 (본 cycle):
  - `python3 -m py_compile agent_core.py + memory.py + kb_backend.py` — PASS
  - `bash -n bin/kb-dual-write-verify.sh + kb-dual-write-stress.sh + kb-pg-role-bootstrap.sh + kb-schema-compare.sh + kb-pg-healthcheck.sh + kb-measure-baseline.sh` — PASS
  - SQL 템플릿 syntax 검증은 M2-b cycle 의 실 호출 시점 (psycopg cursor.execute)
- Runtime 검증 deferral (M2-b 별 cycle 의 사용자 책임 — TASK-0017 / 0018 / 0019 통합 9 step):
  1. main worktree `git pull --ff-only`
  2. `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS=<ISO>` (M2 진입 timestamp)
  3. `make start` 재기동 → memory-init 가 fail-loud 모드 + `_ensure_pg_schema()` 자동 호출
  4. `grants_present` dict 검증 (모든 role × USAGE / SELECT / mutate / sequence / TRUNCATE_denied)
  5. `bin/kb-pg-role-bootstrap.sh --all` + `bin/kb-schema-compare.sh` PASS
  6. M2-b cycle 진입: KbBackend method body 10 구현 + `_dual_write_kb()` wrapper + caller 수정 (5 위치)
  7. `bin/kb-dual-write-verify.sh --all --since $KB_DUAL_WRITE_START_TS` PASS
  8. `bin/kb-dual-write-stress.sh` synthetic load (7-day SLA window)
  9. ANCHOR §3 invariant 6 시나리오 test PASS (LLM 호출 0건 N1 + TRUNCATE 차단 N2 negative assertion)
- 사용자 결정 (2026-05-21): 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Major 의 사용자 명시 진행 의도 표명 = 사람 confirm 충족).
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0007 [SUBAGENT:Plan-subagent]`. RBAC 동반 변경 + 메모리 정책 `feedback_outside_voice_for_rbac.md` 정합. NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영 + 7 Nice-to-have M2-b 위임.

## CHG-20260520-0005
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 — ADR renumber fixup)
- Summary: origin/main 이 본 cycle 의 1차 commit (`4bca163`) push 후 추가 발전 (TASK-0088 PR #38 머지로 ADR-0020 추가). 본 cycle 의 ADR-0023 가 numbering gap (0021/0022 미정의) 을 만들어 rebase 시 conflict 회피 + 연속성 위해 **ADR-0023 → ADR-0021 renumber**. text-level rename only (sed -i 18 references / 12 files).
- Files: `docs/DECISIONS.md` (ADR header), `unit/feature-0002-agent-core/src/modules/{db,memory}.py` (주석), `.env.example` (주석), `docker-compose.yml` (주석), `bin/kb-pg-role-bootstrap.sh` (주석 + stderr 메시지), `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (주석), `unit/feature-0002-agent-core/docs/{TASK,FUNCTION,REVIEW,MODIFY,REPORT}.md` (cross-reference).
- 검증: `git grep ADR-0023` = 0건 ✓. `git grep ADR-0021` 의 모든 reference 가 본 cycle 의 ADR.
- 사유: ADR 번호는 catalog 의 정본 — gap (0020 → 0023) 보다 연속 (0020 → 0021) 이 검색·인용 용이. semantic 변경 0건.
- Outside-voice: 본 fixup 은 text rename only — 의사결정 항목 없음. `REV-20260520-0006 [SKIPPED:renumber-only]` entry 만 추가.

## CHG-20260520-0004
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 Postgres DDL + RBAC role 신설, **Major §12.3** — 인증/인가 변경)
- Summary: §2.1 PLAN-APPROVED 의 **M1 phase Postgres DDL + RBAC role 신설 + ADR-0021** 실행. `agent_kb_schema.sql` (5 KB 테이블 + VIEW + ivfflat index + role grant block, ~241 LOC), `bin/kb-pg-role-bootstrap.sh` (4 mode + rotate-password + weak password fail-loud, ~200 LOC), `bin/kb-schema-compare.sh` (MySQL ↔ Postgres 컬럼 정합 비교, ~157 LOC), `modules/memory.py` 의 `_ensure_pg_schema()` 함수 추가 (~100 LOC, M2 dual-write 진입 entry), `docs/DECISIONS.md` ADR-0021 (2-layer hybrid: connection-level role + application-level `kb.*` 4 권한), `.env.example` 의 `AGENT_KB_PG_RW_PASSWORD` / `RO_PASSWORD` 추가. Outside-voice review (Plan subagent, `REV-20260520-0005`) NEEDS-TWEAK + 4 Critical 본 cycle 내 반영.
- Worktree: `ai/claude/0002/kb-pg-m1` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m1/`. 사용자 결정 (2026-05-20): "다음 Cycle 을 이어서 진행해주세요" (이전 turn 의 worktree 정책 지속 적용).
- Files (코드/설정 + 신규 script + ADR):
  - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규, 241 LOC): pgvector + pg_trgm extension + 4 KB 테이블 (`fact_entries` / `texts` / `rag_documents` / `rag_objects`) + VIEW (`agent_memory_facts`) + index (covering + ivfflat) + role grant `DO $$` block. dialect 변환 매핑 + Blocker B-4 결정 (`texts.embedding vector(1536)` 만, TextHash 별 단일 embedding).
  - `bin/kb-pg-role-bootstrap.sh` (신규, 200 LOC): 4 mode (`--create-db` / `--create-roles` / `--apply-schema` / `--all`) + `--rotate-password`. **Critical #1**: `change_me_*` literal fallback fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요).
  - `bin/kb-schema-compare.sh` (신규, 157 LOC): MySQL ↔ Postgres `information_schema.columns` 비교. PascalCase ↔ snake_case normalization. missing column 검출.
  - `unit/feature-0002-agent-core/src/modules/memory.py` (+100 LOC): `_ensure_pg_schema()` 함수 추가. M2 dual-write 진입 시 1회 호출. psycopg fail-soft + tables/view/extensions 검증 query.
  - `docs/DECISIONS.md` (신규 ADR-0021, ~60 LOC): KB Postgres 분리 후 RBAC catalog 재정의. 2-layer hybrid 모델. Alternatives + Consequences + 후속 액션 4 섹션.
  - `.env.example` (+11 LOC): `AGENT_KB_PG_RW_PASSWORD` + `RO_PASSWORD` 2 변수 + 주석 (outside-voice Critical #1).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + 결과 기록.
- Outside-voice review (Plan subagent) Critical 4건 본 cycle 내 반영:
  1. `.env.example` 의 RW/RO PASSWORD 변수 추가 + bootstrap fail-loud ✓
  2. `kb.write.any` → `kb.mutate.any` (catalog 명명 일관성) ✓
  3. ADR Consequences 보강 (cross-DB audit SLA ≤0.1% + password rotation backoff + `--apply-schema` warning) ✓
  4. ADR §후속 액션 보강 (dynamic grant blindspot cycle 위치 명시 + ADR-0024 후보 명시) ✓
- 검증 (본 cycle, schema 정의 + script + ADR 까지):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/memory.py` — PASS
  - `bash -n bin/kb-pg-role-bootstrap.sh` — PASS
  - `bash -n bin/kb-schema-compare.sh` — PASS
  - SQL 의 실 syntax 검증은 사용자 별 turn 의 `_ensure_pg_schema()` 호출 또는 `bin/kb-pg-role-bootstrap.sh --apply-schema` 호출 시점 (postgres 컨테이너 가동 필요)
- Runtime 검증 deferral (사용자 별 turn — TASK-0017 / 0018 통합):
  1. main worktree 에서 `git pull --ff-only`
  2. `.env` 의 `AGENT_KB_PG_*` 채움 (`HOST=postgres` / `PORT=5432` / `DB=agent_kb` / `USER=postgres` / `PASSWORD=<choose>` / `SSLMODE=prefer` + **`RW_PASSWORD=<choose>` / `RO_PASSWORD=<choose>`**)
  3. `make start` 재기동 → postgres 컨테이너 가동
  4. `bin/kb-pg-healthcheck.sh --container` PASS (TASK-0017 검증)
  5. `bin/kb-pg-role-bootstrap.sh --all` 실행 (본 cycle 검증) — DB + role + schema
  6. `bin/kb-schema-compare.sh` PASS (4 테이블 컬럼 정합)
  7. `bin/kb-pg-healthcheck.sh --extension` + `--pg-connect` PASS
  8. `.env` 의 `AGENT_KB_PG_USER=agent_kb_rw` 전환 + agent 재기동 (M2 사전)
- 사용자 결정 (2026-05-20): 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Major 사람 confirm 권장 — 사용자 "이어서 진행" 명시로 표명).
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0005 [SUBAGENT:Plan-subagent]`. NEEDS-TWEAK + 4 Critical 본 cycle 내 반영 + 4 Blocker (M2 진입 전 처리) + 2 Nice-to-have 식별.

## CHG-20260520-0003
- Date: 2026-05-20
- TASK-Cycle: TASK-0017 (M0 인프라 도입, Minor §12.3 — 비파괴 추가)
- Summary: §2.1 PLAN-APPROVED 의 **M0 phase 인프라 도입** — docker-compose 의 `postgres` 서비스 (pgvector/pgvector:pg16, standalone), `.env.example` 의 AGENT_KB_PG_* 17 변수, `requirements.txt` 의 psycopg+pgvector, `modules/config.py` + `modules/db.py` 의 `_pg_connect()` helper (fail-soft import), `bin/kb-pg-healthcheck.sh` 신규 (4 stage), `bin/kb-measure-baseline.sh` 의 `--latency` mode 추가 (M-1 deferral 보완).
- Worktree: `ai/claude/0002/kb-pg-m0` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m0/`. 사용자 결정 (2026-05-20): "다음 단계를 진행해주세요" (이전 turn 의 "다음 cycle 또한 신규 worktree에서 진행해주세요" 정책 지속 적용).
- Files (코드/설정 변경, 비파괴 추가):
  - `docker-compose.yml`: `postgres` 서비스 추가 (services 안 mysql 다음 위치). pgvector/pgvector:pg16 image, dbnet only, port `${AGENT_KB_PG_PORT:-5432}:5432`, volumes `../artifacts/postgres-data:/var/lib/postgresql/data` + `../artifacts/shared:/shared`, healthcheck `pg_isready`. **agent.depends_on 비추가** (M0 standalone, outside-voice Section F-4 권고).
  - `.env.example`: `AGENT_KB_PG_*` 17 변수 추가 (§2.1.4 전체) — connection 6 (HOST/PORT/DB/USER/PASSWORD/SSLMODE) + read backend + dual-write + embedding 5 + ANN 4. 값은 빈 string default — phase 별 점진 채움.
  - `unit/feature-0002-agent-core/src/requirements.txt`: `psycopg[binary]>=3.1` + `pgvector>=0.2.4` 추가 (4 LOC + 주석 2 LOC).
  - `unit/feature-0002-agent-core/src/modules/config.py`: 9 export (`AGENT_KB_PG_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` / `SSLMODE` / `_ENABLED` + `AGENT_KB_READ_BACKEND` + `AGENT_KB_DUAL_WRITE`) + 9 변수 정의 (`AGENT_KB_PG_*` 의 derivation, default 값 + 주석).
  - `unit/feature-0002-agent-core/src/modules/db.py`: `_pg_available()` + `_pg_connect()` 함수 추가 (~60 LOC). psycopg optional import (fail-soft — postgres 컨테이너 미가동 환경에서도 agent 정상 boot). `_pg_connect()` 가 RuntimeError 로 fail-loud — caller fallback 신호.
  - `bin/kb-pg-healthcheck.sh` (신규, 177 LOC): 4 stage check — `--container` (docker ps + healthcheck status) → `--connect` (docker exec psql SELECT 1) → `--extension` (pgvector available) → `--pg-connect` (agent 컨테이너에서 `_pg_connect()` smoke). `--all` 합본. `COMPOSE_PROJECT_NAME=repo` 강제 + main worktree `.env` fallback.
  - `bin/kb-measure-baseline.sh`: `--latency` mode 추가 (~75 LOC). 5 시나리오 (S1 단순 / S2 follow-up / S3 모호 / S4 메타탐색 / S5 복구) × LATENCY_N 회 (default 3, `--latency-n` 으로 조정). `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출 + wall-clock 측정. JSON `latency` 필드의 `deferred_to=M0` 가 `samples` 배열로 전환. emit_json 의 cycle_id 가 `TASK-0016` → `TASK-0017` 갱신.
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md`: cycle 등록 + 결과 기록 + Completion Checklist 갱신.
- 검증 (본 cycle, 코드/설정 변경만):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py` — PASS
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/db.py` — PASS
  - `bash -n bin/kb-pg-healthcheck.sh` — PASS
  - `bash -n bin/kb-measure-baseline.sh` — PASS
  - `docker compose -f docker-compose.yml config --quiet` — syntax OK (warning 은 본 worktree 의 .env 미설정 — main worktree 의 실 .env 에서는 무관)
- Runtime 검증 deferral (사용자 별 turn 진행):
  - main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 + `git pull --ff-only` + `.env` 의 AGENT_KB_PG_* 채움
  - `make start` 재기동 (postgres 컨테이너 가동)
  - `bin/kb-pg-healthcheck.sh --all` PASS 확인
  - postgres 안에서 `CREATE EXTENSION IF NOT EXISTS vector;` (M1 cycle 의 `_ensure_pg_schema()` 가 책임 — 본 cycle 안 자동화 안 함)
  - `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 + JSON artifact 갱신 (B-2 5/5 완성)
- 사용자 결정 (2026-05-20): 이전 cycle 들과 동일 패턴 — 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족 — M0 는 Minor).
- Outside-voice rationale: skipped — REVIEW.md `REV-20260520-0004 [SKIPPED:outside-voice-not-required]` 참조. 본 cycle 은 비파괴 인프라 추가만, 의사결정 항목 0건. RBAC 변경은 M1 cycle 책임 (그 시점에 outside-voice 필수).

## CHG-20260520-0002
- Date: 2026-05-20
- TASK-Cycle: TASK-0016 (M-1 baseline 측정, Minor §12.3 — read-only)
- Summary: §2.1 PLAN-APPROVED 의 **M-1 phase** 사전 baseline 측정 실행. `bin/kb-measure-baseline.sh` (read-only 측정 스크립트) 신규 + 4/5 측정 (rows / EXPLAIN / JOIN audit / RBAC audit) + JSON artifact (`artifacts/shared/kb-baseline-2026-05-20.json`) 저장. Latency baseline (5/5) 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer.
- Worktree: `ai/claude/0002/kb-pg-m-1` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-kb-pg-m-1/`. 사용자 결정 (2026-05-20): "다음 cycle 또한 신규 worktree에서 진행해주세요".
- Files:
  - `bin/kb-measure-baseline.sh` (신규) — 5 mode: `--rows` / `--explain` / `--joins` / `--rbac` / `--all`. main worktree 의 `.env` fallback + `repo-mysql-1` 직접 `docker exec` (docker compose project name 충돌 회피). 미설치 환경에서 wrapper path 자동 detect.
  - `unit/feature-0002-agent-core/docs/TASK.md` — §1.1 cycle 등록 (TASK-0016) + §1.2 cycle-specific plan + §1.3 TASK-0015 summary + §1.4 historical summary + §3 Task Queue + §4 In Progress + §5 Blocked (clear) + §6 Done + §7 Next Action + §8/§9 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md` — `REV-20260520-0003 [SKIPPED:outside-voice-not-required]` append (측정 cycle 의 의사결정 0건 + JSON artifact 의 sanity check).
  - `unit/feature-0002-agent-core/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md` — §1 Summary 의 M-1 measurement 결과 + §4 Open Issues / §7 Human Attention Needed 갱신 (M0 cycle 진입 안내 + Blocker B-1 Sprint 4 schema 확인 reminder).
- Generated artifacts (git 추적 외):
  - `artifacts/shared/kb-baseline-2026-05-20.json` — measurement 정본. M4 cutover gate (`bin/kb-cutover-readiness.sh`) 의 비교 대상.
- Measurement summary (artifact 의 핵심 필드):
  - rows: FactEntries 774 / Texts 798 / RagDocuments 831 / RagObjects 774 / Facts VIEW 774
  - joins: non_kb_to_kb 0 / kb_to_non_kb 0 (expected 0 ✓ — Open Q #9 충족)
  - rbac: kb_permissions 0 / memory_permissions 0 / agent_kb_permissions 0 / permission_definitions_total_approx 40 (outside-voice Section D 정합 — Postgres 분리 후 role 신설 필수)
  - explain: Q1 range, Q2 ref, Q3/Q4/Q5 ALL (full scan — pgvector ANN selectivity 이득 영역)
  - latency: `deferred_to=M0` (docker compose project name 충돌 회피)
- Verification (본 cycle):
  - 본 cycle 의 코드 mutation 0건 (스크립트 신규 추가만). 외부 영향 0건 (LLM 호출 없음, DB read-only).
  - `bin/kb-measure-baseline.sh` 자체 실행 검증 — `--all` 모드 → JSON 정상 parse + 5 mode 개별 실행 PASS.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출.
- 사용자 결정 (2026-05-20): 즉시 자동 commit + push + main ff-merge — 전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족 (M-1 은 Minor).

## CHG-20260520-0001
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3)
- Summary: KB 정본 5종 (`AgentMemoryFacts` view + `FactEntries` + `Texts` + `RagDocuments` + `RagObjects`) MySQL → Postgres pgvector 마이그레이션 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성. 본 cycle 자체는 plan-작성 cycle 이며 코드·schema·데이터 변경 없음. doc 4종 (TASK, REVIEW, MODIFY, REPORT) 만 갱신.
- Worktree: `ai/claude/0002/pgvector-migration-plan` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-pgvector-migration-plan/`. 사용자 결정: "현재 세션에서 신규 Worktree를 생성 및 진입하되, 해당 worktree에서 plan 작성 또한 진행합니다."
- Files:
  - `unit/feature-0002-agent-core/docs/TASK.md`: §1.1 cycle 등록, §1.2 본 plan-작성 plan, §2.1 신규 마이그레이션 plan (M0~M5 phase + 결정 매트릭스 + 영향 파일 + 검증 체크리스트 + Open Questions), §2.2 기존 plan archive, §3 Task Queue TASK-0015 추가, §4 In Progress, §5 Blocked, §6 Done, §7 Next Action, §8 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md`: `REV-20260520-0001` append (3-D 결정 + trade-off + alternatives + outside-voice 호출 사유).
  - `unit/feature-0002-agent-core/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md`: §4 Open Issues + §7 Human Attention Needed 에 plan-review 상태 표면화 + cutover 시 사람 confirm 필요 항목 명시.
- Plan 의 Execute 영향 (참고 — 본 cycle 에서는 변경 없음, 별 cycle 진행):
  - Source: `modules/{memory,knowledge,insight,schema,planner,utils}.py`, `modules/db.py`, `agent_core.py` (7,500+ LOC raw SQL dialect 변환)
  - Infra: `docker-compose.yml` (postgres 서비스 추가), `.env.example` (신규 `AGENT_KB_PG_*` / `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` / `AGENT_KB_EMBEDDING_*` / `AGENT_KB_ANN_*`)
  - Policy (META path): `AGENTS.md §11.3·§14.1·§15.6·§15.7`, `FUNCTION.md §10`, `INSIGHTS.md §4`, `ANCHOR.md §1·§3`, `docs/{DECISIONS,CONVENTIONS,SECURITY,STATUS,CODEBASE_MAP}.md`
  - Tests: `tests/test_pgvector_migration.py` (신규), `tests/test_compose_system_prompt.py` (회귀)
  - Tooling: `bin/{kb-backfill,kb-dual-write-verify,kb-cutover-readiness,kb-schema-compare,kb-pg-healthcheck}.sh` (신규), `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규)
- Verification (본 cycle):
  - 본 cycle 의 deliverable 은 doc 변경만. 코드 검증 불요.
  - outside-voice review (Plan subagent, Software architect agent) ✓ 완료 — `REV-20260520-0002`. Verdict **NEEDS-TWEAK** + 11 Blocker + 5 Nice-to-have. §2.1 본문 + §2.1.11 추적 표에 반영 완료.
  - 사용자 PLAN-APPROVED 마커 ✓ 부여 (2026-05-20 by ms.mckim.gpt@gmail.com) — TASK.md §2.1 직후의 `<!-- PLAN-APPROVED -->` 마커 + §1.2 status `plan-approved` + §8 Completion Checklist 갱신.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출 (PLAN-APPROVED 직후 자동 진행).
  - 사용자 결정 (2026-05-20): "즉시 자동 마커 추가 + commit/push" — verify-completion PASS 시 본 cycle commit + branch push + main ff-merge 자동 진행 (전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족).

## CHG-20260515-0003
- Date: 2026-05-15
- Summary: TASK-0014 (REQ-20260515-0003) Account scope 시스템 프롬프트도 `전 Product 공통 + Product 전용` 누적 방식으로 정정하고, 최종 user request 가 Product/Role/Account 지침 뒤에 보존되는 것을 테스트로 고정.
- Files:
  - `src/agent_core.py`: Account prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Account×Product 전용 지침 뒤 순서로 변경. `_fetch()`는 특정 Product 조회에서 miss 가 나면 공통 fallback 을 반환하지 않도록 정정해 중복 누적을 방지.
  - `tests/test_compose_system_prompt.py`: Product → Role → Account 순서, Account common+specific 누적, 최종 user request 메시지 보존 테스트 추가.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`

## CHG-20260515-0002
- Date: 2026-05-15
- Summary: TASK-0013 (REQ-20260515-0002) Role scope 시스템 프롬프트의 "전 Product 공통" 지침을 fallback 이 아니라 누적 적용으로 전환.
- Files:
  - `src/agent_core.py`: Role prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Role×Product 전용 지침 뒤 순서로 변경. auto 모드는 Product 전용 지침을 건너뛰고 공통 지침만 사용.
  - `tests/test_compose_system_prompt.py`: fake connection 기반으로 pinned 누적 / auto 공통-only 동작 검증.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
  - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 직접 조회로 `PRODUCT CONTEXT` 뒤 `ROLE GUIDANCE` 안에 `### 전 Product 공통`이 포함됨을 확인.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: agent 코어 소스와 Dockerfile을 기능 단위 구조로 이관
- Files: src/agent_cli.py, src/agent_core.py, src/modules/*, src/Dockerfile
- Notes: Web UI는 별도 feature에서 관리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 워크스테이션 Local LLM 지연 완화를 위해 역할별 모델 바인딩과 검증 문서를 정합화
- Files: src/modules/config.py, src/modules/llm.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../feature-0003-agent-web-ui/docs/TEST.md
- Notes: 현재 repo `.env` 의 alias/timeout/worker 값은 로컬 소비자 설정이라 Git 추적 대상이 아니다. 외부 provider 프로필 조정과 direct bench 기록은 `/root/download/docker/local_llm` 저장소에서 별도로 관리한다.

## CHG-20260421-0003
- Date: 2026-04-21
- Summary: insight-worker 누락 복구 경로와 일자별 로그 보관 구조를 추가
- Files: src/modules/insight.py, src/modules/utils.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../../../../AGENTS.md
- Notes: 기존 더티 워크트리는 보존하고 별도 worktree/브랜치에서 구현했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 완전성 검증을 통과할 때만 fingerprint/refresh 성공 마커를 갱신한다.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0012 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — agent-core 책임 범위, web-ui coupling 인정, modules/ 서브디렉토리 책임 구분, insight-worker 복구 순서 시나리오.
- Files: unit/feature-0002-agent-core/docs/ANCHOR.md, unit/feature-0002-agent-core/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. insight-worker 복구 순서를 바꾸려는 향후 요청은 §3과 충돌 감지 대상 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.

## CHG-20260527-AR-M1
- Date: 2026-05-27
- Related Requirement: TASK-0112 (REQ-20260527-AR-M1, Major §12.3 — DDL + RBAC)
- Summary: Phase 2 AR-M1: agent_runtime 6 테이블 DDL 정본 Postgres 적용 + ADR-0027 + schema compare 검증 도구
- Files: unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql (신규), bin/agent-runtime-schema-compare.sh (신규), docs/DECISIONS.md (ADR-0027 추가), unit/feature-0002-agent-core/docs/TASK.md, unit/feature-0002-agent-core/docs/MODIFY.md, unit/feature-0002-agent-core/docs/REVIEW.md, unit/feature-0002-agent-core/docs/REPORT.md
- Notes: DDL 을 Postgres `agent_kb.agent_runtime` schema 에 직접 apply (6 테이블 CREATE 완료). outside-voice review PASS (REV-20260527-0003) — C1(kv FK 의도적 생략 주석) + C2(meta_json jsonb) + N5(CREATE SCHEMA 방어 guard) 반영. kv.conversation_id='__global__' sentinel (1588건) 로 인해 FK 의도적 생략 — ADR-0027에 명문화. search_path 전역 변경 없음 — AR-M2 SQL은 schema-qualified 명시 필수.

## CHG-20260527-AR-M2-a
- Date: 2026-05-27
- Related Requirement: TASK-0113 (REQ-20260527-AR-M2-a, Minor §12.3 — ABC + skeleton)
- Summary: Phase 2 AR-M2-a: RuntimeBackend ABC + skeleton + dual-write mirror entry point + test catalog
- Files: unit/feature-0002-agent-core/src/modules/runtime_backend.py (신규), unit/feature-0002-agent-core/tests/test_anchor_invariant_runtime.py (신규), unit/feature-0002-agent-core/docs/TASK.md, unit/feature-0002-agent-core/docs/MODIFY.md, unit/feature-0002-agent-core/docs/REVIEW.md, unit/feature-0002-agent-core/docs/REPORT.md, unit/feature-0002-agent-core/docs/FUNCTION.md
- Notes: 비파괴 신규 파일 추가. AGENT_RUNTIME_DUAL_WRITE 기본값 False — 기존 MySQL callsite 무영향. MysqlRuntimeBackend / PgRuntimeBackend 모두 NotImplementedError skeleton (M2-b에서 구현 예정). outside-voice 생략 (RBAC 무변경, code mutation 0건, caller 수정 0건).

## CHG-20260527-AR-M4-read
- Date: 2026-05-27
- Related Requirement: AR-M4-read — PgRuntimeBackend read 메서드 구현 (MySQL fallback 오류 해소)
- Summary: `PgRuntimeBackend` 에 10개 read 메서드 추가. SQL 상수(`_PG_LOAD_KV` 등)는 이미 M4 절에 정의되어 있었으나 메서드 구현 누락. `_read_runtime_pg()` 가 `method is None` 경로로 None 반환 → MySQL fallback → `agentmemorykv` 없음 오류(1146) 연쇄. 메서드 구현으로 PG 경로 정상화.
- Files:
  - feature-0002-agent-core/src/modules/runtime_backend.py (PgRuntimeBackend 에 read 메서드 10개 추가)
- Notes:
  - 추가 메서드: load_kv / load_kv_all / load_kv_by_key / load_kv_by_key_value / load_summary / load_messages / load_steps / list_conversations / load_core_messages / get_conv_messages_full.
  - 기존 write 메서드 (save_*) 무변경. SQL 상수 (lines 134~210) 그대로 재사용.
  - `load_summary()` : None 반환 시 caller `load_memory_context()` 가 MySQL fallback 으로 진입했던 경로 → 이제 `""` 아닌 `None` (row 없음)을 정상 반환 (MySQL parity).
  - web + insight-worker 재빌드 필요.
- Rollback: PgRuntimeBackend 의 read 메서드 10개 제거 (write 메서드 영향 없음).

## CHG-20260527-FULL-TEST
- Date: 2026-05-27
- Related Requirement: TASK-0120 (풀 테스트 + 버그 제거)
- Summary: 서비스 전체 풀 테스트 실행 — 46개 실패 원인 분석 후 전부 수정
- Files: unit/feature-0002-agent-core/src/agent_core.py, unit/feature-0002-agent-core/src/modules/llm.py, unit/feature-0002-agent-core/src/modules/kb_backend.py, unit/feature-0002-agent-core/src/modules/runtime_backend.py, unit/feature-0002-agent-core/src/modules/utils.py, unit/feature-0002-agent-core/src/modules/memory.py, unit/feature-0002-agent-core/src/scripts/kb_backfill.py
- Notes: (1) Python 3.12 SyntaxWarning 2건 수정 (agent_core.py:95, llm.py:412 — 백틱 앞 \\ 이스케이프 제거). (2) kb_backfill.py: texts TABLE_MAPPING id_col="Id" + select_cols에 "Id" 추가 + _insert_pg_batch 항상 row[1:] 사용. (3) kb_backend.py: _DualWriteMirror 클래스 신규 (DEPRECATION NOTICE / M5 / ADR-0025 포함, 6 mirror method) + _dual_write_kb 모듈 인스턴스. (4) runtime_backend.py: AGENT_RUNTIME_DUAL_WRITE env var + RuntimeBackend ABC (6 abstract method) + MysqlRuntimeBackend (NotImplementedError skeleton) + PgRuntimeBackend 10 read method + _dual_write_runtime_mirror 함수. (5) utils.py _text_store_insert + memory.py save_memory_kv caller 연동. pytest 146/148 PASS (2 SKIP, 0 FAIL).

## CHG-20260527-CONV-DELETE-PG
- Date: 2026-05-27
- Related Requirement: TASK-0121 (delete_conversation 500 오류 수정)
- Summary: `delete_conversation` 에 `_pg_delete_conversation()` PG 경로 추가. AR-M5에서 MySQL agent_runtime 6개 테이블 DROP 후 MySQL DELETE 실패 → 500 오류 발생. PG에서 `agent_runtime.kv` 수동 삭제 + `agent_runtime.core_conversations` DELETE (CASCADE: core_messages, messages, steps, summary) + `public.fact_entries/rag_documents/rag_objects` 삭제. MySQL DELETE 구문은 try/except로 보호(테이블 없어도 오류 미전파).
- Files:
  - feature-0002-agent-core/src/modules/memory.py (_pg_delete_conversation 헬퍼 신규 + delete_conversation MySQL 구문 try/except 보호)
- Notes:
  - `_get_pg_runtime_conn()` 재사용 (runtime_backend 패턴 일치).
  - PG 단일 connection으로 agent_runtime + public schema 모두 처리 (같은 agent_kb DB).
  - ON DELETE CASCADE: core_conversations 삭제 시 core_messages/messages/steps/summary 자동 삭제.
  - kv는 FK CASCADE 제외 → 수동 DELETE FROM agent_runtime.kv.
- Rollback: _pg_delete_conversation 헬퍼 제거 + delete_conversation 원복.

## CHG-20260527-CONV-DELETE-FIX
- Date: 2026-05-27
- Related Requirement: TASK-0121 (**Critical §12.3** — AR-M5 PG cutover 후 `delete_conversation` 500 fix)
- Summary: `delete_conversation` 이 MySQL agent_runtime 테이블(AR-M5 에서 DROP됨)에 직접 DELETE 하던 경로를 PG로 전환. `_pg_delete_conversation()` 신규 — agent_runtime.kv (수동), agent_runtime.core_conversations (CASCADE: messages/steps/summary/core_messages), public.fact_entries, public.rag_documents, public.rag_objects 삭제. MySQL DELETE 구문은 try/except 보호로 유지(호환성).
- Files: unit/feature-0002-agent-core/src/modules/memory.py
- Rollback: `_pg_delete_conversation` 호출 제거 + MySQL DELETE 구문 try/except 제거.

## CHG-20260609-PREVIEW-CSV-MATCH
- Date: 2026-06-09
- Related Requirement: TASK-0174 ("전체 N행 미리보기" 링크가 다른 쿼리 CSV 로딩 — #118 후속)
- Summary: `_collapse_large_tables` 가 답변 속 대형 표를 csv_paths 에 **위치 인덱스**로 1:1 매칭하던 것을 값 기반 매칭으로 교체. csv_paths 에는 표로 렌더 안 된 보조 쿼리(MIN/MAX 등) 결과 CSV 까지 실행 순서로 섞여 있어, 첫 대형 표에 MIN/MAX CSV(2열 1행)가 붙어 "전체 15행 미리보기" 가 1행 결과를 로드. → 표 본문 셀의 식별 값 토큰(콤마제거 후 ≥3자리 숫자·라벨)과 각 CSV 데이터 값 토큰 overlap 최대(≥1)로 매칭, 값으로 확정 못 하면 컬럼 수 일치 CSV 로 폴백, 형태 불일치 보조쿼리는 어느 경로로도 배제.
- Files:
  - unit/feature-0002-agent-core/src/agent_core.py (_collapse_large_tables 재작성 + _distinctive_tokens/_md_table_body_cells/_md_table_col_count/_csv_signatures/_match_csv_for_table 신규, render.read_csv_preview import 추가)
  - unit/feature-0002-agent-core/tests/test_collapse_table_csv_match.py (신규 회귀 4종)
- Notes:
  - §18.8 SUBAGENT 패널(REV-20260609-0173) MAJOR 2건 반영: (1) 측정값(%·소수)뿐인 표는 식별 토큰이 없어 링크 소실 → 컬럼 수 폴백 추가, (2) JS 가드 단일토큰 우연 오탐 → previewTokens≥2 임계.
  - read_csv_preview 는 header+50행만 읽어 대형 CSV unbounded read 없음. None-safety: 읽기 실패=(None,0) → 매칭 제외.
- Rollback: _collapse_large_tables 및 헬퍼 5종 제거 + 위치-인덱스 버전 원복.

## CHG-20260609-TASK0174-CLOSE
- Date: 2026-06-09
- Related Requirement: TASK-0174 (cycle closure — 배포·라이브 검증 완료 기록)
- Summary: TASK-0174 (미리보기 링크 값매칭 수정, CHG-20260609-PREVIEW-CSV-MATCH) 의 cycle 마감 — TASK.md 마지막 체크박스를 [x] 로 갱신(main 2b4da2a ff-merge·재배포·healthz 일치·PB-0008 라이브 무회귀 반영). 코드 변경 없음(문서 한정).
- Files:
  - unit/feature-0002-agent-core/docs/TASK.md (TASK-0174 verify/배포/검증 체크박스 완료 표기)
- Rollback: 체크박스 [x]→[ ] 환원.

## CHG-20260610-MULTI-DATASOURCE-DESIGN
- Date: 2026-06-10
- Related Requirement: TASK-0182 (REQ-20260610-0182, Critical §12.3 — design-only)
- Summary: 멀티 datasource(MySQL·MSSQL) 데이터평면 **설계 문서만** 산출(구현·코드 mutation 0). 사용자 질문(단일 MySQL→여러 엔진 DB 가능?)의 타당성·범위를 AskUserQuestion 으로 규명(범위=멀티 datasource 동시, 엔진=MySQL·MSSQL) 후, "단일 MySQL" 가정이 박힌 3계층(드라이버/설정/방언)을 규명하고 datasource 레지스트리·드라이버 디스패치·Dialect 인터페이스·보안게이트 멀티방언·LLM grounding·insight per-datasource·RBAC/시크릿·P0~P6 롤아웃을 설계. ADR-CORE-0002(A 네이티브 dialect-adapter 채택) 기록. outside-voice 적대적 설계 리뷰(REV-20260610-0182, SUBAGENT, NEEDS-TWEAK, BLOCKER 3+MAJOR 4) 전 발견을 DESIGN 문서에 design-fold. 구현 이월(자체 다중 cycle + plan-eng-review + RBAC outside-voice).
- Files:
  - unit/feature-0002-agent-core/docs/DESIGN-multi-datasource.md (신규 — 설계 정본)
  - unit/feature-0002-agent-core/docs/DECISIONS.md (ADR-CORE-0002 append)
  - unit/feature-0002-agent-core/docs/REVIEW.md (REV-20260610-0182 append)
  - unit/feature-0002-agent-core/docs/REPORT.md (2026-06-10 summary append)
  - unit/feature-0002-agent-core/docs/TASK.md (TASK-0182 cycle + current status)
  - docs/STATUS.md (TASK-0182 프로젝트 현황 entry)
- Rollback: 위 문서 변경 환원(코드·런타임 영향 0 — 문서만).

## CHG-20260610-MULTI-DATASOURCE-ENG-REVIEW
- Date: 2026-06-10
- Related Requirement: TASK-0183 (REQ-20260610-0183, Critical §12.3 — design-only)
- Summary: TASK-0182 설계의 2차 검토(`/plan-eng-review` 엔지니어링 매니저 + **Codex cross-model outside voice**) + 발견 design-fold. Codex Verdict REJECT(BLOCKER 4+MAJOR 5). **보안결함 정정(Codex-2)**: §4 의 `db_datareader+DENY` 는 allowlist 와 양립 불가(DB 전체 읽기) → datasource 별 전용 role 에 허용 view/object 만 GRANT SELECT 로 본문 수정. AST 추출 무자격/catalog 보강(Codex-1), insight fact 스코프 교차노출(Codex-3), 보안경계 P1 전진(Codex-4), confirm_heavy/fetchall(Codex-6), AST 재직렬화(Codex-5), pool session reset(Codex-7), scope 정직성(Codex-8). §10 신설 + GSTACK REVIEW REPORT. 코드 mutation 0.
- Files:
  - unit/feature-0002-agent-core/docs/DESIGN-multi-datasource.md (§1·§3.2·§3.3·§3.4·§3.6·§4 정정 + §10 + GSTACK REVIEW REPORT)
  - unit/feature-0002-agent-core/docs/REVIEW.md (REV-20260610-0183 append)
  - unit/feature-0002-agent-core/docs/REPORT.md (2026-06-10 TASK-0183 summary append)
  - unit/feature-0002-agent-core/docs/TASK.md (TASK-0183 cycle + current status)
  - docs/STATUS.md (TASK-0183 프로젝트 현황 entry)
- Rollback: 위 문서 변경 환원(코드·런타임 영향 0 — 문서만). 단 §4 db_datareader 정정은 보안 정합성 수정이라 환원 비권장.

## CHG-20260610-MULTI-DATASOURCE-DECISIONS
- Date: 2026-06-10
- Related Requirement: TASK-0185 (REQ-20260610-0185, design-only)
- Summary: TASK-0183 plan-eng-review/Codex 가 남긴 롤아웃 시퀀싱 미해결 결정 3건(§4 Q6/Q7/Q8)을 사용자 결정으로 확정·기록. (Q6/Q8) multi-MySQL 먼저 — Stage 1(P1~P3) MySQL 전용, MSSQL 은 Stage 2(P4~P7, RBAC outside-voice 재게이트). (Q7) 보안경계 연결과 동시(security-first) — datasource RBAC+allowlist+RO 자격증명이 P1 에. ADR-CORE-0003 기록 + DESIGN §5 Stage 1/2 재구성. 코드 mutation 0.
- Files:
  - unit/feature-0002-agent-core/docs/DESIGN-multi-datasource.md (§4 Q6/Q7/Q8 resolved + §5 Stage 1/2 재구성 + §10 UNRESOLVED/VERDICT 갱신)
  - unit/feature-0002-agent-core/docs/DECISIONS.md (ADR-CORE-0003 append)
  - unit/feature-0002-agent-core/docs/REVIEW.md (REV-20260610-0185 append)
  - unit/feature-0002-agent-core/docs/REPORT.md (2026-06-10 TASK-0185 summary append)
  - unit/feature-0002-agent-core/docs/TASK.md (TASK-0185 cycle + current status)
  - docs/STATUS.md (TASK-0185 프로젝트 현황 entry)
- Rollback: 위 문서 변경 환원(코드·런타임 영향 0 — 문서만).

## CHG-20260610-MULTI-DATASOURCE-P1
- Date: 2026-06-10
- Related Requirement: TASK-0187 (REQ-20260610-0187, Critical §12.3 — 멀티 datasource P1)
- Summary: ADR-CORE-0003 Stage 1 첫 구현 — assistant 가 product 별 다른 MySQL datasource 분석. flag `AGENT_MULTI_DATASOURCE_ENABLED` 기본 OFF → 기존 단일 MySQL 동작 0 변경. 기존 `WebProducts` 에 `DatasourceKey` 바인딩으로 product RBAC·allowlist 재사용(별도 테이블·PG 마이그레이션 0). 좌표/비밀번호는 `.env` named credential 만(DB/payload 비저장). outside-voice 보안 리뷰(REV-20260610-0187) M-1(default_db allowlist 우회→database=None)·M-2(미등록키 fail-open→fail-closed)·N-2(DS_USER root 폴백 금지) 흡수. make test 297 passed/회귀 0.
- Files:
  - unit/feature-0002-agent-core/src/modules/config.py (DATASOURCES 파싱·flag·datasource_public·__all__)
  - unit/feature-0002-agent-core/src/modules/db.py (connect/connect_with_retry datasource param)
  - unit/feature-0002-agent-core/src/agent_core.py (_resolve_product_datasource + DatasourceResolutionError + 연결 site)
  - unit/feature-0003-agent-web-ui/src/app.py (WebProducts.DatasourceKey ALTER + admin_list_datasources/admin_set_product_datasource)
  - unit/feature-0002-agent-core/tests/test_multi_datasource.py (신규 15)
  - .env.example / .env.mysql.example (멀티 datasource 변수)
  - unit/feature-0002-agent-core/docs/{DESIGN-multi-datasource,FUNCTION,REVIEW,REPORT,TASK}.md, docs/STATUS.md
- Rollback: flag 기본 OFF 라 배포 자체로 동작 무변경(shadow). 코드 환원 시 db.connect datasource 분기·agent_core resolver·web 엔드포인트·WebProducts.DatasourceKey 제거(컬럼은 비파괴 보존 가능).

## CHG-20260610-MULTI-DATASOURCE-P2
- Date: 2026-06-10
- Related Requirement: TASK-0190 (REQ-20260610-0190, Major §12.3 — 멀티 datasource P2 Web UI)
- Summary: P1 의 admin datasource API 를 관리 콘솔 UI 로 노출 + 연결테스트 엔드포인트 + 대화 datasource 라벨. `db.probe_datasource`(flag 무관·errno-only 비유출) + `POST /api/admin/datasources/{key}/test`(console.access, 등록 키만→SSRF 불가) + `_list_products` datasource_key 노출. admin.js datasource select·연결테스트(console.manage), app.js product 배지. outside-voice 보안 리뷰 PASS-WITH-NITS BLOCKER 0(REV-20260610-0190). make test 302 passed/회귀 0.
- Files:
  - unit/feature-0002-agent-core/src/modules/db.py (probe_datasource + __all__)
  - unit/feature-0003-agent-web-ui/src/app.py (admin_test_datasource 엔드포인트 + _list_products datasource_key)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (loadAdminData datasources + renderProductDetail datasource UI + adminState)
  - unit/feature-0003-agent-web-ui/src/static/app.js (buildProductDropupItem datasource 배지)
  - unit/feature-0003-agent-web-ui/src/static/{admin.html,index.html} (캐시버스터), styles.css (ds-test·배지 클래스)
  - unit/feature-0002-agent-core/tests/test_multi_datasource.py (신규 probe 2)
  - unit/feature-0002-agent-core/docs/{FUNCTION,REVIEW,REPORT,TASK}.md, docs/STATUS.md
- Rollback: UI 비파괴(추가만). 코드 환원 시 probe·test 엔드포인트·admin.js datasource 섹션·app.js 배지 제거. flag OFF 라 런타임 영향 0.

## CHG-20260610-MULTI-DATASOURCE-P3
- Date: 2026-06-10
- Related Requirement: TASK-0191 (REQ-20260610-0191, Major §12.3 — 멀티 datasource P3 insight per-datasource)
- Summary: insight fact 키를 datasource 차원으로 분리(Codex-3 grounding 교차노출 차단) + worker datasource 순회. config 에 ContextVar+ds_fact_key/like/strip/scope_name 헬퍼(write·read-back·grounding 3자 정합 단일 소유 → livelock 방지). insight.py 키빌드 18곳 치환+순회(연결실패 격리·scan_report 누적). agent_core grounding ds 필터(not_like + set_active_datasource). outside-voice SHIP-ABLE(REV-20260610-0191), MAJOR(scan_report)·M2(MySQL fallback 가드) 흡수. flag OFF=무접두 동작 0 변경. make test 307 passed/회귀 0.
- Files:
  - unit/feature-0002-agent-core/src/modules/config.py (ds 키 헬퍼 + ContextVar + __all__)
  - unit/feature-0002-agent-core/src/modules/insight.py (키빌드 ds_fact_key + run_insight_cycle datasource 순회 + 스캔KV ds_scope_name + scan_report 누적)
  - unit/feature-0002-agent-core/src/modules/schema.py (키빌드 ds_fact_key 2곳)
  - unit/feature-0002-agent-core/src/agent_core.py (_global_insight_rows_pg not_like + _load_schema_list/_load_relevant_table_insights ds 필터 + grounding set_active_datasource + M2 가드)
  - unit/feature-0002-agent-core/tests/test_multi_datasource.py (신규 P3 4) + tests/test_db_query_ux.py (mock 시그니처 +not_like_pattern)
  - unit/feature-0002-agent-core/docs/{FUNCTION,REVIEW,REPORT,TASK}.md, docs/STATUS.md
- Rollback: flag OFF 라 런타임 영향 0(무접두 키=기존). **주의**: flag ON 운영 중 환원 시 ds-스코프 fact 키가 무접두 read-back 과 불일치 → 1회 재생성(livelock 아님).

## CHG-20260610-MULTI-DATASOURCE-P4-MSSQL
- Date: 2026-06-10
- Related Requirement: TASK-0192 (REQ-20260610-0192, Major §12.3 — 멀티 datasource Stage 2 P4 MSSQL 드라이버)
- Summary: engine='mssql' datasource 연결 인프라. pymssql 드라이버 + db.connect engine 디스패치 + 크로스엔진 결과 수집. 방언/보안은 P5/P6 이월. flag OFF shadow. make test 312 passed/회귀 0, pymssql-2.3.13 컨테이너 설치 확인.
- Files:
  - unit/feature-0002-agent-core/src/requirements.txt (pymssql>=2.2.0 + sqlglot <28 pin)
  - unit/feature-0002-agent-core/src/modules/db.py (_pymssql import + _connect_mssql + connect() engine 디스패치 + _collect_cursor_result description + probe engine 분기)
  - unit/feature-0002-agent-core/tests/test_multi_datasource.py (신규 P4 5)
  - unit/feature-0002-agent-core/docs/{FUNCTION,REVIEW,REPORT,TASK}.md, docs/STATUS.md
- Rollback: flag OFF 라 런타임 영향 0. 코드 환원 시 pymssql 의존성·engine 디스패치 제거. `_collect_cursor_result` description 전환은 mysql 등가라 환원 불요(회귀 0).

## CHG-20260610-MULTI-DATASOURCE-P5-DIALECT
- Date: 2026-06-10
- Related Requirement: TASK-0193 (REQ-20260610-0193, Major §12.3 — 멀티 datasource Stage 2 P5 Dialect)
- Summary: tools.py introspection/sample SQL 을 engine 별 dialect 로 추상화. `modules/dialects.py`(MySQLDialect 골든 그대로 + MSSQLDialect 동일 컬럼순서 T-SQL). tools.py 8사이트 치환. config 엔진 ContextVar + agent_core run-wide 설정(run_agent finally 해제). outside-voice SHIP-able(REV-20260610-0193), MAJOR M1(ContextVar 예외안전) 흡수. MySQL 골든 회귀 0. **보안 게이트 MySQL 방언 — P6 전 MSSQL 활성화 금지.**
- Files:
  - unit/feature-0002-agent-core/src/modules/dialects.py (신규)
  - unit/feature-0002-agent-core/src/modules/tools.py (8 SQL 사이트 → _dialects.active())
  - unit/feature-0002-agent-core/src/modules/config.py (_ACTIVE_DATASOURCE_ENGINE + set_active_datasource engine 인자 + __all__)
  - unit/feature-0002-agent-core/src/agent_core.py (run-wide engine 설정 + run_agent finally 해제[M1])
  - unit/feature-0002-agent-core/tests/test_multi_datasource.py (신규 P5 6)
  - unit/feature-0002-agent-core/docs/{FUNCTION,REVIEW,REPORT,TASK}.md, docs/STATUS.md
- Rollback: MySQL 골든이라 환원 시 dialect → inline SQL 복귀(기능 동일). flag OFF shadow.

## CHG-20260615-0256
- Date: 2026-06-15 (TASK-0256)
- Scope: agent-core SYSTEM_PROMPT — 답변 포맷 지침 1개 섹션 추가. RBAC/스키마/엔드포인트/시크릿 0.
- 변경: agent_core.py SYSTEM_PROMPT 의 OUTPUT 섹션 뒤 "SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK" 추가 — 첨부/쿼리 리뷰·편집 시 변경을 ```diff 블록(+/- 라인)으로 제시, 신규 SQL 작성은 ```sql 유지. compose_system_prompt 의 base 합성에 반영(상수=seed/fallback, 라이브 truth=WebSystemPrompts global row).
- 검증: test_compose_system_prompt 4 passed(```diff·DIFF BLOCK·OUTPUT 이후 순서).
- Files: src/agent_core.py, tests/test_compose_system_prompt.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: SYSTEM_PROMPT 섹션 제거 + 라이브 global row 백업 복원(기능 동일, diff 미지시).
- Deploy: ask-worker 재빌드 + 라이브 WebSystemPrompts global row 갱신(백업 보관).

## CHG-20260615-0256e
- Date: 2026-06-15 (TASK-0256e)
- Scope: agent-core 첨부 컨텍스트 주입 — 줄번호 + diff 헌크 지시. RBAC/스키마/엔드포인트/SQL추출 0.
- 변경: agent_core.py 신규 `_number_file_lines`(첨부 텍스트 각 줄 `<N>→` 줄번호 prefix, prompt 사본만) + `_build_attachment_context_section` 본문 주입에 적용 + "LINE NUMBERS & DIFFS" instruction(실제 줄번호로 unified-diff 헌크 헤더 작성·prefix 코드 미포함). 웹 렌더러(buildDiffRows)는 이미 `@@` 파싱 → 무변경.
- 검증: test_attachment_line_numbers 5 passed + 렌더 폐루프 node(`@@ -49` → 49/50/51) + py_compile. make test.
- Files: src/agent_core.py, tests/test_attachment_line_numbers.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `_number_file_lines` 호출/instruction 제거(raw 주입 복귀, 줄번호 1부터).
- Deploy: ask-worker 재빌드(agent_core baked). web/live-row 무관(SYSTEM_PROMPT·렌더 무변경).

## CHG-20260616-0291
- Date: 2026-06-16 (TASK-0284, **Critical §12.3** — 첨부 3개 이슈, feature-0003 주관). agent-core 측 변경.
- Scope: agent_core 첨부 LLM 컨텍스트 주입 스코프(AccountId → ConversationId) + assistant 의 첨부 파일명 지칭. RBAC/스키마/엔드포인트/SQL추출 0.
- 변경: `_build_attachment_context_section` 에 `conversation_id` 인자 추가 + PG/MySQL WHERE 를 conversation 우선 스코프(account 폴백, `_scope_by_conv`)로 — 대화 접근권은 caller(app.py ask owner 게이트)가 보장. `compose_system_prompt`/`_run_agent_core`(2610 호출부) conversation_id 전파. 첨부 포맷 파일명 우선(목록 `- file "..." (attachment_id=..)`, csv/xlsx sandbox 라벨 `file "..."`) + ATTACHED FILES 섹션 "REFER TO ATTACHMENTS BY FILENAME" 지침.
- 검증: test_attachment_idor.py +4(conversation 스코프·account 폴백·파일명 우선, 기존 IDOR 5 무회귀) + make test 전체 회귀 0 + py_compile. 적대 보안 리뷰 REV-20260616-0291 SHIP-WITH-FIXES.
- Files: src/agent_core.py, tests/test_attachment_idor.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: 스코프를 AccountId 로 되돌림 + 포맷 복원.
- Deploy: ask-worker 재빌드(agent_core baked). web 도 동일 변경 포함(feature-0003 app.py 호출부).

## CHG-20260616-0302
- TASK-0289 — 수행시간 end-to-end 집계 + 내부 동작(activity) step + 큐 대기 단축 (agent-core 면, Major §12.3).
- 근본원인: 표시 `duration_ms` 가 `run_start`(초기화 이후) 기준 → LLM 루프만 집계. step 은 tool 만. worker 유휴 폴링 tick 1~2s.
- 변경:
  - (P1) `_compute_duration_breakdown(queued_ms, agent_entry_perf, run_start, now_perf)` → `{queued/init/inference/total}`. `_run_agent_core` 진입 `agent_entry_perf=perf_counter()` + `run_agent`/`_run_agent_core` 에 `queued_ms_seed` 파라미터. 표시·KV·meta `duration_ms`=total, meta `duration_breakdown` 동봉.
  - (P1) worker(modules/ask.py)가 `ask_jobs.claim_ask_job` created_at(RETURNING `j.created_at` 추가 + dict len-guard)로 큐 대기 산출 → `queued_ms_seed`.
  - (P2) `_emit_activity` nested helper(맥락 로드/분석 준비/추론 라운드/결과 정리) `action='activity'`·`tool=''` `save_memory_step` + `emit_index` 통합 step_index(tool step 도 emit_index 사용, `_writes_allowed`/예외 안전).
  - (P4) config `AGENT_ASK_WORKER_IDLE_POLL_SEC`(float, 0.5) — modules/ask.py 유휴 claim 폴링 `_SHUTDOWN.wait(idle_poll_sec)`. tick_sec(reconnect backoff)·sweep 불변.
- Verification: test_duration_breakdown.py 3 + test_ask_jobs.py created_at 2 + feature-0002 전체 회귀 0(2 skip) + py_compile. 적대 코드리뷰 REV-20260616-0302 SHIP(BLOCKER 0).
- Files: src/agent_core.py, src/modules/{ask,ask_jobs,config}.py, tests/{test_duration_breakdown.py,test_ask_jobs.py}, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 표시값 inference-only 복원 / activity step 미emit / IDLE_POLL 제거(tick 복귀).
- Deploy: ask-worker 재빌드(agent_core baked). web 도 동일 import(in-process 폴백 경로).

## CHG-20260619-0319
- TASK-20260619T014034 — LLM provider 외부요인 제한(자격증명 만료) 명시 표면화 (agent-core 면, Major §12.3).
- 근본: LLM 호출 실패가 `result["error"]="LLM 호출 오류: {raw exc}"`(2932)로 raw 노출, gate 류 제한은 tool_result 채널(사용자 미노출). 외부요인(AWS 키 만료 등)을 사용자가 명시 확인할 단일 채널 부재.
- 변경:
  - 신규 `src/modules/llm_provider_health.py`: `classify_llm_provider_error`/`not_configured_restriction`(예외→restriction, 자격증명 비유출) + PG upsert/read(`record_provider_state`·`record_provider_restricted`·`record_provider_ok`·`read_provider_health`) + `probe_provider`(hybrid active, TTL throttle).
  - `src/agent_core.py`: result dict `llm_restriction` 필드 + `_provider_ok_recorded` 가드; `_call_llm` 예외 경로(분류→친화 메시지+passive 기록); 성공 `else` 절 ok 기록; 무자격증명→not_configured.
  - `src/scripts/agent_runtime_schema.sql` §6e + `alembic/versions/20260619_0011_llm_provider_health.py`(CREATE+INDEX+GRANT, 0006 동형). down_revision=0010(head).
- Verification: `tests/test_llm_provider_health.py` 14 + feature-0002 전체 pytest 회귀 0(2 skip) + py_compile. 적대 코드리뷰 REV-20260619-0311(secret leakage/probe auth·cost/agent_core else/PG 폴백).
- Files: src/modules/llm_provider_health.py(new), src/agent_core.py, src/scripts/agent_runtime_schema.sql, alembic/versions/20260619_0011_llm_provider_health.py(new), tests/test_llm_provider_health.py(new), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 분류 미적용(raw 에러 복원) + ok/restricted 기록 제거 + 0011 downgrade(DROP TABLE). 테이블 부재는 graceful(read→unknown).
- Deploy: ask-worker 재빌드(agent_core baked) + 마이그 0011 적용. web 면(app.py 엔드포인트·UI)은 feature-0003 동반.

## CHG-20260619T033714-ai-claude-prompt-injection-defense
- Date: 2026-06-19 (TASK-20260619T033714-prompt-injection-defense — AI 프롬프트 인젝션 방지). 사용자 보안 보강 6종 중 ⑤.
- Scope: feature-0002 `src/agent_core.py`(`_INJ_OPEN/_CLOSE`·`_INJECTION_GUARD_NOTICE`·`_datamark_untrusted`·compose_system_prompt guard 주입·첨부 본문/샘플/recall/**tool 결과**/**KB schema/insights** datamark) + `tests/test_prompt_injection_defense.py`(신규 10) + docs.
- 내용: 비신뢰 콘텐츠(첨부 본문·쿼리 결과·KB 설명·과거 대화)를 sentinel 로 구획(spotlighting) + 명령-계층 고지를 시스템 프롬프트에 코드-주입 → 인젝션("이전 지시 무시" 류) 성공률 저하. defense-in-depth(확률적 완화, 보장 아님; RBAC·SQL guard·allowlist 가 실 경계 fail-closed). sentinel strip 으로 breakout 차단.
- Why: 사용자 요청 — 자연어 인젝션 표면 방어. 기존엔 비신뢰 콘텐츠 무구획.
- Verification: test 10/10(datamark strip 실 동작) + make test 회귀 0 + py_compile. outside-voice SHIP-WITH-FIXES(MAJOR tool/KB datamark + MINOR 표현 흡수).
- Rollback: datamark 호출/guard notice/상수 복원(비파괴, 프롬프트 텍스트만).
- Deploy: **web + ask-worker 재빌드 필수**(agent_core = ask-worker 이미지).

## CHG-20260619T172843-eval-harness
- Date: 2026-06-19 (TASK-20260619T172843-eval-harness — ROADMAP dba-ai-nl2sql **ITEM-01**, Major §12.3). `/_dqa:improve_cycle` 드레인.
- Scope: NL→SQL offline 평가 harness 신규 + `run_agent` None-gated `eval_datasource` seam.
- 내용:
  - 신규 `tests/eval/`: `fixtures/schema.sql`(결정적 합성 e-commerce fixture, prod 무관/PII 없음) · `golden/eval_fixture.yaml`(24문항 nl_question+expected_sql) · `fixture_provision.py`(멱등 provision + datasource 좌표 + ground-truth/생성SQL 실행) · `metrics.py`(execution-accuracy 정규화 set-동치 + retrieval P/R + LLM-as-Judge cap) · `runner.py`(golden→파이프라인→지표→타임스탬프 회귀 리포트; **actual=agent 가 샌드박스 실행해 산출한 결과 CSV 를 읽어 비교 — 생성SQL 을 root 로 재실행하지 않음**, REV BLOCKER 흡수) · `test_eval_harness.py`(스모크 14, Bedrock/DB 불요).
  - `src/agent_core.py`: `run_agent`/`_run_agent_core` 에 keyword `eval_datasource: dict|None=None` 추가. 주어지면 product/registry 라우팅 우회·좌표 직접 data-plane 연결. 운영 호출은 항상 None → **동작 0 변경**(db.connect 좌표 라우팅은 `AGENT_MULTI_DATASOURCE_ENABLED` 게이트 따름 — `make eval` 가 설정).
  - `Makefile`: `eval` 타깃(agent 컨테이너 + 라이브 스택 네트워크, `python tests/eval/runner.py`, pyyaml 설치, judge cap env). `EVAL_ARGS`/`EVAL_MODEL` 옵션.
- Why: ROADMAP ITEM-01 — 현 smoke-only → NL→SQL 품질 정량지표 부재(메타-레버). 이후 성능항목(ITEM-05/06/07/12)의 acceptance 가 본 harness 수치를 인용.
- Verification: pytest 스모크 11/11(정규화/equiv/retrieval/read-only 가드/golden 무결성) + fixture 멱등 provision + expected_sql ground-truth 라이브 검산 일치 + harness end-to-end 실행→리포트 산출 확인. 적대 코드리뷰 REV-20260619T172843-eval-harness. **measured generation accuracy 는 스택 Bedrock 인증 다운(오늘 IAM 제거)으로 보류 — 자격증명 복구 후 `make eval`.**
- Files: tests/eval/{fixtures/schema.sql,golden/eval_fixture.yaml,fixture_provision.py,metrics.py,runner.py,test_eval_harness.py}(신규), src/agent_core.py, Makefile, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: tests/eval/ 삭제 + agent_core eval_datasource 분기/인자 제거(순수 additive, None-gated이라 운영 무영향) + Makefile eval 타깃 제거.
- Deploy: 불필요(개발 도구, 비-서빙). ask-worker 이미지에 eval_datasource seam 포함되나 None-gated 무영향.

## CHG-20260623T101031-ds-business-context
- Date: 2026-06-23 (TASK-20260623T101031-ds-business-context — ROADMAP dba-ai-nl2sql **ITEM-04**, Minor §12.3). `/_dqa:improve_cycle` 드레인.
- Scope: datasource 레지스트리 비즈니스 컨텍스트(Description/DomainTags) → 멀티DS 그라운딩 프롬프트 주입. feature-0002 primary + feature-0003 schema cross-ref.
- 내용:
  - `src/modules/datasources.py`: `_db_datasource` SELECT 에 Description/DomainTags 추가 + **구 스키마 legacy 폴백**(fresh-cursor 루프, 진단 debug 로그). `_row_to_ds` 에 `description`/`domain_tags`(comma-split) 매핑(len-가드 graceful → 구 스키마 None/[]).
  - `src/modules/tools.py`: `_DatasourceRouter.describe()` 에 `description`/`domain_tags` 노출(좌표/비밀번호는 여전히 비노출).
  - `src/agent_core.py`: 인라인 멀티DS 그라운딩 블록을 순수 헬퍼 `_format_multi_ds_grounding(ds_desc)` 로 추출 + 각 datasource 의 설명/도메인 라인 주입. 단일DS/미바인딩(빈 입력)은 "" → 무영향.
  - **cross-ref feature-0003** `src/app.py`: `WebDatasources` CREATE + 멱등 ALTER 로 `Description TEXT`/`DomainTags VARCHAR(512)` 추가(InsightEnabled 선례 미러). 이 컬럼은 feature-0002 read 의 입력원.
- Why: ROADMAP ITEM-04(F-010) — 멀티DS 라우팅/그라운딩에 "이 DS 가 무슨 사업데이터인가" 부재. 설명/도메인을 LLM 에 노출해 라우팅 정확도 그라운딩.
- Verification: `tests/test_datasource_business_context.py` 7 + multi_datasource 회귀 36 = 43 통과 + py_compile(datasources/tools/agent_core/app). 적대 backend 리뷰 REV-20260623T101031 SHIP.
- Files: src/modules/{datasources,tools}.py, src/agent_core.py, ../feature-0003-agent-web-ui/src/app.py(cross-ref schema), tests/test_datasource_business_context.py(신규), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: SELECT/매핑/describe/grounding 추가분 제거(순수 additive, 구 스키마 graceful 라 컬럼 유지돼도 무해) + feature-0003 ALTER 는 nullable 컬럼이라 잔존 무해.
- Deploy: web + ask-worker 재빌드(agent_core/datasources/tools baked + WebDatasources 부트스트랩 ALTER). write-path(admin UI) 는 ITEM-11 follow-up.

## CHG-20260623T105344-kb-glossary-enum
- Date: 2026-06-23 (TASK-20260623T105344-kb-glossary-enum — ROADMAP dba-ai-nl2sql **ITEM-10**, Major §12.3). `/_dqa:improve_cycle` 드레인, PLAN-APPROVED.
- Scope: 용어사전 + ENUM 코드사전(semantic-lite) — agent_kb(PG) ds-scoped 저장 + 질문 매칭 프롬프트 주입. 구조부(저장+읽기+주입); 추출/UI/측정 보류.
- 내용:
  - `src/scripts/agent_kb_schema.sql` §8: `kb_glossary(id,scope_key,term,definition,…)` + `enum_dictionary(id,scope_key,schema_name,table_name,column_name,code,label,…)` (scope_key 컨벤션·UNIQUE·trgm/scope 인덱스·set_updated_at 트리거) + GRANT(agent_kb_rw/ro) 추가.
  - `alembic/versions/20260623_0013_kb_glossary_enum_dictionary.py`(신규): head 0012→0013. UPGRADE(CREATE+INDEX+TRIGGER+GRANT, 멱등)/DOWNGRADE(DROP). 라이브 pg16 트랜잭션 dry-run 검증(ROLLBACK).
  - `src/modules/kb_glossary.py`(신규): `upsert_glossary_term`/`upsert_enum_entry`(RW, ON CONFLICT) + `load_glossary_enum_context(user_message, scope_key, conn)`(RO, ds-scoped 매칭→프롬프트 본문). scope 미지정 시 **`cfg.get_active_datasource()`** 로 도출(멀티DS 격리).
  - `src/agent_core.py` `_build_knowledge_context`: 매칭된 용어/ENUM 을 `## GLOSSARY & ENUM VALUES` 섹션에 `_datamark_untrusted`+펜스로 주입(table insights 뒤). 미매칭/미가용 무영향(try/except).
- Why: ROADMAP ITEM-10(F-007) — 도메인 용어·상태코드 매핑 부재로 NL→SQL 이 코드값/약어 해석 실패. Wren 풀 semantic 은 기각, subset(용어+ENUM)만 채택.
- Verification: `tests/test_kb_glossary_enum.py` 9(upsert SQL/매칭/조립/ds 격리/운영 default scope/미매칭·빈) + KB 회귀(read_backend·ingest) 26 통과 + py_compile + **라이브 pg16 DDL dry-run**(CREATE/index/trigger/GRANT/upsert/scoped-read→ROLLBACK). 적대 backend 리뷰 REV-20260623T105344(NO-SHIP→SHIP-WITH-FIXES, BLOCKER B1 흡수).
- Files: src/scripts/agent_kb_schema.sql, alembic/versions/20260623_0013_kb_glossary_enum_dictionary.py(new), src/modules/kb_glossary.py(new), src/agent_core.py, tests/test_kb_glossary_enum.py(new), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: 마이그 0013 downgrade(DROP 2 테이블) + kb_glossary.py/주입 블록 제거(주입은 try/except·미매칭 ""라 무해). 스키마 테이블은 미사용 시 잔존 무해.
- Deploy: ask-worker + web 재빌드(agent_core baked) + 마이그 0013 적용(superuser, GRANT load-bearing). 등록 UI·추출은 ITEM-11 follow-up.

## CHG-20260623T061043-insight-bottleneck
- Date: 2026-06-23 (TASK-0305 — insight-worker "제품 DB 파악 진전 없음" 병목, Major §12.3). PLAN-APPROVED.
- Scope: insight-worker 처리량/관측성 결함 수정(코드 한정, 스키마/마이그 없음). 지배적 커버리지 원인(28/39 DB GRANT 누락)은 운영 조치로 별도.
- 내용:
  - `src/modules/insight.py` **RC2** — `_compute_schema_fingerprint`/`_compute_table_fingerprint`/`_compute_table_fingerprints_batch` 가 해시할 식별자 토큰을 `casefold()` 정규화(VALUE 한정). MSSQL information_schema 의 케이스 진동(TF_ErrorLog↔tf_errorlog)으로 schema fingerprint 가 흔들려 같은 스키마를 매 cycle 11초 LLM 으로 재생성하던 churn 제거. batch 의 `tname`(dict 키)·`ds_fact_key`/`ds_object_suffix`(저장 키)는 불변 — TASK-0220 write/read-back/grounding 정합 보존.
  - `src/modules/insight.py` **RC3** — `_scan_instance_schema_insights` 에 진전 기반 backoff. 무경계 `_detect_pending_insight_repairs` 가 budget(15s)로 못 닿는 미완성 artifact tail 을 pending 으로 영구 집계 → `force_scan` 이 매 8s tick 영구 latch 되어 도달가능 DB 의 수천-테이블 fingerprint 스캔을 spin 하던 문제. 신규 헬퍼 `_repair_backoff_active`/`_set_repair_backoff`/`_clear_repair_backoff`(per-scope KV `schema_instance_repair_backoff_until`). `pending_only`(=not missing & pending) 스캔이 무진전(생성·복구 0)이면 backoff(최소 60s, 기본 `AGENT_SCHEMA_INSIGHT_RESCAN_SEC`=3600) 동안 pending-only force 억제. missing(새 스키마)·rescan interval(`EVERY_SEC`) 경과·진전 시는 그대로 스캔 → 건강한 처리량 tick cadence 보존. KV 부재=기존 동작.
  - `src/modules/insight.py` **RC5** — `run_insight_cycle` cycle summary 에 `db_failed_perm`/`db_failed_circuit`/`db_failed_other`(TASK-0255 분류 재사용) 추가. `db_failed` 집계에서 `_is_mssql_ds` 게이트 제거(모든 등록 datasource 실패 집계) + 비-MSSQL datasource 도 `db_targets` 1 집계(기본 DB= control-plane 은 제외). 부수: 비-MSSQL ds 실패도 `db_failed>0`→degraded 승격(의도된 가시화).
- Why: TASK-0305 진단(다중 가설+적대 검증). 축 B 처리량(살아있는 DB 의 신규 통찰 0)의 코드 결함 RC2/RC3, 축 A 커버리지(28 DB 권한실패)의 진단 blocker 였던 관측성 공백 RC5. 축 A 의 1차 해결은 GRANT(운영).
- Verification: `tests/test_task0305_insight_bottleneck.py` 8 + feature-0002 회귀 0(사전존재 `test_db_query_ux::test_assemble_core_messages_under_budget_unchanged` 1건은 agent_core 무관·base 에서도 실패, 범위 밖) + py_compile. 적대 backend+qa 리뷰 REV-20260623T061043-insight-bottleneck **ACCEPT**(BLOCKER 0). 컨테이너 미가동 dev 환경이라 라이브 e2e 는 배포 후.
- Files: src/modules/insight.py, tests/test_task0305_insight_bottleneck.py(신규), docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT}.md, wiki/concepts/insight-worker.md, wiki/Log.md, wiki/hot.md.
- Rollback: insight.py 의 casefold(VALUE)·backoff 헬퍼+게이트·RC5 카운터 제거(전부 additive·KV 부재 시 기존 동작). 마이그/스키마 없음 — 코드 revert 만으로 원복.
- Deploy: agent 이미지 재빌드(insight-worker·ask-worker 공유 — insight.py baked). 마이그 없음. RC2 는 배포 직후 1회 cutover 재생성 spike(전 스키마 fingerprint 재계산) 후 안정.

## CHG-20260623T063500-insight-rc4-and-agentcore-test
- Date: 2026-06-23 (TASK-0305 후속 — RC4 throughput 조사 결론 + agent_core 회귀정정). PLAN-APPROVED 연장.
- Scope: **코드 변경은 테스트 1파일뿐**(`tests/test_db_query_ux.py`). RC4 는 조사 결과 document-only(런타임 코드 무변경). 나머지는 문서.
- 내용:
  - **RC4 (document-only, insight.py 무변경)**: 전용 적대 조사 워크플로(3각 + 검증) 결론 = `document_levers_only`. binding constraint = 단일 프로세스 직렬 블로킹 LLM(~11s) × DB-cycle 공유 budget(15s) → DB당 cycle당 ~2건(의도된 self-throttle; 과거 livelock TASK-0145/0146 방어). 안전한 코드 win 없음(병렬화 high-risk·fingerprint 게이팅 테스트 게이트 필요). 튜닝 레버 3종 전부 라이브 부하 데이터 전엔 기본값 변경 금지. REPORT.md/FUNCTION.md 에 constraint·레버·trade-off·카나리 계획 문서화.
  - **agent_core 회귀정정 (`tests/test_db_query_ux.py`)**: `test_assemble_core_messages_under_budget_unchanged` 가 feature-0009 `_merge_consecutive_user_messages`(Bedrock role-교대 제약 대응) 도입으로 stale → 코드 정상 확인 후 테스트를 현행 병합동작에 맞춤 + 원 의도(under-budget pass-through)를 role-교대 fixture 로 보존 + `test_assemble_core_messages_merges_consecutive_user_turns` 신설(`_assistant_text_row` 헬퍼).
- Why: 사용자 요청 "남은 일 및 agent_core 결함도 수정". RC4 는 deferred 항목 — 조사 결과 위험한 blind 변경 대신 문서화가 정답. agent_core 는 stale 테스트(코드 무결).
- Verification: `test_db_query_ux.py` 13/13 + feature-0002 전체 회귀 GREEN(사전결함 해소). RC4 는 적대 워크플로(7 agent)가 검증 — 코드 무변경이라 신규 단위테스트 없음.
- Files: tests/test_db_query_ux.py, docs/{TASK,MODIFY,FUNCTION,REPORT,REVIEW}.md. (insight.py·런타임 코드 무변경.)
- Rollback: 테스트 파일 revert + 문서 entry 제거. 런타임 영향 0.
- Deploy: 별도 배포 불필요(테스트·문서만). RC4 튜닝은 GRANT 후 라이브 데이터 기반 카나리로 진행(본 cycle 범위 밖).
## CHG-20260623T145444-sample-flywheel-core
- Date: 2026-06-23 (TASK-20260623T145444-sample-flywheel-core — ROADMAP **ITEM-02+03** flywheel **PR-A 코어**, Major §12.3). PLAN-APPROVED, 사용자 "성장 루프 앞당김".
- Scope: NL↔SQL 샘플쿼리 저장소(임베딩·검색·주입) + 피드백 flywheel 코어(record/promote/reject·PII). feature-0002 코어; web(RBAC/UI/audit)=PR-B.
- 내용:
  - `agent_kb_schema.sql` §8b + `alembic 0014`: `sample_queries`(scope_key·nl_question·sql·domain·weight·`embedding vector(1536)`·source_type·status·approved·last_validated_at, ivfflat partial 인덱스) + `sample_feedback`(👍/👎/등록 원천·status·promoted_sample_id) + GRANT.
  - `modules/sample_queries.py`(신규): `register_sample`(임베딩 upsert, **`%s::vector` 캐스트**) · `search_samples`(approved∧active∧ds-scoped cosine, **weight 가중**) · `load_example_queries_context`(scope=get_active_datasource, 미가용/미매칭/임베딩실패 "") · `validate_sample_sql`(신선도).
  - `modules/sample_feedback.py`(신규): `record_feedback`(**PII `_mask_prose`**) · `list_pending_feedback`(검수 큐) · `promote_feedback`(승인→approved 샘플 승급, 👎 미승급) · `reject_feedback`. 자동학습 금지.
  - `agent_core.py` `_build_knowledge_context`: `## EXAMPLE QUERIES`(few-shot) 주입 — env `AGENT_SAMPLE_QUERIES_ENABLED` 게이트 + datamark + **"예시이지 실행 대상 아님" 펜스**(injection-only). `config.py` 플래그.
- Why: ROADMAP ITEM-02(F-001, BroQuery 최대 정확도 레버 ±90%) + ITEM-03(F-002, 사용이 정확도를 키우는 순환). 사용자 "샘플이 서비스와 함께 개선되어야".
- Verification: `tests/test_sample_flywheel.py` 12 통과 + py_compile + **라이브 pg16 dry-run**(테이블·ivfflat·cosine sim=1·upsert, ROLLBACK) + **라이브 register(list 임베딩)→search retrieval sim=1.0**(::vector BLOCKER 검증). 적대 backend+security 리뷰 REV-20260623T145444 SHIP-WITH-FIXES(BLOCKER 흡수). **AC-d A/B 측정은 titan-embed(임베딩) 401 다운으로 보류 — 복구 후 `make eval` 샘플 off/on.**
- Files: src/scripts/agent_kb_schema.sql, alembic/versions/20260623_0014_sample_queries_feedback.py(new), src/modules/{sample_queries,sample_feedback}.py(new), src/agent_core.py, src/modules/config.py, tests/test_sample_flywheel.py(new), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: 마이그 0014 downgrade(DROP 2 테이블) + 신규 모듈/주입 블록 제거(주입 try/except·gate·미매칭 ""라 무해). 플래그 OFF 면 즉시 비활성.
- Deploy: ask-worker + web 재빌드(agent_core baked) + 마이그 0014 적용(superuser, GRANT load-bearing). 샘플 등록·피드백 UI·RBAC·audit = PR-B(feature-0003). 임베딩(titan-embed) 복구 전엔 retrieval 무동작(embed None→주입 "").

## CHG-20260623T151643-self-reflection
- Date: 2026-06-23 (TASK-20260623T151643-self-reflection — ROADMAP **ITEM-07**, Major §12.3). PLAN-APPROVED. chat 의존(임베딩 무관).
- Scope: execute_sql 실패 시 명시 bounded 자가수정 넛지(기존 LLM 자율 경로·similar-retry 보강).
- 내용:
  - `agent_core.py`: 모듈 helper `_is_fixable_sql_error`(수정가능 오류 prefix `오류:`/`SQL 실행 오류:`/`도구 실행 오류`, **보안 가드 차단 제외**) · `_classify_sql_error`(syntax 우선→column→table→execution) · `_sql_reflection_nudge`(분류+원SQL[≤400]+표적 힌트, n/cap 표기). tool 루프(tool_msg 조립)에 훅: execute_sql 수정가능 실패 + `reflection_count < cap` 이면 넛지 동봉 + 카운터 증가. per-run `reflection_count=0` 초기화.
  - `config.py`: `AGENT_SELF_REFLECTION_ENABLED`(기본 ON, gate) + `AGENT_SELF_REFLECTION_MAX`(기본 2, cap).
- Why: ROADMAP ITEM-07(F-006) — 에러 되먹임이 LLM 자율 의존 → 명시 bounded 루프로 성공률↑.
- Verification: `tests/test_self_reflection.py` 7(분류/넛지/guard 제외/**실제 'SQL 실행 오류:' shape**/cap/truncate) + prompt-injection 회귀 10 통과 + py_compile. 라이브 관찰(describe-first agent 가 amount→total 무에러 교정 → reflection 백스톱). 적대 backend+security 리뷰 REV-20260623T151643 SHIP-WITH-FIXES: **MAJOR M1(실제 'SQL 실행 오류:' prefix 미매칭 → 주 대상 near-inert) 흡수** + M2/N1/N2. **AC-b 정량 회복률은 에러유발 traffic 필요 — follow-up.**
- Files: src/agent_core.py, src/modules/config.py, tests/test_self_reflection.py(new), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md, docs/improvements/dba-ai-nl2sql/ROADMAP.md.
- Rollback: `AGENT_SELF_REFLECTION_ENABLED=0`(즉시 비활성) 또는 helper/훅 제거(gate off 면 동작 0 변경).
- Deploy: ask-worker + web 재빌드(agent_core baked). 마이그 없음. 임베딩 무관(chat-only).

## CHG-20260623T163242-sample-embed-dim-1024
- Date: 2026-06-23 (TASK-20260623T163242-sample-embed-dim-1024 — ITEM-02 PR-A 후속 fix, Minor §12.3). 사용자 결정(경로 B 로컬 1024 임베딩 전제).
- Scope: sample_queries.embedding 차원 1536→1024 정렬(0014 의 오설정 교정 — 실 임베딩 모델 1024-dim).
- 내용: 마이그 `20260623_0015`(DROP INDEX/DROP COLUMN IF EXISTS/ADD COLUMN vector(1024)/ivfflat 재생성, downgrade 대칭) · `agent_kb_schema.sql` sample_queries 1024 · `config.py` AGENT_KB_EMBEDDING_DIM 기본 1536→1024(texts/titan/로컬 일치).
- Why: 0014 가 sample_queries.embedding 을 vector(1536) 로 생성했으나 titan-embed v2 및 경로B 로컬 모델은 1024-dim(texts 정본=alembic 0001 vector(1024)). 1024 벡터 INSERT 시 차원 불일치 실패 → register/promote 무동작. 라이브 검증(register[1024]→search sim=1.0).
- Verification: 라이브 pg16 0015 적용(컬럼 0행 안전) + 1024 register→search sim=1.0 + test_sample_flywheel 12 회귀 0(FakeConn dim-agnostic) + py_compile. 적대 backend 리뷰 REV-20260623T163242 SHIP(BLOCKER/MAJOR 0).
- Files: alembic/versions/20260623_0015_sample_queries_embed_dim_1024.py(new), src/scripts/agent_kb_schema.sql, src/modules/config.py, src/modules/sample_queries.py(docstring), docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 마이그 0015 downgrade(vector(1536) 복귀, 대칭). 컬럼 비어있어 무손실.
- Deploy: 마이그 0015 적용(superuser). ask-worker/web 재빌드(config baked). 임베딩 모델 1024 확정(경로B bge-m3 등) 후 retrieval 동작.
- **Flag(범위 밖, 기존 drift)**: `agent_kb_schema.sql:68` texts + `kb_backend.py:940` 주석이 여전히 `vector(1536)` — 정본 alembic 0001 texts=1024 와 불일치. texts 는 라이브/정본 1024 라 동작 무관하나 fresh-install bootstrap(schema.sql 우선 실행 시) 해저드 → 별도 cleanup 권장.

## CHG-20260623T170000-task0305-followup-docs
- Date: 2026-06-23 (TASK-0305 후속 — 라이브 배포 검증 정정 + 교훈 기록). **docs-only, 런타임 코드 변경 0**.
- Scope: 사용자 요청 — sudo 배포로 드러난 라이브 발견을 머지된 문서에 정정 반영 + 교훈 2건 기록.
- 내용:
  - `docs/LEARNINGS.md`(repo-level): LRN-20260623-0001(mistake — fingerprint 알고리즘 변경은 fp backfill 동반 필수; casefold 단독 배포가 8,833 fp 무효화→재생성 폭주 유발) + LRN-20260623-0002(pattern — insight db_failed 는 GRANT 보다 네트워크가 지배적일 수 있음, 사유 telemetry 로 perm vs circuit 먼저 가를 것). 둘 다 verified: true.
  - `unit/feature-0002-agent-core/docs/REPORT.md`: "TASK-0305 라이브 배포 검증 + 정정" 섹션 — 축 A 가 GRANT 가 아니라 네트워크(perm:0/circuit:38)임을 라이브 RC5 로 정정 + RC2 cutover 사고·backfill 완화 기록(이력 보존, 정정 명시).
  - `unit/feature-0002-agent-core/docs/TASK.md`: 배포 `[x]`, 축 A 정정 `[x]`, cutover backfill `[x]` 로 갱신.
  - `wiki/concepts/insight-worker.md` §5: db_failed 진단 시 perm(GRANT) vs circuit(네트워크) 를 먼저 가르도록 보강 + 라이브 실측(perm:0/circuit:38) 주의.
- Why: 머지된 docs 가 "축 A=GRANT" 로 서술했으나 라이브 배포가 네트워크 단절(perm:0)로 정정. 동종 재발 방지 위해 교훈 영속.
- Verification: docs-only — 런타임 영향 0. 라이브 근거는 본 cycle 의 배포·datasource_health·RC5 cycle summary(REPORT 기재).
- Files: docs/LEARNINGS.md, unit/feature-0002-agent-core/docs/{REPORT,TASK,MODIFY,REVIEW}.md, wiki/concepts/insight-worker.md.
- Rollback: 문서 entry 제거. 런타임 영향 없음.
- Deploy: 불필요(문서만).

## CHG-20260623T180000-migration-split-brain-hygiene
- Date: 2026-06-23 (TASK-0306 — 마이그 split-brain 해소 + 재발 방지, Major §12.3). PLAN-APPROVED.
- Scope: 라이브 DB 정합(별도 운영 적용·완료) + fresh-install/재발 방지 코드 hygiene.
- 내용(코드):
  - `src/scripts/agent_kb_schema.sql`: texts.embedding `vector(1536)`→`vector(1024)` + 주석(titan-embed v2/경로B 1024-dim, baseline 0001 정합). fresh-install 시 1536 컬럼에 1024 INSERT 차원 불일치로 RAG 임베딩 전면 실패하던 latent 블로커 제거(IF NOT EXISTS 라 기존 라이브 무영향).
  - `alembic/versions/20260623_0015_*.py`: UPGRADE_SQL 을 무조건 DROP+ADD → **멱등 가드**(DO 블록 + `format_type(...)='vector(1024)'` 검사: 이미 1024 면 skip 해 적재 임베딩 보존, 1536/부재면 정렬). downgrade(1024→1536)는 방향별 정확성으로 유지.
  - `bin/alembic-migrate.sh`(repo-level): `alembic_version.version_num` CREATE `VARCHAR(32)`→`VARCHAR(128)` + 무조건 ALTER. revision id `0015_sample_queries_embed_dim_1024`(34자)가 32 초과 → 기록 'value too long' 으로 막히던 latent 버그(라이브 stamp 가 이 사유로 실패) 해소.
  - `src/modules/kb_backend.py`: 시맨틱 검색 docstring 의 stale `vector(1536)/OpenAI` → `vector(1024)/titan-embed v2` 정정(NIT-1).
- 내용(라이브 운영 — 코드 아님, 이미 적용·완료): 0013 UPGRADE_SQL 을 postgres superuser 로 적용(kb_glossary/enum_dictionary 생성+GRANT) → version_num 32→128 확장 → alembic_version 0012→0015 stamp. 파괴적 0015 DROP+ADD 는 실행 안 함(stamp). ITEM-10 glossary/ENUM 기능 silent-dead 복구.
- Why: TASK-0305 후속 내부 진단에서 부트스트랩(_ensure_pg_schema)↔alembic split-brain 발견 — merge 된 ITEM-10(0013)이 silent 미적용. 사용자 "HIGH 포함 전부".
- Verification: 0015 py_compile + alembic-migrate.sh bash -n + 적대 backend 리뷰 REV-20260623T180000 ACCEPT-WITH-NITS(라이브 PG 실측 검증). 라이브 0013 적용·stamp·기능복구 검증 완료.
- Files: src/scripts/agent_kb_schema.sql, alembic/versions/20260623_0015_sample_queries_embed_dim_1024.py, src/modules/kb_backend.py, bin/alembic-migrate.sh(repo), docs/LEARNINGS.md(repo), unit/feature-0002-agent-core/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: 코드 3건 revert(전부 멱등·additive·방어적). 라이브 0013 테이블은 비어있어 DROP 무손실이나 기능 위해 유지 권장.
- Deploy: ask-worker/web 재빌드(schema.sql·kb_backend baked) — 단 라이브 DB 는 이미 정합돼 즉시 효과(glossary 기능 동작 중). 0015 멱등화/script 폭은 fresh-install·차기 ops 안전망.

## CHG-20260623T190000-embedding-auto-backfill
- Date: 2026-06-23 (TASK-0307 — texts 임베딩 백필 + 자동 백필 데몬, Major §12.3). PLAN-APPROVED("백필+자동화").
- Scope: NULL embedding texts 자동 따라잡기(코드) + 1회 백필(운영). kb_embedding_worker 스케줄러 부재로 신규 texts 가 정체하던 것 해소.
- 내용(코드):
  - `src/scripts/kb_embedding_worker.py`: `run_embedding_pass(max_rows)` 추가 — main() CLI batch 로직을 라이브러리로 노출(get_settings/open_pg_conn/fetch_pending_batch/call_openai_embeddings/update_embeddings/count_pending 재사용). **fail-soft**(batch 실패 시 dict 반환·예외 미전파), resumable. main() 무변경.
  - `src/modules/insight.py`: `_embedding_backfill_loop`(별도 **데몬 스레드** — `run_embedding_pass(BATCH_MAX_ROWS)` → `sleep(INTERVAL_SEC)` 반복) + `_start_embedding_backfill_thread`(conn_health 모니터와 동형 daemon). `run_insight_worker_loop` 시작 시 1회 기동. **tick 루프 비블로킹**(per-tick 동기 호출은 titan-embed 수십초 지연으로 본업 블로킹 — REV F1 회피).
  - `src/modules/config.py`: `AGENT_KB_EMBEDDING_AUTO`(기본1) + `_BATCH_MAX_ROWS`(100) + `_INTERVAL_SEC`(60) + __all__.
- 내용(운영, sudo): dry-run(40,200행·~$0.40) 후 1회 백필 실행(titan-embed 느려 수 시간 → 데몬이 이어받음).
- Why: TASK-0305 후속 진단 MEDIUM — 의미검색 recall 저하·확대. 사용자 "백필+자동화".
- Verification: py_compile 3종 + run_embedding_pass import/early-return 라이브 확인 + 적대 backend 리뷰 2회(REQUEST-CHANGES[F1 tick 블로킹, 라이브 batch당 25s 실측]→데몬 분리→**ACCEPT-WITH-NITS** REV-20260623T190000).
- Files: src/scripts/kb_embedding_worker.py, src/modules/insight.py, src/modules/config.py, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md.
- Rollback: `AGENT_KB_EMBEDDING_AUTO=0`(즉시 비활성) 또는 코드 3건 revert(전부 additive·fail-soft). 임베딩 데이터는 그대로(유익).
- Deploy: insight-worker 재빌드·재시작(데몬 활성). **1회 백필 완료/중단 후 배포**(F2 동시중복 회피 — 재시작이 수동 backfill 종료). degraded_readback/error 외엔 데몬 정상 동작(임베딩은 datasource 무관·PG만 필요).

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
