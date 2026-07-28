---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

> 이전 기록(94건): [REVIEW-archive-20260711T120311.md](./_archive/REVIEW-archive-20260711T120311.md)

## REV-20260722T034138-dqa-data-grounding-and-scratch-csv [SUBAGENT:adversarial-backend+security] — 데이터 grounding 지침 + scratch CSV export SHIP-WITH-FIXES
- Date: 2026-07-22
- Cycle: TASK-20260722-dqa-data-grounding (데이터 의미 grounding 지침 — 타임존 B-1·ENUM D-1·분리저장 D-2) + TASK-20260722-dqa-scratch-csv-export (F-5). **Major §12.3**(core 시스템 프롬프트 — 답변 정확성) + Minor(scratch 결과추출). DQA_assistant_마찰개선사항_20260722_v2.md 검토·개선.
- Trigger: §18.8 — (a) core LLM 프롬프트 grounding 변경(정확성 회귀·프롬프트 인젝션 표면·주입 순서) → **backend/correctness** 렌즈; (b) scratch_sql 이 결과를 `/shared/out` CSV 로 export(대화 격리·경로 traversal·share redaction·DoS) → **security** 렌즈. 두 outside-voice general-purpose 적대 리뷰어가 REFUTE 시도.
- VERDICT: **SHIP-WITH-FIXES** (양 렌즈 CONFIRMED 크리티컬 0) → backend PLAUSIBLE 1 흡수 + 정밀도 nit 1 반영.
- **CONFIRMED-SAFE (backend 리뷰어 실측 인용)**: ①주입 무조건성 — `system_content += _DATA_GROUNDING_GUIDANCE`(agent_core.py:4068)가 함수본문 들여쓰기(4)로 `if _group_sender_labels:`(4073, body 8) 밖 → 1:1·그룹 공통. 순서 dialect→active-interpretation→**grounding**→group→conv-ctx→knowledge_ctx→mermaid→scratch(회귀 0). ②GLOSSARY & ENUM VALUES 참조 위치-안전 — 그 절은 knowledge_ctx(4088, grounding 뒤)에 `if glossary_ctx:` 조건부 주입이나, 지침이 "제공됐으면…없으면 샘플링"으로 조건부 서술(위치-중립). ③타임존 주장 기술 정확(MySQL DATETIME naive·@@time_zone≠저장의미). ④run_sql full-fetch — `fetchmany(export_cap+1)`·`truncated=len>cap`·bounded 100k, execute_sql 의 `fetchall()`(무상한)보다 보수적, 유일 소비자 `_tool_scratch_sql`만 `export_truncated` 읽어 계약 변경 무영향(tools.py:2320 truncated 는 materialize 유래). ⑤"CSV 저장: <path>"↔`CSV_PATH_RE` 정확 매칭, `_build_step_result_summary`→`_extract_csv_paths` tool-name 무관 일반 적용, `normalize_step_result_summary` 가 csv_paths 보존 → 프론트 무변경 확증. ⑥첫줄=요약 불변식 보존(2행 결과 false-truncation 없음). ⑦save_csv 실패 graceful.
- **CONFIRMED-SAFE (security 리뷰어 실측 인용)**: ①인젝션 표면 0 — 지침은 보간 없는 정적 상수, `_INJECTION_GUARD_NOTICE`(compose 위치2, 무수정) 순서 불변, 모든 신뢰 지침이 datamarked 미신뢰 GLOSSARY 앞. ②대화 격리 — `scratch_guard`(cross-schema/pg_*/위험함수/다중문 거부 + search_path pin)로 결과=자기 대화 데이터만; CSV 경로는 본 대화 tool 결과에만 emit; `/shared/out` 은 execute_sql 이 이미 쓰는 동일 디렉토리(신규 노출 0). ③경로 traversal 없음 — save_csv 가 서버측 `AGENT_OUT_DIR + uuid` 조립(prefix=정적 리터럴), `/api/file` 이 `_safe_shared_path`(resolve+SHARED_ROOT 봉쇄)로 차단. ④share redaction — `_share_sanitize_step` 화이트리스트(csv_paths 미포함→공유뷰 strip)를 scratch 도 동일 통과, preview_table 만 bounded 노출. ⑤DoS — export cap 100k + statement_timeout 30s 로 bounded(execute_sql 무상한 fetchall 보다 보수적, 회귀 아님).
- **흡수한 PLAUSIBLE (backend — save_csv 실패 시 거짓 CSV 링크 유도)**: `_tool_scratch_sql` 절단 안내가 `_pv_stats.truncated` 에만 게이팅돼, save_csv 예외(디렉토리 부재 등)로 csv_path=None 인데도 "CSV 다운로드 링크를 제공하세요" 를 출력 → 모델이 없는 링크 참조(정직성 결함). execute_sql 은 그 안내를 `if csv_paths:` 안에 중첩. **수정**: 링크 안내를 `if csv_path:` 로 게이트, 실패 시 "전체 결과 CSV 저장에 실패했으니 범위 좁혀 재조회" fallback. 회귀 테스트 `test_scratch_sql_save_csv_failure_no_false_download_claim`.
- **반영한 정밀도 nit (backend advisory)**: 타임존 지침이 DATETIME/TIMESTAMP 를 뭉뚱그림 — `TIMESTAMP` 는 내부 UTC 저장·조회 시 세션 TZ 변환이라 표시가 세션 TZ 따라 달라짐. 지침에 그 구분 1절 추가(지침 자체의 기술 정확도 강화 — 어느 쪽이든 서버 TZ 설정만으로 저장 의미 단정 불가로 귀결).
- **수용(범위 밖·pre-existing, security 리뷰어)**: `/api/file` 이 `conversation_id` 접근만 authz 하고 요청 `path` 가 그 대화 소유인지 미검증 → 인증 사용자가 uuid 경로를 알면 타 대화 `/shared/out/*.csv` 접근 가능. **execute_sql CSV 에도 동등 적용되는 pre-existing 속성**(본 diff 도입 아님·uuid8 unguessable·공유뷰 strip). scratch 는 동일 디렉토리에 producer 만 추가·신규 접근경로 0 → 인지용 flag(별도 follow-up 후보).
- Verification: 변경-특화 `tests/test_scratch.py`(CSV 경로 추출·대량 전체 export·표 포매터 회귀·**save_csv 실패 정직성**) + `tests/test_gc_dialect_context.py`(grounding 본문·무조건 주입 위치·레지스트리) **38 PASS**(로컬 PYTHONPATH), py_compile PASS. **make test 전체 스위트는 기존 비결정 flake**(`postgres-replica` `--no-deps` DNS + 순서-의존 runtime_settings/attachment) — clean main 기준선에도 다른·더 큰 실패셋(15건) 존재, 내 변경-특화 테스트는 양쪽 실패셋 부재 → 회귀 0 확증. **라이브 실증(시각-필터 질의 TZ 확인·가정 명시 / 대량 scratch→CSV 다운로드)은 배포 게이트**.
- Cross-ref: CHG-20260722-dqa-data-grounding-and-scratch-csv / TASK-20260722-dqa-data-grounding / TASK-20260722-dqa-scratch-csv-export / feature-0022-agent-scratch-workspace TASK-0014 / FRICTION_LEDGER(FR-datetime-tz-server-vs-stored·FR-enum-code-hallucination·FR-scratch-result-csv-missing).

## REV-20260716T075345-redteam-axis-rederive [SUBAGENT:adversarial-backend+security] — 자가검증 BLOCK 축 인지 재도출 SHIP-WITH-FIXES
- Date: 2026-07-16
- Cycle: TASK-20260716-redteam-axis-rederive (red-team 자가검증 revise 를 축 인지로 분기 — sql/max-completeness BLOCK 은 도구 허용 재추론으로 승격), **Major §12.3** — core 답변 파이프라인·LLM 비용/지연.
- Trigger: §18.8 — rederive 경로가 실제 도구(execute_sql) 재실행 + LLM 다회 호출 → **backend + security** 렌즈. 적대 코드리뷰(general-purpose outside voice, REFUTE: 인젝션 breakout/무한폭주/라우팅 회귀/fail-open/DB migration). `_datamark_untrusted` 정본 방어·메인 루프 도구 처리·0043 chain 교차검증.
- VERDICT: **SHIP-WITH-FIXES** → BLOCK 1(B1) + WARN 3(W1/W2/W3), B1·W1·W2 흡수, W3 수용.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: ①무한/폭주 — `_rt_rederive` `range(max_rounds+1)`+마지막 라운드 `tools=None` 결정론 종료, `orchestrate_review` while `revisions_done<max_revisions`(기본1·최대2) 종결, 비용 게이트(ENABLED+MAX_TOOL_ROUNDS+max_revisions) 모두 bounded·live. ②라우팅 correctness — 비-sql 축은 텍스트 경로 유지, completeness 는 ordinal≥MIN_LEVEL(기본3=max)에서만 승격, 무산출 시 revise_fn 폴백, new_steps 있으면 evidence 재계산 후 verify(전부 test 확인). ③fail-open — LLM/도구 각 try/except, 무산출 None, orchestrate 최상위 try/except → 예외가 답변 전달 막는 경로 없음. ④migration — 0043 순수 additive ADD COLUMN(PG11+ 메타데이터-only expand-safe), chain 일관(down_revision=0042·MAX_MIGRATION=0043·중복 head 없음), schema.sql 미러 일치, INSERT 15컬럼/15placeholder/15값 정합, GRANT 불필요(상속) 판단 타당.
- **흡수한 B1 (BLOCK — sentinel breakout)**: `build_rederive_instruction`/`build_revision_instruction` 이 비신뢰 findings(claim/fix_hint/evidence — 리뷰어 LLM 산출·적대적 DB 텍스트 유래 가능)를 `<<REVIEW_FINDINGS>>` sentinel 로 감쌀 때 **그 마커를 findings 에서 strip 하지 않아** 위조 close 마커로 구획 breakout 가능. 정본 `_datamark_untrusted`(`_INJ_OPEN/_CLOSE` strip)를 우회. rederive 는 도구 활성이라 breakout→공격자 유도 쿼리 실행 위험 상승(blast radius 는 `execute_tool`/`db_conn` 스코프로 제한 — privilege escalation 아닌 injection foothold). **수정**: `_strip_review_sentinels`+`_findings_bullets` 헬퍼로 자유텍스트 3필드에서 open/close 마커 결정론 제거(`_datamark_untrusted` 대칭), 두 builder 공용. 텍스트 경로(pre-existing 동일 결함)도 함께 봉인. 테스트 `test_findings_bullets_strips_forged_sentinel_breakout`.
- **흡수한 W1 (재도출 SQL 추적성)**: rederive 가 새 SQL 로 최종 답변 근거를 바꾸지만 그 SQL·도구가 steps/executed_sql 에 비가시 → "표시된 실행 SQL 로 추적 가능" 신뢰모델 위배(초안 SQL 만 보임). **수정**: `_rederive_capture`(closure→outer 전달 dict)로 재도출 steps/executed_sql 캡처, orchestrate 반환 후 `rederive_applied` 채택 시 `steps.extend`+`last_sql` 갱신 → `result["executed_sql"]`·표시 step 이 재도출 근거를 가리킴.
- **흡수한 W2 (취소 미존중)**: rederive 도구 루프가 `_cancel_requested_for_run` 미확인 → 취소 후에도 상한까지 SQL/LLM 실행(폭주 아님·비용). **수정**: 라운드 상단 + 도구 실행 전 취소 확인, 취소 시 즉시 break→None(fail-open, 초안 유지).
- **수용(범위 밖·follow-up) W3**: 재도출이 방출한 대형 표는 `all_csv`(초안 steps 산출)에 없어 CSV 링크로 안 접힐 수 있음(초안 CSV 만). 영향 낮음·`execute_tool` CSV 동작 의존 → 라이브 관측 시 follow-up(재도출 후 csv 재산출).
- Verification: `tests/test_redteam.py` **31 PASS**(축 라우팅·completeness max 게이트·evidence 재계산·폴백·B1 sentinel strip) + 전체 스위트(0002+0003) 회귀 0(RC=0). py_compile(redteam/agent_core) PASS. **라이브 실증(높음/매우높음 대화 sql BLOCK 시 rederive_applied=true·tool_rounds>0)은 배포 게이트**.
- Cross-ref: CHG-20260716-redteam-axis-rederive / TASK-20260716-redteam-axis-rederive / feature-0021(red-team 자가검증 정본).

## REV-20260716T010620-graph-search-content-match [SUBAGENT:adversarial-backend+security] — 그래프 뷰 검색 매칭 확장(컨텐츠 카테고리 + AI 능동 분석) SHIP-WITH-FIXES
- Date: 2026-07-16
- Cycle: TASK-20260716-graph-search-content-match (그래프 뷰 검색이 이름/FQN 외 컨텐츠 카테고리·AI 능동 분석 본문까지 매칭), **Minor §12.3** — 비파괴·읽기전용 검색 쿼리 확장·내부 API. 코드 거주 feature-0002, 정본 기능 feature-0016.
- Trigger: §18.8 — 변경 키워드 `query`/`schema`(Cypher WHERE·SQL 조회 확장·인젝션 표면) → **backend + security** 렌즈. 적대 코드리뷰(general-purpose outside voice, REFUTE: 인젝션/NULL 3치/scope 누출/컬럼 불일치/크래시/RO 권한/성능/랭킹 회귀). `_node_dict` 호출처 3곳·alembic 0028/0029/0031/0038·프로덕션 호출처 2곳·shared/db autocommit 교차검증.
- VERDICT: **SHIP-WITH-FIXES** (CONFIRMED 크리티컬 0) → PLAUSIBLE 2건(P2/P4) 흡수 후 SHIP.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: ①인젝션 — `_cq` escape 순서(`\`→`\\` 먼저, `'`→`\'`)가 openCypher C-style 규약 정합 + `_cypher` 동적 dollar-quote(`$mdgq$…$z`) SQL 탈출 차단 + `analysis_keys` 는 DB 출처+`_cq` 인용 + node_analysis_jobs 쿼리 전량 bind param → 신규 인젝션 표면 0(기존 B1 `ev$$il` 테스트 정합). ②NULL 3치 — 비클러스터 노드 `toLower(null)=null`, `null CONTAINS q=null`, OR 에서 무시 → 오포함·크래시 없음. ③scope 격리 — 조립 결과 `WHERE ((A OR B OR C OR n.key IN […]) AND n.scope_key='scope')`, scope AND 가 key IN 포함 OR 그룹 전체를 감쌈 → analysis key 경유 타 datasource 누출 없음(SQL scope + Cypher scope 이중 = redundant-but-correct). ④position() 타입 — alembic 0028 `analysis text` 확정, `::text` no-op(json/jsonb 여도 동작). ⑤RETURN 9식 ↔ `_cypher(...,9)` ↔ `_node_dict` row[0..8] 정합, 유일 다른 shape 생산자 `_node_from_props`(props dict·positional 아님) 무관, `len(row)>8` 가드 하위호환. ⑥RO 권한 — alembic 0028 `GRANT SELECT ON node_analysis_jobs TO agent_kb_ro` 존재. ⑦name/fqn 회귀 없음(OR short-circuit·빈질의 no-op·1자는 analysis 만 스킵).
- **흡수한 P2 (결과 누락 — top concern)**: Cypher `LIMIT` 절단이 trigram 점수 정렬 **이전**이라, 넓힌 WHERE 에서 category/analysis 매칭이 스캔순서 앞을 채우면 이름-정확 매칭이 반환 cap 에 밀려 결과에서 소실(정렬로도 복구 불가). **수정**: `_SEARCH_FETCH_CEIL=240` 후보 풀을 반환 limit 보다 넓게(`fetch_n=max(limit,min(240,limit*4))`) 뜬 뒤, 점수 정렬 후 `out[:limit]` 재절단 → 고점수(이름-정확) 매칭 보존. 반환 개수 계약(limit) 불변. 회귀 테스트 `test_search_nodes_post_sort_truncates_and_keeps_high_score`.
- **흡수한 P4 (latent graceful-degrade 계약)**: `_analysis_match_keys` 실패 시 [] graceful 이 **autocommit 커넥션에서만** 참(현행 두 호출처·`_ro_conn` 모두 autocommit=True 라 오늘은 안전) — 그러나 향후 non-autocommit conn 주입 시 실패가 트랜잭션 abort→후속 Cypher `InFailedSqlTransaction`→검색 전체 빈결과. **수정**: `autocommit` 인자 + non-autocommit 시 SAVEPOINT 로 감싸 실패 시 ROLLBACK TO SAVEPOINT 로 트랜잭션 복원(autocommit 은 savepoint 미사용). graceful 불변을 무조건 참으로. 테스트 `test_analysis_match_keys_savepoint_rollback_on_non_autocommit`·`_autocommit_no_savepoint`.
- **수용(범위 밖·follow-up)**: (P1) 모든 검색이 `node_analysis_jobs` 무인덱스 `position(lower(analysis))` 스캔 1회 추가 — `status='done'` 필터·2자 게이트·300ms 디바운스로 완화하나 done 잡 대규모(수만) 시 전역(scope=None) 검색 지연 체감 가능. 프로퍼 수정 = `analysis` trigram GIN 인덱스(alembic)이나 Minor cycle 에 스키마 변경·stale-image 배포 hazard 회피 위해 **follow-up 으로 이연**(라이브 지연 관측 시). (P3) score GREATEST 에 cluster_label similarity 추가가 cluster_label 보유 노드의 기존 name 랭킹 상대순서를 바꿈 — 카테고리도 정당 신호라 **의도된 행동 변화**로 수용.
- Verification: `tests/test_graph_search_content.py` **10 PASS**(SQL/Cypher 합성·match_via·scope·graceful·P2 절단·P4 savepoint) + 기존 metadata_graph/semantic_cluster/funcproc/routine 회귀 0(PYTHONPATH 로컬) + py_compile. **라이브 실증(배포 후 `/api/admin/metadata/graph?q=<카테고리/분석어>` 매칭)은 배포 게이트**.
- Cross-ref: CHG-20260716-graph-search-content-match / TASK-20260716-graph-search-content-match / feature-0016-metadata-graph(그래프 뷰 정본 §78~81 컨텐츠 카테고리·§69 node_analysis) / feature-0003 graph-ctxmenu.js `_metaGraphSearch`(프론트 소비, 무수정).

## REV-20260715T120000-llm-probe-thinking-budget [SUBAGENT:llm-probe-adversarial-backend]
- Date: 2026-07-15
- Cycle: TASK-20260715-llm-probe-thinking-budget (LLM 헬스 probe 오탐 — stale "요청량 한도/사용량 소진" 배너 고착 해소), **Major §12.3** — LLM 라우팅·외부 비용.
- Trigger: §18.8 — LLM 라우팅/외부요인 분류(backend) + 외부 비용(claude-corp 토큰·5h 윈도우). 적대 코드리뷰(general-purpose outside voice, REFUTE: 불변식/override 실효/게이트/가드/비용 재고정/파이썬 정합).
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0) → CONCERN 흡수 후 SHIP.
- **CONFIRMED-SAFE (리뷰어 실측 인용)**: ①불변식 max_tokens(1088)>budget(1024) 성립, 1024=Anthropic 하한(model_catalog.py:299) · ②요청단위 thinking override 가 litellm config 고정 budget(5000)을 대체 — probe 의 extra_body shape 가 `_call_llm`(agent_core.py:2930) 프로덕션 경로와 byte-identical, reasoning-effort selector 가 동일 메커니즘 프로덕션 의존 · ③게이트 `model_supports_thinking("claude-haiku-4-interactive")`=True / "edge"=False · ④TTL·running·M2 stampede 가드 + classify→None(false restricted 없음) 무변경 · ⑥`create_kwargs: "dict[str,Any]"` 로컬 annotation 미평가·`Any` import 됨, off-by-one 없음.
- **흡수한 CONCERN (item 5 — 비용/5h 윈도우 재고정)**: 리뷰어 지적 — valid-ping 수정이 idle 탭 probe 를 "400 거부(0토큰)"에서 "성공 생성(≤1024토큰)"으로 바꿔, claude-corp 5시간 rolling 윈도우를 60s 마다 재고정(refresh-claude-oauth-token.sh 가 cron probe 를 제거한 바로 그 부작용). 특히 밤새 열어둔 idle 탭이 유일 트래픽이 되는 경우. **수정(백엔드 단독)**: `probe_provider` 에 recovery-only gate 추가 — 비-force probe 는 **state=restricted(복구 감지 필요)일 때만** 실제 valid-ping, ok/unknown 은 실제 호출 없이 cached 반환. 정상 상태 새 제한은 reactive(agent_core record_provider_restricted)가 잡고, force(사용자 재시도)는 gate 우회. → idle 정상 운영 중 claude 실호출 0(재고정 원천 차단), 능동 ping 은 outage 창(rare)에만. 프론트 변경 불요(cross-feature 회피).
- **수용(범위 밖·inherent)**: probe alias `claude-haiku-4-interactive` 의 litellm fallback 에 edge(gemma) 포함 → 두 claude 계정 완전 장애 시 probe 가 gemma 로 성공해 ok 기록 가능. 실제 대화도 동일 alias 로 동일 fallback → service-availability semantics 상 일관, max_tokens/thinking 변경이 도입한 것 아님(별도 follow-up 여지).
- **미계측 주의**: probe 토큰 소비는 llm_usage 미기록(model_catalog.py:361, SDK usage 필드 부재) — 비용 대시보드 비가시. recovery-only gate 로 실호출 자체가 outage 창 한정이라 실질 영향 미미.
- Verification: test_llm_provider_health.py **37 passed**(probe valid-ping 2 + recovery-only gate 4 신규 포함, RC=0) + py_compile. **라이브 실증(배포 후 `/api/llm/health` probe 성공·stale 배너 해소)은 보류** — 배포 게이트.
- Cross-ref: CHG-20260715-llm-probe-thinking-budget / TASK-20260715-llm-probe-thinking-budget / feature-0007 litellm_config.yaml(thinking budget) / bin/refresh-claude-oauth-token.sh(윈도우 재고정 원칙).

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
## REV-20260714T161500-mssql-crossdb-discovery [AGENT-TEAM:security+backend+qa-adversarial] — MSSQL 구조화 발견 도구 DB(catalog) 인지 (conversation_audit FR-mssql-crossdb-structured-discovery)
- Date: 2026-07-14. Related Change: CHG-20260714T161500-mssql-crossdb-structured-discovery. **위험등급 Critical §12.3**(데이터소스 접근 모델). Trigger(§18.8): `schema/query/마이그레이션`(backend+qa) + `데이터소스 바인딩·접근경계`(security) → full 3렌즈 적대 패널.
- 방식: 3 병렬 적대 서브에이전트(security / backend·correctness / qa·regression), 각 "결함 적발" 입장으로 diff+보안게이트+기존테스트 정독. **판정 종합**: BLOCKER 0, MAJOR 3(+ BLOCKER-인접 1), MINOR/LOW 다수. **모든 MAJOR 본 cycle 내 수정 후 재검증**.
- **[security MAJOR → FIXED]** cross-DB 구조화 경로(`_mssql_struct_target` target_db 분기)가 `_struct_schema_access_error` 의 시스템 스키마(sys/guest/db_*) 차단을 우회 → `get_sample_rows(database='Shop', schema_name='sys', table_name='database_principals')` 로 `[Shop].[sys].*`(DB principals/permissions/sql_modules) 표본 유출 가능(M1 의도 경계 재개방). **봉인**: `_mssql_resolve_catalog` 에 명시 시스템 스키마 거부(`database`+sys / `db.schema`+sys) + `_mssql_resolve_table_schema` 시스템 스키마 후보 제외·폴백 dbo + `_mssql_struct_target` 최종 eff backstop. 회귀 테스트 3(`get_sample_rows_crossdb_system_schema_blocked` = 쿼리 실행 0 확인 등).
- **[backend MAJOR/BLOCKER-인접 → FIXED]** `routine_definition` cross-DB 의 `OBJECT_DEFINITION(OBJECT_ID(3-part))` — `OBJECT_DEFINITION(id)` 은 db_id 인자가 없어 **current(pin) DB 컨텍스트**로 평가 → 대상 DB object_id 를 pin DB 에서 해소해 NULL(→4000자 절단 폴백) 또는 오답. **봉인**: cross-DB 는 `[db].sys.sql_modules`(object_id 도 [db] 공간 해소)로 정의 조회, no-db(primary)는 OBJECT_DEFINITION 유지(골든). **라이브 QA 실증**: `routine_definition('dbo','P_CharacterMoveSnapShot_ReadAll_BackOffice',db='Shop')` → 1345자 전체 정의(NULL/절단 아님). 기존 테스트가 문자열만 봐 버그 통과 → 실동작 테스트로 교체.
- **[qa MAJOR M1 → FIXED]** `describe_table` catalog 경로가 describe_columns 에 빈 schema 전달 → 동명-다스키마 컬럼 혼입+헤더/인덱스 축 불일치(하필 관측 마찰 경로). **봉인**: 해석된 `eff_schema`(구체)로 컬럼 조회(헤더/인덱스/샘플 동일 축). **[qa MAJOR M2 → FIXED]** sample/indexes/fk/routine 의 cross-DB 핸들러 경로 미검증 → 통합 테스트 6 추가.
- **[LOW m4 → FIXED]** describe_routine 실스키마 미상 시 dbo 고정 → 비-dbo 루틴 미발견 + "search_tables 로 스키마 탐색"(루틴 미검색) 오도 안내 + 헤더 DB 미표기. **봉인**: `default_schema=''`(스키마 필터 생략·이름 매칭) + DB-qualified 헤더 + 힌트 정정. **[MINOR → 인지]** allowlist display 값이 `_safe_ident` 미적용(악성 admin config 한정 — allowlist 는 이미 검증된 DB명, 방어심화 후속 이월).
- **재검증**: 전체 회귀 **1980 passed / 2 skipped / 0 failed**(신규 `test_mssql_crossdb_discovery.py` 46). 라이브 QA(mssql-web-qa) 수정 실증: describe_columns([Shop],T_ItemInfo)=15컬럼 · search_tables('Buy',Shop)=L_Item_Buy_Log · routine cross-DB 1345자.
- 근본성 교차(R3/R4): 보안 렌즈 — cross-DB 는 유효 허용 DB(freeform 이 이미 도달)만·시스템 DB/스키마·agent_memory·`_safe_ident`+allowlist 이중 방어 유지(경계 확장 0, sys backstop 복원). 회귀 렌즈 — MySQL 골든 db-무시 11 메서드 + 비활성 경로 불변.
- Human Approval: **AskUserQuestion 2026-07-14 "완전 DB인지"**(Critical 접근 모델 사람 승인). PR/deploy 는 외부영향 confirm 별도.

## REV-20260714T171000-mssql-crossdb-deploy [SKIPPED:post-deploy-doc-reconciliation] — 배포 완료 기록 + 원장 상태 정합
- Date: 2026-07-14. Related Change: CHG-20260714T171000-mssql-crossdb-deploy. 코드 변경 0(docs-only).
- SKIPPED 사유: 런타임 코드 무변경 — PR #790(REV-20260714T161500 검증 완료) 배포 후 상태 정합(FRICTION_LEDGER fixed:undeployed→fixed:deployed:unverified-live + TASK 체크박스). 배포 검증 결정적: 4서비스 GIT_COMMIT=b364e964 healthy + deploy-web soak 통과 + 배포 이미지 baked end-state 실증(mssql-web-qa cross-DB describe 15컬럼·routine 1345자).
- Human Approval: 배포 사용자 confirm(AskUserQuestion 2026-07-14 "병합+배포"). 본 follow-up 은 그 배포의 정직-상태 기록(docs-only).
## REV-20260714T063200-partial-evidence-grounding [SUBAGENT:partial-evidence-adversarial-security+backend+qa → API 세션한도 조기종료 → 인라인 자기검증 완료] — 부분 증거 전수 단정 환각 봉인 (conversation_audit FR-partial-evidence-false-verification)
> **rebase 재평가(정직)**: 애초 계획 Lever D(@@ 거부 SHOW VARIABLES 힌트)는 병렬 세션 CHG-20260714T153113-sysvar-select-guard 가 MySQL `@@` denylist 를 제거해 dead 경로가 되어 **출하 철회**(코드·테스트 삭제, 회귀가드 추가). 아래 S-2/B-4 는 N/A 로 격하. 출하 lever = A(절단 epistemics)+B(byte-bounded 확장)+C(grounding 계약).
- Date: 2026-07-14. Related Change: CHG-20260714T063200-partial-evidence-grounding. cycle: ai/claude/feature-0002-agent-core.
- Trigger (§18.8 dispatch): SYSTEM_PROMPT(L1) + execute_sql 도구 피드백/미리보기(L2/render) code change — §18.8 표 키워드 0건 매칭 → **full panel default = security + backend/correctness + qa/regression** 3렌즈. L6(모델·디코딩) 미변경이나 비결정 LLM 행동(프롬프트·도구 피드백) 변경이라 **+회귀 렌즈** 포함. 3 subagent(general-purpose outside voice) dispatch 했으나 **API 세션한도(5:30pm KST reset)로 3건 전부 조기종료** → FR-readonly-query-shapes 선례대로 **인라인 자기검증**으로 대체 완료(메인 루프 Opus 4.8, 코드 확인 근거 첨부).
- **패널 결과: BLOCKING/MAJOR 0**. 전 항목 REFUTED(코드 확인). 실질 조치 0.
- **security — 전부 REFUTED**:
  - [S-1] Lever B 데이터 노출 확대(50→≤500행): 신 경계 침범 아님 — LLM 은 동일 데이터를 sql_guard 통과 SELECT 페이지네이션으로 이미 조회 가능하고 CSV 는 어차피 사용자에 전량 전달(`tools.py:1199` save_csv). forbidden schema(agent_memory) 는 `_INTERNAL_SCHEMAS` 가드가 result 이전 차단이라 이 경로로 누출 불가(변경 없음). char-budget(12,000)·행 상한(500)이 무제한 노출 방지.
  - [S-2] ~~Lever D 힌트 인젝션~~ **N/A — Lever D 출하 철회**(병렬 세션 CHG-20260714T153113 가 MySQL `@@` denylist 제거 → 거부-시-힌트 dead 경로 → `_server_variable_redirect` 삭제). 잔여 diff 에 @@ 관련 코드 없음.
  - [S-3] 프롬프트 상충: Lever C SERVER OPTIONS 규칙은 "never reason from documented defaults — read the actual value first(`@@var`/SHOW VARIABLES)" 로 sysvar-guard 가 @@ 를 허용한 태세와 **정합**(우회 유도 문구 없음). _INJECTION_GUARD_NOTICE(parts index 1) 미훼손.
  - [S-4] stats out-param: `total_rows/shown_rows/truncated` 3정수만 담김(값·PII 없음), caller 는 절단 안내 분기에만 사용(사용자 표면 미노출). REFUTED.
  - [S-5] 웹 렌더 상호작용: 웹 UI step preview_table 은 **CSV 우선 경로**(`render.py:206-219 read_csv_preview max_rows=50`)라 500행으로 안 늘어남(50행 유지) — Lever B 는 LLM 텍스트 content 만 확장. 대량 렌더 무발생.
- **backend/correctness — 전부 REFUTED**:
  - [B-1] 호출처 회귀: `_format_result_sets` 호출처 6곳(tools.py 924/1002/1269/1341/1376/1390/1412/1419) 전부 expand 미전달=종전 동작(legacy 캡). 하류 파서 `render.py:187 parse_result_preview_table` 정규식 `\.\.\.\s*\(\d+\s*행 중` 은 신 문구 `... (N 행 중 M행만 표시 — …`도 **매칭 유지**(실측 MATCH), 소형 전량표시 시 `(N 행)`→truncated=False(정확). feature-0003 절단문구 파서 부재(grep 0).
  - [B-2] 경계값: `shown>=max_rows and not(expand_rows and expand_char_budget and shown<expand_rows and used_chars<expand_char_budget)` — expand=None→break(legacy), shown=500→`500<500`=False→break(hard cap), 예산 소진→break. per-result-set shown/used_chars 리셋 + shown_total 합산 정확. execute_sql 은 단일 SELECT/CTE(multi-statement 차단)라 실질 set 1개.
  - [B-3] 절단 안내 정합: rows kind 결과는 항상 save_csv(`tools.py:1199`)→csv_paths 비지 않음→`truncated`시 안내 항상 붙음(누락 없음). total_row_count·stats.total_rows 모두 rows kind 만 합산=일치.
  - [B-4] ~~@@ 힌트~~ **N/A — Lever D 철회**(위 S-2). SERVER OPTIONS 실측은 Lever C 프롬프트 계약이 담당.
  - [B-5] 프롬프트 충돌: "COMPARING an attachment against the live DB … fetch BOTH sides" 는 **비교를 사용자가 요청한 경우** 조건부 → 기존 ATTACHED FILES 예외("unless the user explicitly asks you to run or validate", `agent_core.py:114,856`)와 정합(리뷰-only 과업 오도 없음). 이 대화가 정확히 그 예외 케이스.
  - [B-6] 테스트 품질: `test_partial_evidence_grounding.py` 는 실 결함 포착형(확장 vs 캡 유지 대비·500 상한·legacy 캡·절단 안내 문구·프롬프트 계약·Lever D 재도입 회귀가드). monkeypatch 경로(`T._raw_execute_sql`/`save_csv`/`_apply_query_cap`/`_freeform_sql_access_error`)가 실 코드 경로 일치.
- **qa/regression — 전부 REFUTED**:
  - [Q-1] 원 마찰 봉인: 183행(2컬럼 협폭 ≈ 30자/행 × 183 ≈ 5.5K자)·61행 목록 모두 12,000자 예산 내 전량 표시(단위테스트 `test_medium_result_expands_fully` 183행 마지막행 확증). 300행+ 대형 목록은 예산 초과 시 절단 안내 정확 유지.
  - [Q-2] 토큰: 최악 per-set 12,000자 ≈ 3–4K 토큰(단일 set 정상). 증가분은 소형 협폭 목록(≈5.5K자)에 국한, 광폭/대형은 기존 캡. 컨텍스트 임계 무위협.
  - [Q-3] 웹 UX: step preview_table CSV 50행 유지(S-5 참조) — 500행 렌더 성능 무영향.
  - [Q-4] 미확인 남발: "미확인" 은 "could not verify" 조건부(전수 확인된 단순 질답 미발동). Discovery budget(효율적 발견)과 상보(발견 실패 시 정직 표기) — 충돌 아님.
  - [Q-5] 커버리지 갭: 하류 절단문구 파서(render.py) 정규식 회귀 없음 실측(B-1). multi-set stats·csv 없는 절단(rowcount)·경계는 코드상 무결(B-2/B-3).
- OVERALL: BLOCKING 0 / MAJOR 0 / MINOR 0 / NIT 1(C-5 문구가 기존 예외와 이미 정합 — 현 문구로 충분, 별도 조치 불요).
- **라이브 실측 필요분(Phase 11b)**: 코드/테스트는 "절단 시 자기교정 안내·소형 결과 전량 노출·부재/전수 단정 근거 계약·@@ 실측 유도" 증명. "실제 대화에서 부분증거 전수 단정 환각 소멸" 은 배포 후 corroboration 재측정분(미수행) → FRICTION_LEDGER `fixed:deployed:unverified-live`.
- Human Approval: PLAN-APPROVED A+B+C+D 전부 + PR/배포 인가(AskUserQuestion 2026-07-14). Major(코어 LLM 경로) → PR/deploy 외부영향 confirm 완료.
- Cross-ref: CHG-20260714T063200-partial-evidence-grounding(MODIFY) · FRICTION_LEDGER FR-partial-evidence-false-verification · ANCHOR 0002 §1~§3 무충돌.

## REV-20260714T210000-attach-review-grounding [SUBAGENT:adversarial-security+backend/correctness] — 첨부섹션 grounding 모순 제거 + LLM 오류 분류 2종 (Cycle B ③④)
- Date: 2026-07-14. Related Change: CHG-20260714T210000-attach-review-grounding. cycle: ai/claude/attach-review-grounding(feature-0002-agent-core).
- Trigger (§18.8): SYSTEM_PROMPT(L1) grounding 계약 + `classify_llm_provider_error`(L2/오류경로) code change → full panel(security/prompt-injection + backend/correctness/regression). 2 subagent(general-purpose outside voice) dispatch — **완주**(cross-session resume 세션, 세션한도 미도달). 원 세션의 인라인 pre-review(security Concern 3 → status 게이트 `_req_ok` 도입)를 fresh 패널로 재검증·확장.
- **패널 결과: BLOCKING 0 / MAJOR 1(수정) / MINOR 2(수정) / NIT 3(2수정·1수용).** 전 diff(③④ + REV-20260714T221500 case-fix 동반)를 한 번에 검토.
- **[MAJOR → FIXED] ③ 모순 제거 불완전 — 정적 SYSTEM_PROMPT 억제 존속**: 두 리뷰어 독립 수렴. ③ 은 동적 `_build_attachment_context_section` INSTRUCTION 억제만 제거하고, **항상 주입되는 정적 SYSTEM_PROMPT `## ATTACHED FILES` 섹션(agent_core.py:112-116)의 동일 억제("Do NOT run execute_sql ... unless the user explicitly asks") + "These attachment instructions take precedence over the general 'query the database' guidance"** 를 방치. L113 작업목록에 "compare" 포함 → 전역 grounding 규칙(L103 "COMPARING an attachment against the live DB: fetch BOTH sides")과 정면충돌하고, "takes precedence" 라 정적 억제가 동적 verify 를 이겨 **③ 이 봉인하려던 환각 경로 유지**. **봉인**: 정적 L114-116 을 동적본과 동형으로 교정(순수 내부리뷰=DB 불필요 유지 / 실 DB 관계 주장=전역 규칙 위임·"Focusing on the attached files does NOT override that grounding rule"). 잔여 억제 사본 grep 0 확인.
- **[MAJOR → FIXED] ③ 가드 테스트 vacuous**: `test_contradictory_suppression_removed` 가 동적 문자열(접두어 "answer about it directly and do NOT...")만 부재 검사 → 더 강한 정적 문구(접두어 "Do NOT...")를 놓쳐 통과(거짓 확신). **봉인**: `test_static_attached_files_suppression_removed`(정적 억제 + "take precedence over the general 'query the database'" 부재) + `test_static_attached_files_section_delegates_to_grounding`(전역 위임 존재·순수리뷰 보존) 추가.
- **[MINOR → FIXED] ④ status=None fallback 이 실 throttle/auth 훔침**: `_req_ok = status is None or status in (400,404,413)` 의 None 폴백 — status 잃은(래핑/네트워크) throttle("too many tokens")/auth("unknown model") 예외가 토큰/모델 어휘로 요청-레벨 매칭돼 `persist_health=False` → provider-health 배너 억제. 주공격은 REFUTED(실 SDK 오류는 status_code 실려 게이트 정확) 이나 잔여 gap → **봉인**: `_req_ok = status in (400,404,413)` 로 None 폴백 제거(context_length/bad_model 은 status 확정 시에만).
- **[MINOR → FIXED] ④ status 게이트 회귀테스트 부재**: 게이트 제거해도 기존 테스트 green → **봉인**: `test_status_429_with_token_text_stays_throttled`·`test_status_403_with_model_text_stays_auth`·`test_statusless_token_text_not_request_level` 추가(위험 status + 어휘가 요청-레벨로 안 새는지 실측).
- **[NIT → 수용] ④ probe 경로 persist_health 비대칭**: probe 는 `confirmed` 게이트만(persist_health 무시). 실무상 probe=1토큰 ping 이라 context_length 불가·bad_model 은 클래스명 무매칭 confirmed=False → 미영속. 저위험 수용(후속 통일 이월).
- **[NIT → 수용] ④ 정규식 greedy**: `invalid.*model.*passed` 등 `.*` 광역 매칭. 영향=친절메시지 치환+persist_health=False 뿐이고 400 은 client-side 라 health 무오염. 저위험 수용.
- **REFUTED**: (persist_health 회귀 0) `_build_restriction` 이 모든 kind 에 키 주입 → 기존 kind True, caller/feature-0003 소비자 무영향. (정규식 정확성) litellm/OpenAI/Anthropic/Bedrock 실제 문자열 5종 직접 probe 전부 정분류. (비밀 누출) 친절 메시지 정적 상수·`_short_tag` raw text 미포함(오히려 기존 raw 덤프 대비 누출↓). (가드 완화) datamark 센티널·sql_guard·RBAC·PII 도구계층 코드 강제·프롬프트 우회 불가.
- Human Approval: PLAN-APPROVED(사용자 "우선순위 자율 + cycle-finalize 까지", 2026-07-14). Major(코어 LLM 경로) → PR/deploy 외부영향 confirm(deploy_scope: included).
- Cross-ref: CHG-20260714T210000(MODIFY) · REV-20260714T221500(동반 case-fix) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260714T221500-attach-case-insensitive-grounding [SUBAGENT:adversarial-security+backend/correctness/regression] — 라이브 실측 잔존 false-missing 봉인(식별자 대소문자)
- Date: 2026-07-14. Related Change: CHG-20260714T221500-attach-case-insensitive-grounding. cycle: ai/claude/attach-review-grounding.
- Trigger (§18.8): SYSTEM_PROMPT grounding 계약 code change → 위 REV-20260714T210000 과 동일 fresh 2 subagent 패널이 전 diff 를 한 번에 검토.
- 계기: FR-partial-evidence **라이브 실측(직접 재현)** — 배포본 244e6bec 에서 원 증상(charactermakinglog "누락 ❌")은 소멸했으나 `gunzlog.LoginEventLog`(첨부 162행 활성 TRUNCATE·활성 131개 중 유일 CamelCase)를 "쿼리에 없는 누락"으로 오판. 근본 = 실 DB(lower_case_table_names=1) 소문자명 vs 첨부 CamelCase 를 모델이 대소문자 구분 비교. grounding 계약에 case-fold 비교 규칙(L102 ABSENCE 직후) 추가.
- **패널 결과(case-fix 부분): NIT 1(수정) — hard contradiction REFUTED.**
- **[NIT → FIXED] 무조건 case-insensitive 동일시가 lcase=0 에서 반대오류(거짓 동일시) 유발**: 초안은 "Match identifiers CASE-INSENSITIVELY" 무조건 서술 → case-sensitive 서버(lower_case_table_names=0)에서 대소문자만 다른 이름이 실제 별개 객체일 수 있어 거짓 동일시 위험. **봉인**: "case-only 차이는 그 자체로 absence 근거 아님(→ case-fold 검색/probe 선행)" 은 유지하되, **동일시(equating)는 lower_case_table_names=1 실측 확인 시로 조건화**("on a case-sensitive server, confirm before equating") → L105 SERVER OPTIONS 규칙과 정합.
- **REFUTED**: (hard contradiction) 신규 규칙(비교/부재판정)과 기존 L252(쿼리 작성 시 표기 보존·소문자화 금지)는 **스코프 분리** — 프롬프트상 구분 명확. (인젝션) 규칙은 정적 SYSTEM_PROMPT(사용자 통제 불가) → 벡터 없음.
- 검증: `test_attach_grounding.py` case 테스트 3(규칙 존재·lcase 조건화·case-fold 검색 요구) — 파일 총 10 PASS. 로컬 41 PASS. `make test`(feature-0002+0003) 신규 회귀 0(무관 4건 pre-existing/환경 — REPORT 상술).
- **라이브 실측 필요분(§정직)**: 프롬프트 레버(모델 추론 대조라 결정론 코드 lever 부재)는 확률적 완화. 배포 후 동일 입력 재-재현으로 LoginEventLog 오판 소멸 확인이 최종 증거 → 배포검증 단계에서 실측.
- Human Approval: 라이브 실측 결과 표면화 후 사용자 "잔존 먼저 조사·수정 후 함께 배포" 명시 선택(AskUserQuestion 2026-07-14). Major → PR/deploy confirm(deploy_scope: included).
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification(라이브 실측 결과) · CHG-20260714T221500(MODIFY) · REV-20260714T210000(동반 Cycle B) · ANCHOR 0002 §1~§3 무충돌.
## REV-20260714T233000-attach-table-coverage [SUBAGENT:adversarial-security+backend/correctness] — 첨부↔실DB 테이블 커버리지 결정론 코드 봉인(신규 tool)
- Date: 2026-07-15. Related Change: CHG-20260714T233000-attach-table-coverage. cycle: ai/claude/attach-table-coverage(feature-0002-agent-core).
- Trigger (§18.8): 신규 tool `check_table_coverage`(DB 접근 + 첨부 파싱 + SQL 식별자 추출) code change → full panel(security/injection + backend/correctness). 2 subagent(general-purpose outside voice) **완주**. 계기: case 프롬프트 레버(REV-20260714T221500) 배포(ee3424c3) 후 라이브 재-재현 부분작동 → 사용자 "코드로 결정론적 봉인"(Option C).
- **패널 결과: BLOCKING 2 / MAJOR 1 / MINOR 2(+security MINOR·NIT) — v1 설계의 순진함을 정확히 적발, 전부 재설계로 봉인.** 도구가 노린 대소문자 seal 자체는 REFUTE 실패(동작)했으나, 반대방향(false-coverage)·절단 경로에서 "authoritative" 배너를 달고 오답을 생성하던 결함들을 수정.
- **[BLOCKING B1 → FIXED] 절단 첨부 → false-missing 을 authoritative 확정**: v1 이 `meta["truncated"]` 미확인 → 대형 스크립트 절단 시 뒷부분 테이블을 "authoritative 미참조"로 선언, 봉인하려던 FR-partial-evidence 를 코드 권위로 재도입(SYSTEM_PROMPT PREVIEW-TRUNCATED/ABSENCE 규칙과 정면충돌). **봉인**: `any_truncated` 감지 → 헤더 "⚠️ 첨부 절단됨" + "미조작 확정(authoritative) 아님" 캐비엇 + SYSTEM_PROMPT 라우팅에 "truncated 면 미확인·원본 재요청" 예외. 테스트 `test_truncated_attachment_downgrades_authority`.
- **[BLOCKING B2 → FIXED] 블록/인라인/# 주석이 active 로 새어 false-coverage**: v1 이 `ln.strip().startswith("--")`(전체 라인 -- )만 분리 → `/* TRUNCATE t */`·`TRUNCATE a; -- TRUNCATE t`·`# TRUNCATE t` 를 활성 조작으로 오집계, 의도적 보존 테이블을 "완전 커버"로 오단정. **봉인**: `_split_sql_active_comment`(블록 `/* */` re.DOTALL + 라인/인라인 `--`·`#` 분리). 테스트 `test_block_comment_not_active_op`·`test_inline_and_hash_comment_not_active_op`.
- **[MAJOR M1 → FIXED] 이름이 아무데나 등장하면 '참조' → 실제 누락 은폐**: v1 `_coverage_referenced`(단어경계 어디서나 매칭)가 컬럼/함수/키워드 동명(`status`/`log`/`user`/`date`/`account`)을 '참조'로 오집계 + "do NOT re-flag referenced" 로 봉인 → 실제 미조작 테이블을 모델이 못 잡음. **봉인**: `_operated_tables`(조작 동사 TRUNCATE/DELETE FROM/DROP TABLE/INSERT INTO/UPDATE/ALTER/RENAME 뒤의 식별자만 추출 — 단순 이름 등장 제외). '참조'→'조작(operate-on)' 의미로 재정의. 테스트 `test_column_or_function_name_not_false_operated`.
- **[MINOR m1 → FIXED] cross-schema 동명**: whole-attachment 검색이 `USE`·schema-qualifier 무시. **봉인**: `_operated_tables` 가 USE 로 현재 스키마 추적 + `schema.table` qualifier 를 requested_schema 로 게이트. 테스트 `test_cross_schema_qualified_not_counted`.
- **[MINOR m2 → 수용/문서화] 다중첨부 union**: `attachment_id` 미지정 시 모든 첨부 content join → before/after 비교에서 한쪽 조작을 전체 커버로 오집계 가능. 도구 description·SYSTEM_PROMPT 에 before/after 는 `attachment_id` 지정 안내(v1 은 union 유지 — 초기화 리뷰 주 용례는 단일 스크립트). 후속 개선 여지.
- **[NIT → FIXED] 테스트 한쪽방향·deadcode**: v1 테스트가 seal 방향만 검증(false-coverage/truncation 회귀 0건) + `out.replace(" "," ")` no-op·취약 assert. **봉인**: B1/B2/M1/m1 회귀 테스트 추가(파일 12), 헬퍼 직접 테스트(`_operated_tables`·`_split_sql_active_comment`), deadcode 제거.
- **[NIT → FIXED] 스캔 비용 O(tables×text)**: 재설계로 `_operated_tables` 가 텍스트를 **1회** 토큰화(finditer)해 set 구성 → per-DB-table O(1) 조회. O(text)+O(tables).
- **REFUTED(보안 — security 렌즈 5벡터 전부)**: 접근 우회(`_struct_schema_access_error`+`_safe_ident` 동일 게이트, agent_memory·미허용DB·시스템스키마 차단) · 정보유출(테이블 **이름만**, describe_schema 의 부분집합·행/컬럼 데이터 0) · 첨부격리(ContextVar per-request run-scope·교차계정 불가) · ReDoS(`re.escape`·중첩 quantifier 없음) · attachment_id(int 강제·현재 run 내 필터, traversal 불가). deferred import 순환/부작용 없음(sys.modules 캐시).
- 검증: `tests/test_check_table_coverage.py` 12 PASS(seal + B1/B2/M1/m1 회귀 + 헬퍼) · import 무결성 · MSSQL crossdb 46 회귀 0 · `make test` 신규 회귀 0(무관 pre-existing/환경 실패는 REPORT 상술).
- **라이브 실측 필요분**: 도구 로직은 결정론(코드). "모델이 도구를 호출하고 결과를 뒤집지 않는가"는 배포 후 라이브 재-재현으로 실측(SYSTEM_PROMPT 라우팅=확률적, 대조=결정론).
- Human Approval: 사용자 Option C "코드로 결정론적 봉인" 명시 선택(AskUserQuestion 2026-07-14). Major → PR/deploy confirm(deploy_scope: included).
- Cross-ref: CHG-20260714T233000(MODIFY) · REQ-20260714-attach-table-coverage(FUNCTION) · CHG-20260714T221500(case 프롬프트 레버 — 상보) · FRICTION_LEDGER FR-partial-evidence-false-verification · ANCHOR 0002 §1~§3 무충돌.

## REV-20260715T104500-friction-ledger-reconcile [SKIPPED:post-deploy-ledger-reconciliation] — FR-partial-evidence 원장 상태 arc 정합 (docs-only, 코드 변경 0)
- Date: 2026-07-15. 런타임 코드 무변경. FRICTION_LEDGER FR-partial-evidence-false-verification 엔트리의 잔존-결함 문구가 "별도 triage 대상"(PR #800 작성 시점)에 머물러, 실제로 완료된 후속 봉인 arc(case 프롬프트 레버 CHG-20260714T221500 부분작동 → 결정론 도구 CHG-20260714T233000 배포 `3c8e78df`)를 반영하도록 정합. status enum 은 `fixed:deployed:unverified-live` 불변(도구 결정론은 코드+유닛 증명, `verified` 는 원장 정의상 다음 audit corroboration 으로 닫힘; end-to-end 라이브 재-재현은 외부 gunzgame DB unreachable 로 미완).
- SKIPPED 사유: 순수 docs(원장) 정합 — 런타임 코드·테스트 변경 0(§18.4 META). 봉인 코드 자체의 적대검증은 REV-20260714T221500(case 레버)·REV-20260714T233000(결정론 도구, BLOCKING2·MAJOR1 수정)에서 완료.
- Human Approval: 사용자 결정 arc(라이브 실측 표면화→"잔존 먼저 수정"→"코드로 결정론 봉인" Option C) 반영의 정직-상태 기록.
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification · CHG-20260714T221500 · CHG-20260714T233000 · REV-20260714T233000.
## REV-20260715T050000-conv-alias-leak-guard [SUBAGENT:adversarial-security+backend/routing/correctness] — 대화 답변 model alias 누출(Bedrock 400) 봉인
- 대상: `shared/model_catalog.py conversation_answer_model` + `agent_core.py _call_llm` budget 산정. 적대 서브에이전트 1렌즈(security+backend+routing 통합, 6축).
- **CONFIRMED-DEFECT#1 (수정 완료)**: 초기 fix 는 outbound `model` 만 `claude-haiku-4-chat` 로 해소하고 `max_tokens`/thinking 은 원본(auto) 기준 산정 → `max_tokens_for_model("auto")=2048`(local cap), 그런데 outbound `-chat` 은 litellm config 에 고정 `thinking.budget_tokens=5000` → **`2048<5000` Anthropic 제약 위반 = 2차 400**(정확히 프로덕션 트리거 `OPENAI_MODEL=auto` 에서 400→400). bare `claude` 는 `max_tokens_for_model`=None → max_tokens 미설정 → 동일 실패.
  - **Fix**: `_call_llm` 에 `budget_model = model if model_supports_thinking(model) else outbound_model` 도입 → **max_tokens 산정만** outbound 기준(agent_max_output(claude-haiku-4-chat)=20000>5000). **thinking 주입 게이트는 원본 model 유지**(비-thinking 누출 alias 는 client thinking 미주입 → outbound config 고정 5000 적용, `20000>5000` 안전). 정상 claude-haiku-4 경로 budget_model=원본=24000 무회귀. `model_supports_vision`·`_record_llm_usage` 는 원본 유지.
  - **회귀 봉인**: G7(model-name 해소, stub 로 예산 경로 미검증)에 더해 **G8 신설** — `max_tokens_for_model`/`model_supports_thinking` 미stub, `agent_max_output` 스파이로 budget 산정 모델을 검증(누출 alias 예산이 outbound=chat 기준·`max_tokens>5000`·기록은 원본). 회귀 `test_reasoning_level_ignored_for_non_thinking_model`(edge→thinking 미주입) 재통과 확인.
- **REFUTED (패널)**: ①해소 대상 claude-haiku-4-chat 타당(등록·edge-free·기본값, sonnet 무강등) ②over-capture 없음(litellm 등록 model_name 전수 대조: edge-fallback≠edge·bare claude만·registered claude-* 무포획) ③insight/routine collateral 없음(`conversation_answer_model` 단일 caller `_call_llm`, insight/aux 는 별도 create 경로) ⑤옛 `edge→edge` 계약은 버그 인코딩이었고 신규 계약 정확(G2b/G6 비-tautological) ⑥FR-edge-fallback 불변식 보존(해소 대상 체인 edge 미도달, G5 config 파싱 검증).
- **PLAUSIBLE-RISK (저위험·수용, 문서화)**: (a) map lookup 은 strip-only(비-lowercase), leak-guard 는 case-insensitive → `"Claude-Haiku-4"` 혼합대소문자는 map miss 후 identity — **비현실적**(모델 문자열은 catalog canonical lowercase). (b) guard 는 known-bad allowlist 라 `claude-haiku-4-interactive`(체인이 edge 도달) 같은 alias 는 identity 통과 가능 — **대화-답변 모델 아님**(OPENAI_MODEL/API_MODEL_OPTIONS 미포함, 대화 경로 미발생). 둘 다 현 입력 도메인 밖 → 미수정, 재검토 트리거만 기록.
- OVERALL: BLOCKING 0 / MAJOR 1(수정 완료) / MINOR 0 / PLAUSIBLE-RISK 2(수용·문서화).
- 검증: `test_conversation_answer_no_edge_alias.py` 15 PASS(옛계약 갱신 + G2b/G6/G7/G8) · `test_reasoning_effort.py` 재통과 · feature-0002 전체 신규 실패 0. `make test`(agent 컨테이너)는 verify-completion 단계에서 정본 실행.
- Human Approval: PLAN-APPROVED(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Major(대화 outbound 라우팅) → PR/deploy confirm(deploy_scope: included).
- Cross-ref: CHG-20260715T050000-conv-alias-leak-guard(MODIFY) · CHG-20260714T210000(같은 축 ④ friendly-message 표면 계층) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260715T060000-attach-inline-honesty [SUBAGENT:adversarial-backend/correctness/prompt] — text-inline 회귀테스트 + 첨부 cap-note 정직화
- 대상: `agent_core.py _build_attachment_context_section` cap-omit 노트 + `test_attach_inline_honesty.py`. 적대 서브에이전트 1렌즈(backend/correctness/prompt, 5축).
- **CONFIRMED-DEFECT ×3 (전건 수정)**: 초안 정직-노트가 새로운 부정확을 도입 —
  - **(1) 거짓 회복 경로**: "ask about it by file name so it is prioritized for inlining" — 파일명 우선순위 메커니즘 **부재**(선택은 `_prepare_text_inline_attachments` 의 `ORDER BY Id DESC LIMIT 20`, 전달 `attachment_ids` 순서는 `WHERE IN` 뿐이라 SQL ORDER BY 가 덮음). → 모델이 파일명 지정 재요청해도 같은 top-20 재선택=broken loop. **수정**: 진짜 회복 = **재첨부**(높은 Id → 최신 → 인라인).
  - **(2) "size cap" 오기**: 크기 상한(64KB) 초과 파일은 `_conv_store.py` 에서 **truncate 되어 여전히 인라인**(`cap_note/truncated`)됨 → 부재 원인이 될 수 없음. 부재는 **count cap 초과 또는 판독실패**만. **수정**: "size cap" 삭제.
  - **(3) len==0 진단 역전**: 0개 인라인은 인프라/판독 실패 가능성 最高인데 초안이 "NOT necessarily a system or MinIO error" + cap 귀속으로 **올바른 진단에서 멀어지게** 함. **수정**: len==0 분기에서 cap 귀속·downplay 제거("the cause is not confirmed", "Do NOT assert a specific cause", 재첨부/재시도).
  - **정정 반영**: `len(map)`을 cap·"N most recent" 로 단정하지 않음("only the most recent … (currently N loaded)"). 회귀 테스트도 갱신(재첨부·no size-cap·no MinIO 단정).
- **REFUTED (패널)**: ②주입안전(노트는 code-authored 상수·int 만 보간, 파일 body 는 여전히 datamark 별도 구획, 신규 sentinel-bypass 면 0) ③기존 테스트 회귀 없음(옛 노트 문자열 참조는 본 신규 파일만, version/injection/idor 테스트는 무관 필드 assert) ④신규 테스트 비-tautological(MinIO 노트 제거는 옛 코드에서 fail).
- OVERALL: BLOCKING 0 / MAJOR 0 / CONFIRMED-DEFECT 3(전건 수정) / MINOR 0.
- 검증: `test_attach_inline_honesty.py` 4 PASS(정정 반영) · feature-0002 전체 신규 실패 0. `make test` 컨테이너는 verify-completion 단계 실행.
- Human Approval: PLAN-APPROVED(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(프롬프트 note + 회귀 테스트) → PR/deploy(deploy_scope: included).
- Cross-ref: CHG-20260715T060000-attach-inline-honesty(MODIFY) · Cycle C(②-frontend app.js 라벨 대칭, 후속) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260715T082345-schema-name-case-drift [SUBAGENT:adversarial-security+backend+qa] READY-TO-SHIP (§18.8 적대 패널 — datasource 스키마 접근/query → security+backend+qa 3렌즈)
- Trigger: 변경 키워드 `datasource`·`schema`·`query`(스키마 접근 경계) → **security + backend + qa** 3렌즈(Critical §12.3 데이터소스 바인딩). `[SUBAGENT:adversarial-{security,backend,qa}]` + 재검증 `[SUBAGENT:adversarial-reverify]`.
- 대상: CHG-20260715T082345-schema-name-case-drift(A: tools.py canonicalize+refresh_case, agent_core.py grounding) + CHG-20260715T082345-picker-case-preserve→**write-path 정규화로 재설계**(feature-0003 admin_products.py).
- **security 렌즈 = REFUTED(치명결함 0)**: 6개 반증 벡터(allowlist 경계 우회·내부/시스템 스키마 노출·SCHEMATA 인젝션·모호·캐시오염·MSSQL) 전부 깨기 실패. 핵심 3주장(소문자-게이트 불변·유일매칭만 교정·내부/시스템 차단 불변) 유지. MINOR 2(SCHEMATA 프로브 breaker 미경유·picker/runtime 모호처리 비대칭)·NIT 2 — 비-보안경계.
- **backend/qa 렌즈 = 결함있음(BLOCKING 0)**: 보안 경계·MSSQL no-op·교차런 오염 반증됨(REFUTED). 적발 confirmed 결함:
  - [MAJOR] 멀티-ds **비-primary**·단일-ds freeform execute_sql grounding 이 저장 소문자로 남음(구조화 도구는 arg-canonicalize 봉인).
  - [MAJOR] `_mysql_schema_case_map` 프로브 일시 실패가 빈맵 캐시 + `_allow_schemas_case_fixed` latch → 런 canonicalize poison.
  - [MAJOR] Part B(admin_console picker) 실효 없음 — admin.js 가 MySQL 스키마명 `.toLowerCase()` 저장, wrong-endpoint.
  - [MINOR] 인용 schema_name canonicalize miss.
- **수정(전건 봉인)**: (1) grounding → `_correct_allow_schemas_case_via_graph`(run-start·모든 바인딩 datasource·metadata_kb graph·connection-free·degrade-safe·MySQL only·모호 제외·live-fixed ds skip[authority]). 단일-ds 는 스키마 리스트 grounding 미주입 + arg-canonicalize 봉인 → deferred(문서화). (2) 프로브 실패=캐시/latch 안 함+경고 로그(재시도 유지), latch=성공(non-empty)만. (3) Part B 재설계 = write-path 정규화(`list_server_databases` 서버 실제 case·SSRF 선행·degrade-safe·모호 제외 — admin.js/수기 입력 무관 chokepoint 봉인); admin_console picker 변경 원복. (4) 인용(`\`\"[]`) 제거 후 조회.
- **재검증 = READY-TO-SHIP**: 결함 1~4 전부 `SEALED`(호출순서·참조정합·재시도·게이트 불변 코드확인). 신규 BLOCKING/MAJOR 0. 잔여 MINOR 3(authority-inversion→**수정반영**·agtype SQL 실AGE 미테스트[런타임 라이브 프로브로 실증됨]·seq-scan 경미[Schema 334행])·NIT 2(admin 저장 지연·write-path 실AGE 테스트 공백) — 전부 non-blocking.
- 검증: `test_schema_name_case_drift.py` 24 + `test_product_databases_case_normalize.py` 2 PASS. 전체 회귀 feature-0002+0003 **2113 passed, 2 skipped**. 보안·멀티ds 회귀(sql_trust_boundary·mssql_security_boundary·multi_datasource·product_multi_datasource·mssql_crossdb·datasource_registry) 무회귀.
- 라이브 실측(§정직): 실 mysql-mv-qa-game(10.103.204.59) 앱 복호 경로 프로브로 **datasource-레벨 라이브 확증** — `dev_1_1_1_20`(소문자)=0테이블 / `DEV_1_1_1_20`(canonical)=63테이블(fix 가 0→63 뒤집음 실증). end-to-end(배포된 agent 가 실 대화에서 canonicalize 호출)는 배포 후 원 입력 재현분(unverified-live).
- Human Approval: **Critical(§12.3 데이터소스 바인딩) → attended AskUserQuestion(2026-07-15) = "A + B(ingestion)"**. PR/deploy = confirm(override 불가).
- Cross-ref: CHG-20260715T082345-schema-name-case-drift(MODIFY) · feature-0003 CHG-20260715T082345-picker-case-preserve(write-path 재설계) · FRICTION_LEDGER FR-schema-name-case-drift · ANCHOR 0002 §1~§3 무충돌.

## REV-20260715T234757-probe-throttle-monotonic-flake [SKIPPED:backend-throttle-sentinel-single-condition-no-rbac-no-data-no-security] — LLM 헬스 probe throttle 센티넬 수정 (20260715T2347-probe-throttle-monotonic-flake, Minor §12.3)
- Panel skip 사유(§18.8): 단건 조건 가드(`last_ts > 0.0 and`) + 테스트. RBAC/데이터/스키마/보안경계/분류로직 무변경. 적대 코드리뷰(권한·주입·enforcement) 이득 없음.
- 근본원인: throttle 이 `now(=monotonic, 부팅 이후 절대초) - ts < min_gap` 만 봐서 초기 ts=0.0 + monotonic<min_gap(갓-부팅)에 첫 probe spurious throttle. 러너 uptime 의존 flake + 첫 복구 probe 누락 잠복 버그.
- 적대 자가검토(refute):
  ① "센티넬 가드가 정상 throttle 을 깨나?" → 실 probe 는 `_PROBE_STATE["ts"] = now`(monotonic>0)로 스탬프(line 441) → 이후 `last_ts>0` 항상 참 → TTL/5s throttle 정상. ts=0.0 은 오직 미-probe 초기값(monotonic 이 정확히 0.0 을 반환하는 일 없음). `test_probe_recent_ts_within_ttl_throttles` 로 잠금.
  ② "과도 probe(비용) 유발?" → 첫 1회만 센티넬로 허용, 그 뒤 스탬프되어 throttle 복원. running 가드·M2 PG throttle 별도 유지 → stampede 방지 불변.
  ③ "recovery-only gate 우회?" → gate(restricted/force 만 실호출)는 throttle 이후 단계(line 425~439)로 무접촉. ok/unknown skip 로직 불변.
  ④ "flake 실증?" → monotonic=10<60·ts=0.0·restricted 재현 시 수정본 1 ping(구 0). 결정적.
- 검증: `test_llm_provider_health.py` 39 PASS(회귀 잠금 2 신규) · flake 조건 재현 확증.
- Cross-ref: CHG/TASK/TEST-20260715T234757-probe-throttle-monotonic-flake · 선행 1c1889e4(recovery-only gate) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260722T050006-branch-chain-race [SUBAGENT:general-purpose] — SHIP-WITH-FIXES (1 needs-fix 반영, 6축 not-a-defect) — 재답변 브랜치 체이닝 동시성 경합 수정 (20260722T050006-branch-chain-race, Major §12.3, PLAN-APPROVED)
- §18.8 적대적 리뷰(general-purpose subagent, 7축 실패-시나리오 탐색). 원 버그(답변이 자기 run 의 user 형제로 붙어 user 가 active-path 에서 사라짐)는 per-run thread-local 커서로 **정확히 봉인** — 답변이 항상 자기 run 직전 write 에 체인, user 는 자신의 답변을 후손으로 가짐. 판정 요지:
  - **[1] needs-fix (반영 완료)**: `branch_run_end()` 가 `_run_agent_core` 평문 말미(finally 아님)라 예외 escape 시 skip → 워커 스레드 stale 커서 잔존, 게다가 begin 이 has_branches 프로브와 같은 try 라 프로브 raise 시 begin skip → 다음 run 이 타 대화 stale id 에 체인 가능(저확률·실재, REV-20260610-P5 M1 이 이미 데인 평문-해제 패턴). **수정**: ⓐ `branch_run_end()` 를 `run_agent` 래퍼 finally(datasource/contextvar 해제와 동일 위치·예외 안전)로 이동, 평문 tail end() 제거. ⓑ `_run_agent_core` entry 에서 프로브 **전** 무조건 리셋(`branch_run_end()`) 후 has_branches 성공 시에만 `branch_run_begin(True)` — 프로브 raise 에도 stale leak 0.
  - **[2] 비분기 회귀 not-a-defect**: `branch_run_active()`=false 면 else 블록이 수정 전과 로직 동일(load_branch_state→chain|linear). INV-1 byte-identical. ([1] 수정으로 leak 시 오진입 경로도 봉인.)
  - **[3] 첫-write not-a-defect**: 첫 write 가 active_leaf 1회 read 중 리셋돼 user.parent 가 어긋나도, 답변은 커서(user)에 체인 + leaf=답변 → user 는 항상 active-path 에 잔존(원 "user 사라짐" 재현 불가). 잘못된 분기점은 [5] version-active 로 격하.
  - **[4] 비-run 호출자 not-a-defect**: 커서 소비 함수(`_save_message`/`save_memory_message`)의 비-run 호출자 리포 전역 부재(전부 `_run_agent_core` 경유). 엔드포인트 sibling 은 `edit_version==1 and edit_root is None` 가드로 커서 경로 우회. 신선 스레드 기본 active=False.
  - **[5] overlap 잔여 not-a-defect(version-active 로 격하)**: thread-local 이라 각 run 내부 체인 무결. 진짜 동시 run 이면 공유 active_leaf 를 마지막 write 가 점유 → 진 run 의 turn(user+answer **함께**)이 비활성 sibling 으로 감(=버전 활성 경합, "user 만 사라짐" 아님). 원 버그 봉인됨.
  - **[6] store 혼선 not-a-defect**: `_save_message`='core'/`save_memory_message`='disp' 별도 thread-local 속성 키. core_messages.id / messages.id 각 store 커서에만 저장·소비.
  - **[7] 반환값 not-a-defect**: `_save_message` 가 `_saved_id` 반환 추가 — 7 호출자 전부 bare statement 로 무시. 무영향.
- 반영 후 검증: `py_compile` 3파일 · 단위 `tests/test_branch_chain_race.py` **6 PASS**(리뷰 권고 추가: core-store `_save_message` 체인 + leak-후 비분기 write 미오염). feature-0002 전체 회귀 PASS(마운트).
- Cross-ref: CHG/TASK/FUNCTION/TEST-20260722T050006-branch-chain-race · feature-0019 ANCHOR §1-§3(INV-1~5) 무충돌 · 데이터 복구(오염 5행)=POST-DEPLOY.

## REV-20260722T055000-branch-chain-race-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 브랜치 체이닝 수정 배포 + 데이터 복구 실증 기록 (CHG-20260722T055000-branch-chain-race-postverify)
- Panel skip 사유(§18.8): 코드 변경 0(POST-DEPLOY 실증 기록·TASK 완료). 코드 리뷰 정본 = REV-20260722T050006-branch-chain-race([SUBAGENT:general-purpose] SHIP-WITH-FIXES).
- 실증: 배포 main 5a32a480(web+워커 롤아웃 soak PASS). 데이터 복구 트랜잭션(UPDATE 1 display + UPDATE 4 core, dry-run count 일치)·복구 후 active-path 에 user 1299 복귀·오염 잔존 0·`/api/history`(bootstrap_admin read.any)가 복구된 트리 6 메시지 반환("로그 흐름만…" 포함) — UI 렌더 경로 실검증. 오염 범위=이 대화 1건뿐.
## REV-20260722T033854-enum-schema-grounding [SUBAGENT:adversarial-backend+security+qa] READY-TO-SHIP — ENUM 자동등록 schema-grounding 게이트 (환각 DB/테이블 차단, Major §12.3)
- Panel(§18.8 3렌즈 — 자동등록 grounding·scope 격리·소급 정리 파괴성): **BLOCKER 0**. 재현 버그 클래스(`dbLog.Currency`/bare `Currency`) 차단·scope 격리·SQLi·트랜잭션 견고 확인(REFUTED).
- **MAJOR 1 (수정)**: sweep 스크립트가 common scope 를 `set_active_datasource("common")` 로 넘겨 `table_insight:ds:common:%` 오조회 → 빈 카탈로그→소급 정리 누락 + 운영자 오도(라이브 게이트는 common 을 active=None 로 grounding). → `None if scope == FACT_SCOPE_COMMON else scope` 로 수정(라이브 게이트와 정합). 보고된 prod scope(mysql-kr-an1-auth)는 datasource scope 라 무영향(완결성 gap).
- **MINOR (수정)**: ① `_enum_known_table_index` 가 `_kb_read_is_pg()`(read-backend flag)에 결합 → mysql-read+PG쓰기 조합에서 게이트 무음 무력화. 카탈로그는 cutover 후 PG 정본이므로 `_kb_read_is_pg()` 게이팅 제거(`_global_insight_rows_pg` 의 `_pg_available()` 자체 가드에 위임). ② `sweep_ungrounded_enum` fail-open 가드 `is None`→`not known_idx`(빈 set 주입 시 전건 DELETE 파괴 footgun 봉인).
- **MINOR (수용)**: 부분 카탈로그 시 실존 table 의 legit enum false-reject 가능(best-effort 자동수집 트레이드오프 — reject 는 `enum_autopropose_skip_ungrounded` 로깅, 답변 비차단). label 내용 검증은 설계 범위 밖(grounding 은 (schema,table) 실존만; 악성 label 공격면 불변).
- **QA 공백(수정)**: 순수함수+FakeConn happy-path 위주 지적 → 게이트 wiring 통합테스트 신설(`test_enum_autopropose_gate.py` 3: 환각 차단·flag off 전건통과·fail-open) + 빈-set sweep no-op 테스트 추가. `not is_enum_grounded` 분기 뒤집기 검출 가능.
- 검증: 신규 20 PASS(grounding 14 + wiring 3 + sweep 추가 3) · 기존 enum/glossary 35 PASS · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- Cross-ref: CHG/TASK/TEST-20260722T033854-enum-schema-grounding · ANCHOR 0002 §1~§3(core/modules 책임분리) 무충돌 · cross-ref feature-0003 admin_metadata(검토 큐 UI, 무편집).

## REV-20260722T033854-enum-schema-grounding [SUBAGENT:adversarial-backend+security+qa ×2 rounds] self-heal 라운드 — insight-worker ENUM 자가수리 (사용자 추가 요청)
- 맥락: 예방 게이트에 이어 "재발해도 insight/ask-worker 동작에 따라 자가수리". insight-worker tick 이 스키마 스캔 직후 활성 scope 의 '없는 DB' enum 을 주기 회수(파괴적 자동 DELETE) → 적대 패널 2라운드.
- **Round 1 — BLOCKER 1 + MAJOR 2 적발(초안: table_insight 점진 카탈로그 기반 table-레벨 sweep)**:
  - **BLOCKER-1**: 부분(불완전) 카탈로그에서 legit enum 영구 오삭제 — table_insight 는 batch·6h·budget rotation 축적이라 buildup/auth-cooldown 창에 **항상** 불완전, 미분석 테이블의 source='auto' enum 을 DELETE.
  - **MAJOR-2**: `else` 블록이 6h interval 미경과 조기 return 에도 실행 → 매 8s tick 낭비·파괴 반복("refresh 직후" 서사 거짓).
  - **MAJOR-3**: `AGENT_ENUM_SCHEMA_GROUNDING=0`(게이트 off)이 self-heal 파괴를 못 막음 → register/delete thrash·명시 허용분 삭제.
- **안전 재설계 → Round 2 재검증 RESOLVED(코드 라인 근거)**:
  - BLOCKER-1 **RESOLVED**: table_insight 카탈로그 폐기, 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`=`load_known_schemas`=단일 `information_schema.SCHEMATA` 조회, budget/rotation 무관 전량)으로 `sweep_unknown_schema_enum` 이 schema(=DB) 존재만 검증. 빈 schema_name 은 SQL `<> ''` + 루프로 절대 미터치. 목록 완전 → false-deletion 원천 차단.
  - MSSQL 제외 **RESOLVED**: `engine != 'mysql'`(allowlist, NIT-D 반영) → schema≠database 엔진 오삭제 차단. MySQL `_db_targets=[None]` 단일이라 다중 DB last-value 문제 없음.
  - MAJOR-2 **RESOLVED**: `scanned=_rep.get('scan_started')` 게이트 → 실제 스캔 tick(~6h)에만. 신규 sweep 은 `SELECT DISTINCT schema_name` 1회로 구설계 full-catalog read 대비 경량.
  - MAJOR-3 **RESOLVED**: `AGENT_ENUM_SCHEMA_GROUNDING and AGENT_ENUM_SELF_HEAL` 결합(둘 다 on 일 때만).
- **Round 2 잔여 MINOR-A(권한 회수/부분조회로 known_schemas 일시 축소 시 오삭제) → catalog-shrink 가드로 봉인**: per-scope KV(`enum_self_heal_prev_unknown`)로 스키마 부재를 **직전 scanned tick + 이번 tick 2회 연속** 관측할 때만 삭제(`sweep_unknown_schema_enum(confirm_lower=)`) → 일시 축소 tick 의 오삭제 흡수(transient 는 재출현 시 confirm 에서 빠져 미삭제). NIT-C(config 주석 stale) 갱신, NIT-D(denylist→allowlist) 반영.
- **범위(정직·MINOR-B)**: self-heal 자동 정리는 **whole-nonexistent-DB enum** 만(안전 subset). 실존 DB 안 wrong-table·bare-schema(db prefix 無)·system-schema 환각은 보존 → 운영자 dry-run 검증 `scripts/enum_grounding_sweep.py`(table-레벨) 담당. ask-worker(run_agent→_enum_autopropose) 경로는 예방 게이트로 이미 커버(무변경).
- 검증: 신규 self-heal 14 PASS(게이트 결합·scanned·engine allowlist·fail-open·dedup·예외·shrink-가드 confirm/저장·빈-schema 제외) · feature-0002 전체 회귀 신규 실패 0 · ruff clean. Round-2 판정: BLOCKER/MAJOR 구조적 흡수, 잔여 MINOR 봉인.
- Cross-ref: CHG/TASK/TEST-20260722T033854-enum-schema-grounding(self-heal) · `modules/insight.py _enum_self_heal`+`sweep_unknown_schema_enum` · ANCHOR 0002 §1~§3 무충돌.

## REV-20260724T054326-timeout-console-sync [SUBAGENT:adversarial-general-purpose] SHIP — LLM upstream 타임아웃 ↔ 관리 콘솔 AGENT_TIMEOUT_SEC(live) 요청 단위 동기화 (CHG-20260724T054326-timeout-console-sync, Major §12.3 — hot-path LLM 호출·타임아웃 계약)
- Trigger(§18.8): 변경이 메인 agentic loop 의 LLM 호출 경로(`_call_llm` extra_body·client·run 예산 타임아웃)를 건드림 → 적대 리뷰 1렌즈(general-purpose, "이건 깨진다" 기본자세 7개 공격각). 결과 **SHIP**(BLOCKER/MAJOR 0).
- 공격각 검증 결과:
  - A(SDK forwarding/collision) **CLEAN**: openai 2.26.0 `extra_body`(body JSON 추가)와 `timeout`(httpx)은 별개 파라미터. `_call_llm` kwargs 에 top-level `timeout` 없음 → double-set 없음. body `timeout` 은 litellm 예약 파라미터로 소비(gemma 로 미전달). 선행 라이브 실험(body=5→408·=200→200)이 litellm per-attempt 소비 확증.
  - B(edge/gemma) **CLEAN(코드)**: 모든 agent 요청은 단일 LLM_BASE_URL litellm 프록시 경유·`timeout` 은 litellm 소비. extra_body 가 edge 에서 비어야 한다는 assert 없음(구 `"extra_body" not in kwargs` edge 가드 → `_xb(kwargs)=={}` 로 올바르게 마이그). 잔여: 결정 실험이 sonnet-only → POST-DEPLOY edge ping 1회로 완전 봉인.
  - C(`_rts.get_int` 안전) **CLEAN(실증)**: 항상 int 반환·None/예외 없음(파일 read guarded, bad value fallback). override 시 [5,3600] clamp, 무override 시 .env/스펙 기본(60). 450→450·999999→3600·1→5·"notanint"→60 확인. `max(5,int(...))` 은 redundant-safe.
  - D(client 캐싱) **CLEAN**: ask() client(≈3979)는 `_run_agent_core` 당 신규 로컬 생성(모듈 캐시 아님) → 콘솔 변경이 다음 ask() 에 반영.
  - E(retry/fallback wall-clock) **CLEAN**: 앱→litellm 단일 HTTP; httpx client timeout(=콘솔값)이 총량 bound → num_retries=1+fallback 의 다중 slow attempt chain 을 컷(빠른 429/401 fallback 은 fit). 변경 전과 동일 구조.
  - F(테스트 정확성) **CLEAN(전부 PASS)**: `_xb()` 는 timeout 만 pop → 모든 thinking/effort 정확매칭 가드 보존. Sonnet5-never-budget_tokens·'일반' no-override 불변식 유지. `test_body_timeout_synced_...`(450∈[5,3600] → write_snapshot 미거부·미clamp) **non-vacuous**.
  - G(probe 미변경) **CLEAN**: `probe_provider` 는 top-level `timeout=8`(httpx)·body timeout 무 → 8s 헬스 ping bound 유지. probe 테스트 유효.
- 수용된 트레이드오프(Finding 1, MINOR by-design): 콘솔을 스펙 max **3600** 으로 상향 시 단건 hung 호출이 serial ask-worker 를 최대 ~3600s(client), 병리적 다라운드는 run 예산 상한(~10800s)까지 점유 가능. **이는 사용자가 명시 요청한 sync 의 의도된 결과**(운영자가 3600 을 고르면 그 호출을 3600s 허용하겠다는 뜻)이며 스펙 max 로 이미 bounded — client httpx 를 콘솔과 무관하게 독립 cap 하면 sync 목적 자체를 훼손하므로 미채택. 운영자 판단 영역(REPORT §트레이드오프 기록).
- 반영된 NIT(2·3, 주석 정확성): `_call_llm` 타임아웃 주석에서 (2) client 는 ask() 진입 시점 값이라 run 도중 콘솔 상향 시 min(client,body)·다음 ask() 자동정합, (3) 이 client 는 로컬 생성 OpenAI 로 `_get_llm_client` 캐시 경로 아님을 명시하도록 수정.
- Cross-ref: CHG/TASK/TEST-20260724T054326-timeout-console-sync · feature-0007 REVIEW-20260724T054326-timeout-console-sync(config 주석) · subagent id a600d2a00c460bae7 · ANCHOR 0002 §1~§3 무충돌.

## REV-20260724T155534-tool-result-cap-raise [SUBAGENT:adversarial-general-purpose] SHIP — 도구 결과 4000자 하드캡 → 대형 설정 backstop (CHG-20260724T155534-tool-result-cap-raise, Major §12.3 — 코어 LLM 루프·전 도구 결과 경로; conversation_audit FR-procedure-analysis-result-truncated)
- Trigger(§18.8): 변경이 메인 agentic loop 의 **도구 결과 → LLM 되먹임 경로**(context sizing)를 건드림 + 도구 결과는 최대 인젝션 벡터(untrusted DB 데이터) → 적대 3렌즈(backend/correctness + security + qa/regression, "이건 깨진다" 기본자세). 결과 **SHIP**(BLOCKING/MAJOR 0).
- 렌즈별 검증 결과:
  - **backend/correctness** — REFUTED ×2: ① "저장 site 가 uncapped 대형 content 영속" → `tool_result = _cap_tool_result(tool_result)`(4921)가 messages.append/_save_message/step_info 이전 **무조건** 재대입, 사이 branch/continue 없음 → 저장은 이미 캡된 값(안전). ② "rederive step record 가 캡된 길이 보고" → `_tr_len = len(_tr)` 를 `_cap_tool_result` **전**에 계산해 `result_length` 는 TRUE 길이 보존(메인 루프 result_length 는 캡 후 반영이나 구 `[:4000]` 코드에서도 동일 — 회귀 0).
  - **security** — REFUTED ×1 + 경계 불변 확인: "캡 상향이 인젝션 방어 약화" → `_datamark_untrusted` 는 캡 **후** 두 `role=tool` append 에만 적용, sentinel 구획·forged 마커 strip 은 truncate 무관 → 메커니즘 불변(동일 spotlighting envelope 안 content 만 증가). sql_guard/RBAC/datasource 바인딩/PII 경로 **0 변경**(순수 context-sizing 상수+슬라이스). `cap<=0` 무제한 sentinel 은 **운영자 전용 env**(공격자 미도달).
  - **qa/regression** — 커버리지 충분(기본캡≥100k·프로시저 passthrough·초과 절단+note·경계·무제한 sentinel 0/-1·짧은 결과). 옛 4000 tool-result 절단 assert 하는 기존 테스트 **부재**(다른 4000 매치=토큰예산 테스트) → 파손 0. FR-partial-evidence 계약 보존(절단 시 `... (truncated)` note 유지·테스트).
- **저장/영속 경로 실증**: PG `agent_runtime.core_messages.content`=`text`(무제한, agent_runtime_schema.sql:147)·save 경로 PG-only(MySQL content dual-write 부재 → 64KB overflow 없음). mirror 경로는 `preview[:500]`·step `result_preview[:300]` 로 캡 무관 bounded.
- **수용된 트레이드오프(MINOR, by-design)**: 메시지당 컨텍스트/비용 상한이 4k→최대 100k(describe_routine)·~12k(execute_sql 자체 `_TOOL_PREVIEW_CHAR_BUDGET`) 로 상향. 히스토리 reload 는 **메시지 수**(`max_messages=50`) 기준 윈도우라 대형 결과 누적 시 context_length 도달 가능 — 단 `classify_llm_provider_error` context_length 분류(persist_health=False·글로벌 배너 미오염)로 **graceful degradation**(친절 에러) + 유한·env 튜닝 가능(`AGENT_TOOL_RESULT_MAX_CHARS`). 사용자 결정("전 도구 대형 캡")의 명시적 수용 범위. **운영 note**: 필요 시 캡 하향 또는 byte-기준 히스토리 윈도우는 후속 별도 lever.
- 반영된 NIT 3건: (a) rederive docstring `4000자 truncation`→`_cap_tool_result 대형 backstop 캡`(agent_core.py:4636) (b) 저장 comment `원문 유지`→`datamark 미적용(원문); 캡은 이미 적용된 tool_result 저장`으로 명확화(:4926) (c) `_cap_tool_result` 중복 가드 `if cap and cap > 0`→`if cap > 0`(2791, 동작 동일·가독).
- Cross-ref: CHG/TASK/TEST-20260724T155534-tool-result-cap-raise · FUNCTION.md(tool_result 대형 backstop 캡 항목) · FRICTION_LEDGER FR-procedure-analysis-result-truncated · 선행 FR-show-create-routine-blocked(describe_routine) · FR-partial-evidence-false-verification(절단 epistemic) · subagent id a2af724b865cf671a · ANCHOR 0002 §1~§3 무충돌.

## REV-20260724T085937-sonnet-reasoning-budget-guide [SKIPPED:test-only-code-review-canonical-in-feature-0003] — PASS
- 대상(feature-0002): `tests/test_runtime_settings.py` 의 sonnet-budget 단정 갱신(shared runtime_settings 가 adaptive 죽은 budget 스펙 제거함에 따름). src 코드 변경 0(test-only).
- 리뷰 방식([SKIPPED] 사유): 로직 정본(shared/runtime_settings + admin UI)의 적대 리뷰가 feature-0003 REV-20260724T085937-sonnet-reasoning-budget-guide [SUBAGENT:adversarial-general-purpose] **SHIP-WITH-FIXES**(Finding D 반영). feature-0002 는 그 변경에 대한 테스트 계약 갱신뿐이라 추가 패널 판별력 낮음.
- Cross-ref: feature-0003 REVIEW/CHG/TASK · shared MODIFY 동일 slug.

## REV-20260727T105326-worker-attachment-postprocess [AGENT-TEAM: backend+concurrency] SHIP-WITH-FIXES — §18.8 Verification Panel (2 rounds)
- **Trigger**: worker 실행 경로 + 첨부 쓰기 + KV 상태 전이 순서 변경 → backend correctness + concurrency 렌즈(§18.8 `schema/query` + 상태머신). 2라운드(수정 후 재검증) 수행.
- **[R1 BLOCKER 1 → 반영·R2 CLOSED]** worker 모드에서 web 의 **strip 블록이 미게이팅** — 빈 materialize 목록으로 블록을 지워 DB 저장 → 워커가 읽을 때 블록이 없어 첨부 영영 미생성 + 스크립트 본문 소실(원 결함보다 악화). Fix: web 후처리 **4곳 전부** 게이팅.
- **[R1 BLOCKER 2 → 반영·R2 CLOSED]** 순서 계약 무효 — 독자(web attach loop·`/api/ask_result`·프런트 재조회)는 ask_jobs terminal 이 아니라 **KV last_status** 를 보고 탈출하는데, 그 done 은 `run_agent` **내부**(agent_core.py)에서 후처리 전에 기록됐다. Fix: `defer_terminal_status` 로 성공 경로 KV done 을 후처리 뒤로 이전(error/cancel 즉시 유지 + finally 보장).
- **[R1 MAJOR 3 → 반영·R2 CLOSED]** `import web.app`(~0.93s 실측) 비용이 첫 job 의 민감 구간에 위치 → 기동 시 워밍업.
- **[R2 MAJOR 4 → 반영]** **혼합 버전 배포 창**: 모드 기반 게이팅은 web(신)+worker(구) 구간에서 첨부 미생성 + 원문 영구 잔존(`deploy-web-only` 면 영구). Fix: **증거 기반 게이트**(`_raw_block_left` — 블록이 남아 있으면 web 이 self-heal). 배포는 워커 포함 전체 스코프.
- **[R2 MINOR → 반영]** (a) worker 모드 첨부 step 기록 소실(TASK-0285 ④ 회귀) → `_record_attachment_step` (b) error/cancel 경로 strip 누락(web 정책은 무조건 strip) → materialize 만 skip (c) `_update_assistant_message_content` 가 예외를 삼켜 MINOR 가드가 inert → **bool 반환** 후 게이팅.
- **[R2 LOW → 반영]** (a) error 가 늦게 설정되면 terminal 미기록 위험 → error 로라도 기록 (b) 마커 pop 순서.
- **검증-SAFE(REFUTED)**: 이중 materialize(웹 게이팅+워커 직렬+error 가드)·lease fencing(`only_if_current_run`)·conn/커서 누수·inproc 경로 무변경·다른 답변 생산 경로 부재(fix-with-ai·reanswer 모두 `/api/ask` 재dispatch)·`/api/progress`·`/api/ask_status` 미노출.
- **잔존(기존·미해결로 명시)**: `/api/history` 는 run-status 게이트가 없어 `_save_message`~strip 사이 raw 블록이 조회 가능(pre-existing — inproc 도 동일, 창은 수 초). 근본 해소는 저장 시점 strip 이며 별도 triage.
- **판정**: SHIP-WITH-FIXES → 전 findings in-cycle 반영, 2라운드 재검증에서 BLOCKER/MAJOR CLOSED. 라이브 실측=POST-DEPLOY.

## REV-20260727T175800-false-truncation-belief [SUBAGENT:adversarial-security+backend+qa] SHIP-WITH-FIXES — 허위 절단 인식 봉인 + 루틴 정의 offset 이어읽기 (CHG-20260727T175800-false-truncation-belief, Major §12.3 — 코어 SYSTEM_PROMPT + 전 도구결과 피드백 경로; conversation_audit FR-false-truncation-belief)
- **Trigger(§18.8)**: 변경이 (a) 메인 agentic loop 의 **SYSTEM_PROMPT epistemic 계약**과 (b) **도구 결과 → LLM 되먹임 문구**를 동시에 건드림 + 도구 결과는 최대 인젝션 벡터(untrusted DB 데이터) → 적대 3렌즈 병렬(security / backend·correctness / qa·regression, "이건 깨진다" 기본자세). **사용자 승인**: AskUserQuestion 2026-07-27 "서브에이전트 패널(권장)". 원 세션의 1라운드는 계정 5시간 한도로 3렌즈 전부 조기 종료 → **본 세션에서 전량 재실행**(부분 산출물은 harvest 후 폐기, 재검증으로 대체).
- **판정**: **SHIP-WITH-FIXES** — 3렌즈 합계 BLOCKER 2 / MAJOR 8 / MINOR 7 / NIT 3 중 **in-cycle 반영 12건**, 정직 이연 4건(아래 명시), 수용 1건.
- **[BLOCKER 1 — 3렌즈 전원 독립 적발 → 반영]** **셀 100자 절단이 완전성 판정에서 누락**. `_format_result_sets` 는 100자 초과 셀을 `s[:100]+"..."` 로 자르면서 `stats["truncated"]`(행 절단)에는 집계하지 않는다. 그래서 1,269~3,179자 프로시저 본문을 **105자만** 보여준 결과에 A2 가 "절단되지 않았습니다" 를 붙이고 A3 가 "마커 없으면 전량" 을 확정했다 — 원 마찰(허위 절단 인식)의 **정반대 방향인 허위 완전성**을, 그것도 원 대화 주제(프로시저 본문 조회)에서 곧바로 발동. 3렌즈가 각각 재현(`정의 3179자 → 표시 103자 / '전부입니다'=True / 절단 마커=0건`). **Fix**: `stats["cell_truncated"]`/`cell_truncated_count` 분리 out-param + 셀 절단 시 기존 화이트리스트 어휘("당신은 보지 못했습니다")로 **명시 마커** 부착 + A2 게이트를 `행 미절단 ∧ 셀 미절단 ∧ export 미절단` **3축 AND** 로 강화(execute_sql·scratch_sql parity).
- **[BLOCKER 2 — qa 렌즈, security 렌즈 MAJOR 로 중복 → 반영]** **닫힌 마커 화이트리스트 + "NO MARKER = COMPLETE" 가 무통지 절단 경로를 완전으로 단정**시킴. qa 렌즈가 절단 통지 **19곳 전수 census** 를 만들어 3종 마커 매칭을 대조한 결과 **미매칭 13곳**: 첨부 인라인 ` [truncated]`(agent_core.py:917 — FR-partial-evidence 원천 경로), check_table_coverage 절단 경고(§107 EXCEPTION 과 자기모순), search_tables DB cap, scratch_import `(상한 초과분 잘림)`, scratch export 상한, graph_navigate 무통지(`nodes[:60]`/`edges[:60]`, `neighborhood()['truncated']` 미노출), MSSQL `ROUTINE_DEFINITION` 4000자 폴백, comment `[:40]`/`[:30]`, EXPLAIN `StmtText[:80]`, sandbox 샘플 `[:77]`, 답변 collapse 마커, **그리고 이 cycle 이 새로 만든 describe_routine 조각 자신**. **Fix(근본)**: 완전성 추론을 **침묵 기반 → 긍정 신호 기반**으로 반전. ① 절단 신호를 **열린 집합**으로 재작성(`[truncated]`·절단·잘림·상한 초과·…만 검색·전체 N행 미리보기·정의 구간 등 실제 어휘 열거 + "many ways") ② `NO MARKER = COMPLETE` 삭제 → `COMPLETENESS COMES FROM AN EXPLICIT COMPLETENESS SIGNAL, NOT FROM SILENCE` + "Absence of a truncation notice is NOT proof of completeness — some tools cap silently" 명문화. "지어낸 도구 한계 금지" 는 **결과가 완전성을 단정할 때만** 적용되도록 한정. 이로써 무통지 절단 13곳이 **프롬프트 레벨에서 일괄 무해화**(개별 emitter 수정 없이).
- **[MAJOR — backend, 반영]** **창(50k) < 캡(100k) 이라 종전에 한 응답이던 50k~98k 루틴이 불필요하게 2조각**으로 쪼개짐(실측 60,504자 정의 → 2조각). 부분 열람 위험을 없애려는 변경이 그 밴드에서 부분 열람을 새로 만든 것. **Fix**: `AGENT_ROUTINE_DEF_CHUNK_CHARS` 기본을 **0 = auto**(창 = `캡 - reserve`)로 바꿔 **캡이 어차피 자를 지점부터만** 쪼갠다 → 캡 이하 정의는 조각화 회귀 0, 캡 초과분만 페이징. 부수효과로 초대형 정의 호출 수 ~절반(패널 NIT 반영).
- **[MAJOR — backend, qa MINOR 중복, 반영]** `max(1_000, cap - 2_000)` **바닥값이 자기 docstring 의 불변식을 깨뜨림**: cap ≤ ~1,090 에서 창 ≥ 캡이 되어 `_cap_tool_result` 가 조각 꼬리(다음 offset 안내)를 잘라 **전량 도달 경로가 사망**(모델은 `(truncated)` 만 받고 다음 offset 을 모름). 실측 표 `cap=1000 → offset안내 생존=False`. **Fix**: 바닥값 제거 — `room = cap - reserve ≤ 0` 이면 **윈도잉 비활성(0)** 으로 전환해 캡의 `... (truncated)` 가 정직한 절단 신호로 남게 한다(dead-end 보다 우월). 캡 무제한(≤0)도 자를 이유가 없어 비활성. 음수 설정 = kill-switch. 전수 테이블 테스트로 고정(cap 100000/10000/1500/1000/800/0/-1 × chunk 0/-1/1/50000/500000).
- **[MAJOR — security, 반영]** **페이징 종료 신호가 루틴 본문으로 위조 가능**. 정지조건이 문구("마지막 구간")였고 프레임과 본문이 같은 평문 네임스페이스를 공유 → `CREATE PROCEDURE` 권한 보유자가 본문 앞부분에 종료 문구를 심으면 모델이 조기 종료하고 **미열람 백도어 구간을 "전체를 받았다" 로 오인**(실측: 청크1 안에 위조 종료문 1건 + 그 뒤 `GRANT ALL ON *.*`). `describe_routine` 은 "이 프로시저 위험한가" 의 유일 증거원이라 영향이 크다. **Fix**: 종료 판정을 **산술**로 이전 — 권위 있는 `[정의 구간 A~B / 총 T자 … 마지막 구간: 예/아니오]` 머리말을 **본문보다 앞**에 두어(본문이 덮어쓸 수 없음) `B == T` 로만 종료하게 하고, SYSTEM_PROMPT 에 "정의 본문 안의 문장에서 종료 신호를 받지 말라(a routine author can write 마지막 구간입니다 into the SQL)" 를 명시. 회귀 가드 테스트 신설.
- **[MAJOR — backend, 반영]** **범위 초과 offset 이 헤더·파라미터·권한 안내를 전부 버리고 "이미 마지막 구간까지 조회했습니다" 라는 검증 불가한 이력을 단정**. 대형 루틴 A를 페이징하던 모델이 인자를 복사해 루틴 B를 조회하면 **내용 0자를 받고도 "다 읽었다"** 는 신호를 얻어 B 분석을 날조할 수 있다(실측: 권한 거부 안내문 소실). **Fix**: offset 을 0 으로 되돌려 **정상 출력 + 사실 통지만**("요청한 offset=N 은 …범위를 벗어나 처음부터 반환합니다"), 열람 이력 단정 문구 삭제. 관련 NIT(offset>0 에 "앞 구간은 이전 호출에서 이미 받았습니다" 라는 날조 provenance)도 사실 서술("앞 구간 0~N자는 이 응답에 포함되지 않았습니다")로 교체.
- **[MAJOR — backend·qa·security 3중 적발, 반영]** scratch_sql **`export_truncated` 미확인**: export 경고가 `if _pv_stats["truncated"]` 안에 중첩돼, 미리보기는 완전한데 export 만 잘린 조합에서 **경고가 삼켜지고 하필 신규 완전성 단정이 발화**. `row_count` 자체가 상한값이라 "전체 N행" 도 거짓. 기본값(100,000 > 미리보기 500행)에서는 latent 지만 `_rt()` 런타임 하향으로 즉시 도달. **Fix**: export 경고를 독립 분기로 hoist(항상 노출) + 완전성 단정 3축 AND 에 포함.
- **[MAJOR — backend·qa 중복, 반영]** **"조각 이어붙여 원문 전량 복원" 헤드라인 테스트가 합성 입력 artifact**. fixture 가 `"".join(f"L{i:04d};")` = **개행 0개** 라서만 통과하고, `out.split("\n\n", 2)` 파싱을 빈 줄 포함 실전 본문에 적용하면 **1,320자 중 151자만 복원(89% 손실)**. 즉 사용자 요구("길이 제한 없이 전체 본문")의 유일한 증거가 현실 입력에서 무효. 윈도잉 자체는 정확했음이 길이 기준 파싱으로 반증됨. **Fix**: fixture 를 빈 줄 + ```sql 펜스 포함 실전형으로 교체하고, 검증을 **머리말이 광고한 구간의 산술 계약**으로 재작성(`full[a:b] in out` + 구간이 빈틈·중복 없이 `[0,total)` 을 덮음 + 이어붙여 원문 동치). 안내문 문자열 파싱 의존 제거.
- **[MINOR — qa, 반영]** **0행 결과에 대칭 신호 부재**. "X가 없다" 허위 단정의 최다 진입점인데 A2 가 `total>0` 로 게이트돼 침묵했다. **Fix**: "(조회 결과 0행 — 도구가 자른 것이 아니라 이 조건에 맞는 행이 없습니다. '없다/누락됐다' 고 단정하기 전에 테이블·컬럼·필터·식별자 대소문자를 먼저 확인)" 부착(DML `rowcount` 경로 오발동 방지로 `had_rows_set` 게이트).
- **[MINOR — backend, 반영]** **형식 오류 offset 의 조용한 0-폴백**. `"50.0"`·리스트·`True`(→1) 가 침묵 처리돼 모델은 이어읽었다고 믿으며 1번 조각을 재수신(컨텍스트 낭비)하거나 1자 밀린 조각을 받았다. 범위 초과는 명시 오류인데 형식 오류는 침묵인 비대칭. **Fix**: 타입 화이트리스트(`int`/`str`, `bool` 배제) + 명시 오류 반환. 미지정/None/공백/`"  0  "` 은 정상 경로 유지(기존 호출 형태 100% 호환).
- **[MINOR — security, 반영]** **`Infinity`/`1e400`/5,001자리 int 가 raw Python 예외 문구로 누출**(`OverflowError: cannot convert float infinity to integer`, `ValueError: Exceeds the limit (4300 digits)`) — `except (TypeError, ValueError)` 가 OverflowError 를 못 잡고, `tool_args` 에 남은 `inf` 가 step 기록을 조용히 유실시켰다. **Fix**: `except Exception` + 타입 게이트. **본 수정 중 내 신규 테스트가 2차 결함을 자체 적발** — 오류문 조립의 `repr(raw)` 자체가 5,001자리 int 에서 ValueError 를 던짐 → `try/except` 로 감싸 형식 요약(`<int 값 표시 불가>`)으로 대체.
- **[MINOR — security, 반영]** env 창 설정에 **하한 부재**(`CHUNK_CHARS=1` → 100KB 정의에 100,000회 호출 필요 → `AGENT_MAX_STEPS=128` 소진 후 도달 불가). **Fix**: `_ROUTINE_CHUNK_MIN=4_000` 하한 + `0`/음수 의미를 형제 상수 규약과 정합(0=auto, 음수=비활성)하도록 재정의 — 구 구현은 인접 상수의 "0/음수=무제한" 규약과 **반대**여서 운영자가 `0` 을 "쪼개지 마라"로 읽으면 정반대 결과(50k 창)를 얻었다(qa/backend MINOR 동시 반영).
- **[MINOR — backend, 반영]** A2 문구가 **결과셋 완전성과 모집단 완전성을 구분하지 않아** 모델이 쓴 `LIMIT n` 결과가 `ABSENCE/COMPLETENESS` 규칙의 "non-truncated result" 증거로 승격될 경로. **Fix**: "이 쿼리가 반환한 N행 전부이며 도구는 아무것도 자르지 않았습니다 — 단 이 쿼리의 WHERE/LIMIT 범위 밖은 여전히 미확인" 으로 한정 + §ABSENCE 규칙의 "a non-truncated result" → "a result that states it is complete" 로 정합.
- **[MAJOR — qa, 프롬프트 레벨로 반영·코드 이연]** 답변 collapse 마커 `📎 [전체 181행 미리보기]` 가 **실제 절단**(181→5행)인데 A3 가 "미리보기 = 절단 아님" 으로 재라벨했고, 그 마커는 `_build_self_review_messages`(red-team/revise)·`_save_message`(다음 턴 히스토리)로 **모델에게 되먹여진다**. **Fix(이 cycle)**: A3 절단 신호 목록에 `"전체 N행 미리보기" (a collapsed table in your own earlier answer IS truncated)` 를 명시 → 재라벨 무효화. **이연(정직)**: 마커 문구 자체를 `전체 N행 중 M행 표시` 로 바꾸는 것은 답변 렌더 출력 + 테스트 3곳 변경이라 pre-existing 개선으로 분리(프론트는 `a[href*="/api/file?"]` URL 기준 파싱이라 문구 결합 없음 — 실측 확인, 후속 cycle 안전).
- **정직 이연(이 cycle 이 도입하지 않은 pre-existing gap — 프롬프트 반전으로 무해화되었으나 emitter 미수정)**: ① `graph_navigate` 노드/관계 60개 절단 무통지(`neighborhood()['truncated']` 미노출) ② MSSQL `ROUTINE_DEFINITION` 4000자 카탈로그 폴백 무표식 — A3 에 "결과가 자체 절단 통지를 담은 경우엔 정직히 고지하라(SQL Server catalog fallback)" 예외를 넣어 **정직한 고지가 금지되지 않도록** 했으나 표식 자체는 미구현 ③ comment `[:40]`/`[:30]`·EXPLAIN `StmtText[:80]`·sandbox 샘플 `[:77]` 무통지 ④ 절단 통지 emitter 를 단일 헬퍼(SSOT)로 통합하고 프롬프트↔emitter 정합을 census 테스트로 고정하는 리팩터. → FRICTION_LEDGER 후속 triage 로 기록.
- **수용된 트레이드오프(by-design, 사용자 결정 범위)**: 초대형 정의 페이징에 **회차 예산이 없다**(security MAJOR). 실측 4MB 루틴 = 42~84회 호출, 조각이 `role=tool` 히스토리로 이후 턴마다 재전송(히스토리 윈도우가 **메시지 수** 기준). 다만 **전량 도달 자체가 사용자 명시 요구**(AskUserQuestion 2026-07-27: "여러 번 호출하여 초대형 캡을 넘어가는 범위도 조회")이므로 강제 상한은 요구 위반이다. 완화: auto 창(캡-여유)으로 호출 수 ~절반, 머리말이 총 문자수를 미리 알려 모델이 전량 필요 여부를 판단, `AGENT_MAX_STEPS`(128) 가 단일 run 을 유한하게 유지, `AGENT_ROUTINE_DEF_CHUNK_CHARS` 음수로 kill-switch. 선행 CHG-20260724T155534-tool-result-cap-raise 가 동일 축(대형 결과 ↔ 컨텍스트 예산)을 같은 근거로 수용한 전례와 정합.
- **REFUTED(실제 공격·입력을 시도해 결함을 만들지 못한 축)**: ① **권한/allowlist/RBAC 게이트 우회·순서 역전 불가** — `agent_memory`·allowlist 밖 스키마에 offset 0/1/100000/399999 전수 시도, 전부 차단 + **DB 쿼리 실행 0회**. 윈도잉은 `_safe_ident` → `_mssql_struct_target`/`_struct_schema_access_error` → 카탈로그 조회 → 루틴 부재 early-return **전부 뒤**의 최종 return 에만 적용. ② **offset 경유 SQLi 불가** — offset 은 SQL 조립에 전달되지 않고 이미 실행된 결과 문자열 슬라이싱에만 쓰임. ③ **길이/존재 oracle 불가** — 정의 열람 권한 없으면 오류문의 "전체 길이" 는 거부 안내문 길이이고, 없는 루틴은 윈도잉 전에 return. ④ **secret 노출 0** — 신규 코드가 참조하는 config 키 2개뿐, secret 계열 40키 참조 0건, 출력물 내 값 출현 False. ⑤ **DB fetch 무캡** — `_collect_cursor_error`/`execute_sql` 에 행 상한·자동 LIMIT 주입 0건이라 execute_sql 의 행 완전성 주장은 참. ⑥ **다중 result set 혼재** — `truncated_any` OR 로 완전성 억제됨. ⑦ **offset 산술** — 창 100/총 250에서 경계 전수(0·1·99·100·149·150·249·250·251·10000) 중복·누락 0, offset 단조 증가(무한루프 없음). ⑧ **조각 정렬 붕괴 없음** — `ORDER BY ROUTINE_TYPE` 결정적, 동명 proc+func 공존 시에도 순서 고정·양 헤더 도달. ⑨ **"절단되지 않았습니다" + "(truncated)" 모순 쌍 불성립** — parts 조립 순서상 캡이 완전성 문구를 먼저 잘라냄. ⑩ **제거된 문구("핵심 미리보기(수 행)만") 외부 소비자 부재** — 프론트엔드 파서 의존 0.
- **검증**: 신규 `tests/test_false_truncation_belief.py` **13건 → 23건**(패널 반영분 전건 회귀 가드: 셀 절단 억제·stats out-param·0행 대칭·scratch parity 3건[소스 문자열 검사 → **실제 핸들러 호출**로 승격]·프롬프트 열린집합/부정단정·산술 종료조건·창 산정 전수 테이블·캡 이하 미분할·캡 통과 후 offset 안내 생존·실전형 본문 전량 복원·위조 방어·범위초과 클램프·형식오류 명시·병리적 값 예외 비노출). 인접 계약 테스트 `test_partial_evidence_grounding.py` 2건은 **계약 변경 반영**(stats 키 추가·프롬프트 라벨) — 프롬프트 라벨은 `TRUNCATION NOTICES (PREVIEW-TRUNCATED and every other wording)` 로 구 앵커 문자열을 보존해 선행 cycle 테스트를 깨지 않음. 컨테이너 `make test` 회귀: **FAIL 4건 전부 pre-existing 환경 의존**(`git archive HEAD` 무변경 체크아웃에서 동일 실패 재현으로 확증) · ruff PASS.
- **라이브 실측 미수행(POST-DEPLOY)**: "실제 대화에서 assistant 가 없는 도구 한계를 더는 지어내지 않는지" + "offset 이어읽기가 라이브에서 관측되는지" 는 배포 후 원 입력 재현 + 다음 audit corroboration 재측정.
- Cross-ref: CHG/TASK-20260727T175800-false-truncation-belief · FUNCTION.md(완전성 신호 대칭 항목) · shared/docs/MODIFY.md 동일 slug · FRICTION_LEDGER FR-false-truncation-belief · 선행 FR-partial-evidence-false-verification(절단 epistemic — 본 변경이 그 과발동을 좁히고 반대 방향 과발동을 봉인) · FR-procedure-analysis-result-truncated(`AGENT_TOOL_RESULT_MAX_CHARS` backstop 유지) · FR-show-create-routine-blocked(describe_routine 신설) · subagent ids: security/backend/qa 3렌즈(원 세션 1라운드는 한도 소진으로 폐기, 본 세션 재실행분이 정본) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260727T185742-false-truncation-belief-deploy-status [SKIPPED:post-deploy-status-transition-doc-only] — PASS
- 대상: `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-false-truncation-belief 의 status 전이 `triaged` → `fixed:deployed:unverified-live` + 배포/런타임 실측 증거 기록. **코드 변경 0**(pure-meta changeset — verify-completion META mode).
- 리뷰 방식([SKIPPED] 사유): 로직의 적대 검증은 직전 REV-20260727T175800-false-truncation-belief [SUBAGENT:adversarial-security+backend+qa] 에서 완료(BLOCKER 2 / MAJOR 8 / MINOR 7 / NIT 3 → 12건 in-cycle 반영). 본 cycle 은 그 배포 결과를 원장에 기록하는 사실 전사이므로 추가 패널의 판별력이 없다.
- 근거(측정): PR #963 merge main `ef24448c` → `make deploy-web` 전체 스코프 soak 통과, 4서비스 GIT_COMMIT=ef24448c, web `/healthz` ok(mysql_ok·pg_ok), 배포본 ask-worker 런타임에서 신규 계약 9항 실측 확인(열린 절단신호·침묵≠완전·구 닫힌계약 제거·산술 종료조건·auto 창 99000·초대형 머리말·offset 안내 캡 생존·캡 이하 미분할·셀 절단 stats 분리·offset 형식오류 명시).
- 라이브 대화 실측은 여전히 미수행 → 원장 status 는 `unverified-live` 유지(거짓 done 금지).
- Cross-ref: REV/CHG/TASK-20260727T175800-false-truncation-belief · PR #963.

## REV-20260728T104438-false-truncation-belief-live-verified [SKIPPED:live-measurement-record-doc-only] — PASS
- 대상: FR-false-truncation-belief **라이브 실측 결과 전사** + 원장 `fixed:deployed:verified` 전이 + 신규 축 `FR-false-absence-zero-row-catalog-scope` 분리 기록. **코드 변경 0**.
- 리뷰 방식([SKIPPED] 사유): 로직의 적대 검증은 REV-20260727T175800-false-truncation-belief [SUBAGENT:adversarial-security+backend+qa] 에서 완료. 본 cycle 은 라이브 측정치의 사실 전사이므로 추가 패널의 판별력이 없다. 대신 **측정 자체의 반증 설계**를 적용했다(아래).
- **측정의 반증 설계(패널 대체)**: (a) 시그니처 부재를 성공으로 읽지 않기 위해 **원 시나리오 동형의 대량 완전 결과**를 강제하는 turn 을 별도 투입(291행 카운트 + 200행 렌더) — "마찰이 발동할 조건을 만들고도 발동하지 않음" 을 확인. (b) 신호가 실제로 붙었는지 **도구 결과 실물**을 PG 에서 대조(모델 답변만 보고 판단하지 않음). (c) 완전성 억제가 우연이 아님을 셀 절단 사례로 역방향 확인. (d) 실측 중 발견한 부재 단정에 대해 **배포 전 base rate 를 별도 측정**해 자기 변경으로의 오귀인을 차단(89건 중 5건 — 기존 실패 모드). (e) 페이징 미관측을 "검증됨"으로 포장하지 않고 **데이터 분포(35건 max 7,732자)로 미도달임을 명시**.
- **판정**: 주 판정축(허위 절단 오귀속) **verified**. 부가축(offset 페이징) 라이브 미도달 — 배포본 직접 호출로만 검증됨을 원장에 정직 표기. 신규 축(허위 부재)은 미수정 `triaged`.
- Cross-ref: REV/CHG/TASK-20260727T175800-false-truncation-belief · CHG-20260728T104438-…-live-verified · 재현 대화 `20260728012534-a56ec98e` · PR #963.

## REV-20260728T114459-false-absence-catalog-scope [SUBAGENT:adversarial-security+backend+qa ×2 rounds] SHIP-WITH-FIXES — 0행→허위 부재 봉인: 루틴 열거 도구 + 카탈로그 스코프 인지 (CHG-20260728T114459-false-absence-catalog-scope, Major §12.3 + **보안 경계 완화**)
- **Trigger(§18.8)**: 코어 SYSTEM_PROMPT + LLM 도구 표면 신설 + **freeform SQL 가드 완화**(보안 경계) → 적대 3렌즈 병렬(security 중심). 사용자 범위 결정: **RC-B 포함**. BLOCKING 적발로 **2라운드 재검증** 수행(security 렌즈).
- **판정**: **SHIP-WITH-FIXES** — 1R BLOCKER 3 / MAJOR 9 / MINOR 8 → 전건 반영. 2R 에서 1R 봉인이 **불완전함이 재적발**(BLOCKER 1 STILL OPEN) → 재수정 후 실증 CLOSED. 잔여는 pre-existing 1건(HEAD 동일)만 정직 이연.
- **[1R BLOCKER — 3렌즈 독립 적발 → 반영]** **`sys` TVF piggyback**: `collect_schema_object_refs` 가 테이블-ref 만 훑어 `sys.dm_exec_sql_text(...)` 등 함수/TVF 가 pair 에서 소실 → 화이트리스트 뷰 하나(`sys.objects`)를 앵커로 끼우면 임의 DMV·서버 파일 판독 TVF 통과. HEAD 좌우 대조로 **순수 회귀** 확증(10건 HEAD BLOCK → WT ALLOW). Fix: 수집기가 ① db-only 참조를 `(db,"")` 센티널 ② 함수 참조를 `(schema, 함수명)` 으로 합류 + `_FORBIDDEN_FUNCTIONS_TSQL` 에 서버 스코프 TVF + `dm_` 접두 거부.
- **[1R BLOCKER — 반영]** **MySQL `search_routines` 가 `agent_memory` 열거**: "allowlist 무관 영구 차단" 불변식을 신규 도구가 깼다(`schema_name` 명시 경로는 거부하면서 생략하면 통과 = fail-open). Fix: dialect 가 `sys_exclude_schemas` 를 받아 양 엔진에서 제외. 2R **CLOSED** 실증.
- **[1R BLOCKER(qa) — 반영]** **라이브 1차 쿼리 형태 미개입**: 실제 부재 단정을 낳은 것은 `SELECT COUNT(*) …` 로 **0행이 아니라 값 0인 1행**인데, 0행 분기에만 단 초기안은 이를 놓친 채 오히려 "1행 전부이며 자르지 않았습니다" 완전성 문구를 붙여 **배포 전보다 "0개" 단정을 쉽게** 만들었다. Fix: 스코프 진단을 **행 수 무관 + AST 기반**으로 재작성, 진단이 붙는 결과엔 완전성 단정 억제, 이미 3-part 인 쿼리엔 미부착(거짓 진단·재시도 루프 제거).
- **[2R BLOCKER — 1R 봉인 불완전, 재수정 후 CLOSED]** **별칭 그림자(alias shadowing)**: `FROM sys.objects sys CROSS APPLY sys.fn_xe_file_target_read_file(...)` 처럼 **보호 스키마명을 테이블 별칭으로 선언**하면 수집기의 UDT 메서드 alias 면제가 발동해 함수 참조가 다시 소실 → 1R 우회가 재개통(HEAD BLOCK → WT ALLOW, 순수 회귀). T-SQL 에서 2부분 함수호출의 앞 토큰은 **항상 스키마**라 서버는 진짜 `sys` 함수를 호출한다. Fix: `_alias_exempt()` 신설 — 보호 네임스페이스(`sys`/`guest`/`information_schema`/`agent_memory`/시스템 DB)는 별칭으로 가릴 수 없고, 면제는 **2토큰 이상**(정당한 `alias.column.method()`)에만. 3 수집기(`_collect_qualified_func_refs`·`_named`·`_has_overqualified_function`) 공통 적용. **실증 CLOSED**: 별칭·브라켓·대문자·앵커교체·`agent_memory`/`guest`/`master` 가리기 7종 전부 BLOCK, UDT 메서드 체인은 계속 ALLOW.
- **[2R MAJOR — 반영]** **완화를 프롬프트가 무효화**: 프롬프트가 여전히 "the `sys` schemas are blocked" → 위험만 늘고 편익은 사라짐. Fix: 문구를 `_safe_sys_views_phrase()` **SSOT** 로 생성. 더해 2R 이 지적한 사용성 결함(뷰만 열고 관용구는 안 알려줘 `SCHEMA_NAME()` 으로 쓰다 `current_schema()` 라는 **PostgreSQL 이름**으로 거부돼 thrash → 원래의 구조적 0행 경로로 회귀)도 같은 문구에 **금지 함수 제약 + 대체 형태**(`JOIN sys.schemas`/`sys.types`/`sys.sql_modules.definition`)를 실어 해소.
- **[2R MINOR — 반영]** `dm_` 접두 전면 거부가 **사용자 UDF/TVF**(`dbo.dm_calc_total()`·`dbo.dm_GetSales(2024)`)를 차단 = 정상 기능 회귀. Fix: 접두 규칙을 **`sys` 자격 함수에만** 적용(DMV 는 항상 `sys.` 자격 필요). 테이블·컬럼·별칭·리터럴 오발동은 원래 없음(2R 실증).
- **[2R MINOR — 반영]** 화이트리스트가 DB 스코프 정본 뷰를 과차단 → `partitions`(행수 관용구 `SUM(p.rows) … index_id < 2`)·`allocation_units`·`stats`·`sql_expression_dependencies` 추가. `database_files`/`database_principals` 는 파일경로·주체 노출이라 제외 유지.
- **[1R MAJOR ×4 — 반영]** ① `_cfg_active_default_db()` 가 **항상 AttributeError**(`get_active_datasource()` 는 dict 가 아니라 키 문자열) → 진단의 핵심인 현재 pin DB 가 죽고 pin 을 "다른 허용 DB" 로 오열거. 내 테스트가 monkeypatch 로 가리고 있었다 → `get_active_default_db()` 정본 사용 + 테스트를 실경로로. ② per-DB 실패 삼킴이 "3/3 로그인 실패"를 "검색 결과 없음"으로 위장하고 커버리지를 과대 단정 → 실패 DB 명시 + `N/M개` 표기 + 전량 실패 시 오류. ③ TOP 50 포화 무통지 → TOP 51 로 감지해 조건부 고지. ④ 루틴 타입 필터가 CLR/확장/복제필터(`PC`/`FS`/`FT`/`AF`/`X`/`RF`) 누락 → 부재 방지 도구 안의 새 허위 부재 → 필터·CASE 동시 확장.
- **[1R MAJOR ×2 · MINOR — 반영]** `keyword` 필수라 원 질문("몇 개나 있나") **열거 불가**인데 프롬프트는 수기 SELECT 금지 → 와일드카드 우회 유도 → `keyword` 선택화. RC-E 규칙이 무조건적이라 정당한 업무 0행까지 미확인으로 밀고 인접 규칙 2개(`:99` 0-row, `:105` targeted probe)와 모순 → **메타데이터/카탈로그 맥락 + 스코프 경고 동반 시**로 한정하고 targeted-probe 예외 명시. 루틴 빈 결과가 `search_tables` 를 권하던 오안내 제거, step 서술 매핑 3곳 등록, `search_routines` 제외 집합을 `search_tables` 와 동일 SSOT 로.
- **정직 이연(pre-existing — HEAD 동일, 이 변경이 만들지 않음)**: 임의 DB명을 테이블 별칭으로 가리는 함수 우회(`SELECT otherdb.dbo.fnLeak() FROM dbo.Orders otherdb`, 4-part `lnk.appdb.dbo.fn()`). 정적 집합으로 못 막고 수집기 구조 변경(면제된 Dot 체인을 버리지 않고 별도 반환 → catalog 게이트가 fail-closed 처리)이 필요. 2R 이 HEAD 좌우 대조로 pre-existing 확증. → FRICTION_LEDGER 후속 triage. **단 `sys` 앵커로 진입 장벽이 낮아졌던 부분은 별칭 그림자 수정으로 함께 닫혔다.**
- **REFUTED(2R 실측)**: 3-part 미허용/시스템 DB catalog·서버 스코프 뷰 18종·서브쿼리/CTE/UNION/파생/APPLY 중첩·인용/주석/대소문자 변형·다중문·`OPENROWSET`/`OPENQUERY` 전부 차단 유지. `collect_schema_object_refs` 가 빈 집합일 때 **차단 유지**(fail-closed) 실증. 화이트리스트 뷰의 DB 스코프성 문서 대조 확인. RC-D 진단문은 프롬프트가 이미 주는 정보(현재 DB·허용 DB)의 중복이라 신규 노출면 아님. keyword 인젝션 5종 무력(`_safe_ident`). `database` 인자 allowlist escape 불가. 기존 보안 테스트 **약화 흔적 없음**(순증 +21/−1, M1 단정 무변경).
- **검증**: 신규 `tests/test_false_absence_catalog_scope.py` **40건**(1R·2R 이 뚫은 경로 전부 회귀 가드 — 별칭 그림자는 `dm_` denylist 에 가려지지 않도록 `fn_` 계열로 작성) + `test_mssql_security_boundary.py` 강화(+21/−1). 컨테이너 `make test` **2,614건 중 2,608 PASS / 4 FAIL / 2 skip** — FAIL 4건은 이전 cycle 과 동일한 **pre-existing 환경 의존**분, 신규 실패 0. ruff PASS. 2R 이 worktree/HEAD 양쪽 전체 스위트를 돌려 실패 집합 **IDENTICAL** 확인.
- **라이브 실측 미수행(POST-DEPLOY)**: 동일 질문("masangsoftweb 문서 조회 프로시저 탐색")으로 `search_routines` 사용·"0개" 오판 소멸을 재현 확인해야 원장이 닫힌다.
- Cross-ref: CHG/TASK-20260728T114459-false-absence-catalog-scope · FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope · 선행 FR-mssql-crossdb-structured-discovery(같은 실패 모드의 구조화-도구 판 — 본 변경은 그 **누락된 형제**) · FR-false-truncation-belief(본 축을 라이브 실측으로 노출) · ANCHOR 0002 §1~§3 무충돌.

## REV-20260728T123229-false-absence-live-verified [SKIPPED:live-measurement-record-doc-only] — PASS
- 대상: FR-false-absence-zero-row-catalog-scope **라이브 재실측 전사** + 원장 `fixed:deployed:verified` 전이. **코드 변경 0**.
- 리뷰 방식([SKIPPED] 사유): 로직의 적대 검증은 REV-20260728T114459-false-absence-catalog-scope [SUBAGENT ×2 rounds] 에서 완료. 본 cycle 은 배포 후 측정치의 사실 전사라 추가 패널의 판별력이 없다.
- **측정의 반증 설계**: (a) 마찰을 촉발한 **동일 질문·동일 product·동일 모델**로 재현해 "조건을 만들고도 발동하지 않음" 을 확인 (b) 모델 답변뿐 아니라 **PG 도구 결과 실물**을 대조해 `search_routines` 실사용과 신규 문구 부착을 확인 (c) 우연히 발생한 **MSSQL 연결 단절**을 자연 실험으로 활용해 실패-고지 lever 가 실전에서 작동함을 확인(구 코드 대비 행동 차이가 결정적) (d) 배포본 런타임에서 보안 경계 4축(별칭 그림자·서버 스코프 뷰·시스템 DB·사용자 UDF 과차단)을 직접 실측.
- **판정**: 주 판정축(허위 부재) **verified**. 잔여는 pre-existing 이연 1건(임의 DB명 별칭 그림자 — HEAD 동일)만.
- Cross-ref: REV/CHG/TASK-20260728T114459-false-absence-catalog-scope · 재현 대화 `20260728031510-16927f9b` · PR #991.

## REV-20260728T124500-llm-usage-target-scope [SKIPPED:session-policy-no-subagent] — PASS

CHG-20260728T124500-llm-usage-target-scope.

### D1. 왜 별 컬럼인가 (target 접합·payload 삽입을 모두 배제)

- **target 에 접합**(`ds:schema.table`): `target` 은 표시용 자유 문자열이고 스코프는 **필터·조인 키**다.
  접합하면 조회마다 파싱이 필요하고 기존 표시가 깨진다(0032 가 task 와 target 을 분리한 것과 동형 논리).
- **프롬프트 payload 에 datasource 추가 후 거기서 읽기**: payload 는 `json.dumps` 되어 **모델 입력**이
  된다. 필드를 늘리면 프롬프트가 바뀌어 출력이 달라질 수 있고(§12.3 2차-효과), `semantic_cluster` 의
  라벨 캐시처럼 payload 파생 상태가 있는 곳에 무효화가 번질 수 있다. 계측 값을 모델 입력에 실어
  나르지 않는다 — **함수 인자**로 분리했다.

### D2. 명시 인자 + ContextVar 폴백 (둘 중 하나가 아니라 둘 다)

`_ACTIVE_DATASOURCE_KEY` 는 ContextVar 라 대화 in-process 병렬(WEB_PARALLEL_LIMIT)에서도 격리된다 —
`cfg.MEMORY_CONVERSATION_ID` 전역이 가진 race 문제가 없다. 그래서 insight 워커 사이클
(`insight.py` 가 datasource 마다 `set_active_datasource`)에서는 ambient 만으로 정확하다.
**단 ContextVar 는 새 스레드로 전파되지 않는다** — `node_analysis._run_llm`,
`semantic_cluster` 병렬 라벨링은 별 스레드에서 LLM 을 호출하므로 ambient 가 None 이 된다.
그 3곳만 명시 전달해 "대부분 자동 + 위험 지점 명시" 로 최소 침습을 유지했다.

### D3. 소급 백필하지 않는다

과거 행의 정확한 데이터소스는 복원 불가다. 역해소로 백필하면 **모호한 추정이 '기록된 사실'로
승격**되어, `scope_source` 로 기록/추정을 구분하는 의미 자체가 사라진다. legacy 행은 조회 시점
역해소(종전 동작)로 두고, 시간이 지나며 신규 행이 자연 대체되게 한다.

### D4. 웹 2단 폴백 + 컬럼 부재 자가치유 (배포 순서 무관)

expand-only 라 마이그·이미지·웹의 배포 순서가 어긋나도 죽지 않는다:
INSERT 는 4단 사다리로 컬럼을 줄여가며 재시도하고, SELECT 는 실패 시 리터럴 `''` 로 같은 인덱스를
채우는 폴백 SQL 로 재조회한다. 폴백 경로에서도 legacy 역해소가 살아 있어 **기능 저하가 종전 수준**
(0 이 아님)이다.

### D5. fold 키에 scope 포함 = 의도된 행 분리

`dbGame.PlayerMisc` 가 qa·dev 양쪽에서 분석되면 종전에는 한 줄(합산)로 뭉개졌다. 이제 두 줄로
분리된다 — 사용량을 데이터소스별로 보는 것이 이 컬럼의 목적이므로 이 변화가 곧 기능이다.
회귀 가드 테스트(R3)로 고정했다.

### 리스크·한계

- 신규 행만 채워지므로 **전환기에는 기록/추정이 혼재**한다. `scope_source` 로 구분 가능하나 UI 에는
  노출하지 않았다(운영자에게 의미 있는 구분이 아니고, 이동 정확도는 어느 쪽이든 최선을 다한다).
- `target_scope` 는 계측 값이라 **인가 결정에 쓰지 않는다** — 콘솔 스코프 select 의 초기값 힌트일 뿐,
  데이터 접근 자체는 기존 RBAC·product allowlist 가 통제한다.
- 테스트 더블 arity 7건을 함께 고쳤다(프로덕션 결함 아님). keyword-only 로 추가해 위치 인자
  호출부는 영향이 없다.
