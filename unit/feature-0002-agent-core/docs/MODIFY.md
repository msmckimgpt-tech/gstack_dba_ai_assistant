---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

> 이전 기록(109건): [MODIFY-archive-20260711T120311.md](./_archive/MODIFY-archive-20260711T120311.md)

## CHG-20260730T190000-review-proposed-change-framing (쿼리 리뷰 시간 방향 계약 + 미발견 분류 교정 힌트 + 루틴 본문 매칭 스니펫 — conversation_audit FR-review-frames-live-db-as-spec)
- Date: 2026-07-30. worktree `ai/root/feature-0002-agent-core`(base main bb4be6e4). 출처: `/_dqa:conversation_audit "SQL 쿼리 코드 리뷰"` 사용자 명시 호출. 범위 승인(AskUserQuestion 2026-07-30) = **A+B+C 전부 + search_routines 매칭 스니펫**.
- **무엇을(A 시간 방향 계약)**: `agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 신설 — 첨부가 **적용될 변경**(DDL/마이그레이션/신규·수정 루틴)이면 라이브 DB=**BEFORE**, 첨부 세트=**AFTER**. 변경이 스스로 도입하는 차이(아직 없는 객체, 바뀐 시그니처, 스크립트가 추가할 키/제약)는 **적용 전제이지 결함이 아니다** — 결함/문제/위험 어휘 금지, 🔴/🟡 배지 금지, "실행되지 않았다/실패했다" 단정 금지. `compose_system_prompt` 의 `parts` 에 always-append 해 **운영자 `WebSystemPrompts` global row 가 base 를 통째로 대체해도 살아남는다**(AUTH-1a 코드 권위선, `_ATTACHMENT_DELIVERY_DIRECTIVE` 와 대칭). SYSTEM_PROMPT §ATTACHED FILES 에 압축 미러 1줄 + 첨부 주입 INSTRUCTION 에 포인터.
- **무엇을(B 출력 구조 계약)**: 같은 상수 안에서 — 전제 항목은 "적용 전제 / 배포 순서" **한 절**에 사실로 기재, 심각도 배지·결함 목록은 **적용 후에도 남는** 문제에만. 리뷰 본문(논리·성능·키/인덱스·트랜잭션·보안·운영)은 적용 후 상태 기준으로 작성.
- **무엇을(C 도구 L2 짝)**: `tools._proposed_change_hint()` — 미발견 시그니처(`doesn't exist`/`Unknown column`/`Invalid object name`/1146·1054·1049 …)에만 붙는 **분류 교정** 3분기 힌트. ① 첨부가 만드는 객체면 적용 전제 ② 어느 첨부도 안 만들면 실제 선행 누락(결함) ③ 권한·스코프·대소문자/오타로도 미발견이 나므로 **교차확인 전에는 ①②로 단정 금지**(선행 0행≠부재 봉인 유지). 부착 3지점: `_tool_execute_sql` 오류 · `_tool_describe_table` 컬럼 0행 · `_tool_describe_routine` 정의 0행.
- **무엇을(scan 스니펫)**: `search_routines` 결과에 `MATCH_SNIPPET` 4번째 컬럼 — 본문 매칭 지점의 앞뒤 문맥(앞 40자~총 140자, 표 셀 120자 상한). MySQL `LOCATE/SUBSTRING/GREATEST`, MSSQL `CHARINDEX/SUBSTRING`. keyword 미지정(전체 열거)은 상수 `''`(LOCATE('')=1 무의미 머리말 회피). 종전에는 목록만 줘서 "왜 이 루틴이 걸렸는지" 알려면 후보마다 `describe_routine` 왕복이 필요했다.
- **파일**: `src/agent_core.py`(상수 1 + compose 주입 1줄 + SYSTEM_PROMPT 1줄 + 첨부 INSTRUCTION 1문장); `src/modules/tools.py`(힌트 3종 상수·`_proposed_change_hint`·`_routine_snippet_cell`·표 렌더 2경로·도구 설명); `src/modules/dialects.py`(MySQL/MSSQL search_routines + base docstring 계약); `tests/test_review_proposed_change_framing.py`(신규 27건).
- **왜**: 라이브 A/B 대조쌍 — 동일 5파일(sha256 일치)·동일 요청문이 3분 간격에 한쪽은 코드 리뷰(`…4348bc34`), 다른 쪽은 현재-DB 부재 지적 중심(`…a2efa955`)으로 갈렸다. 계약 부재로 프레임이 모델 재량이었다. `…b5f40d99` 는 미적용 마이그레이션을 "동적 ALTER 로직이 실행되지 않았거나 실패한 상태" 로 **허위 결함 단정**. corroboration structural(60일 SQL 첨부 96대화 중 12 distinct_conv).
- **호환/안전**: 프롬프트는 보간 없는 **정적 상수**(인젝션 표면 0), `_INJECTION_GUARD_NOTICE` 순서 불변. **라이브 대조 강제·부재 단정 금지 규칙은 그대로**(약화 0 — 회귀 테스트로 고정). 가드/allowlist/RBAC 경계 **무변경**: 스니펫은 `describe_routine` 이 이미 같은 채널로 반환하는 정의 본문의 **진부분집합**이고 같은 `_struct_schema_access_error` allowlist·RO GRANT 뒤에 있다. keyword 는 기존과 동일하게 `_safe_ident` 통과(codex 실측: 따옴표·백슬래시·대괄호 breakout 불성립). 표 컬럼은 스니펫이 전부 비면 종전 3컬럼 유지(열거 잡음 0·하위호환).
- **Rollback**: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 상수·주입 1줄·미러 2곳 제거 + `tools.py` 힌트/스니펫 헬퍼·호출 3+2지점 제거 + `dialects.py` MATCH_SNIPPET 2곳 revert + 테스트 제거. 스키마/마이그레이션 변경 없음.

## CHG-20260729T141200-runtime-settings-test-env-agnostic (cross-unit — 정본 feature-0003 TASK-20260729T1412)
- `tests/test_runtime_settings.py::test_missing_snapshot_is_fail_open`: `monkeypatch.delenv("AGENT_TIMEOUT_SEC")`
  추가. override 부재 시 baseline 이 **배포 env 우선**인 것은 `_baseline_int` 의 설계된 동작인데
  (운영 `.env` 의 300 을 존중해야 config.py 와 byte-동치), 테스트는 env 를 둔 채 스펙 리터럴 60 을
  요구해 `.env` 를 상속하는 컨테이너 테스트 환경에서 상시 FAIL 이었다. 검증 의도("스냅샷 부재 →
  폴백")를 보존하면서 env 의존만 제거.
- 코드(제품) 변경 0. 상세 근거·라이브 검증은 feature-0003 REVIEW REV-20260729T141200-test-live-db-isolation.

## CHG-20260722-dqa-data-grounding-and-scratch-csv (데이터 의미 grounding 지침 신설 + scratch_sql 결과 CSV export — DQA 마찰 B-1/D-1/D-2/F-5)
- Date: 2026-07-22. worktree `ai/claude/dqa-grounding-scratch-csv`(base main 66a48870). 사용자 요청(/_template:entry): `DQA_assistant_마찰개선사항_20260722_v2.md` 마찰 검토·개선. 스코프 승인(AskUserQuestion) = B-1 타임존 + D-1 ENUM + F-5 scratch CSV(E-5 대화누출은 병렬 세션 `feature-0019-xconv-leak` 담당이라 중복 회피).
- **무엇을(1) 데이터 의미 grounding 지침**: `agent_core._DATA_GROUNDING_GUIDANCE` 신설 — `_run_agent_core` compose 에서 `_ACTIVE_INTERPRETATION_GUIDANCE` 직후 **무조건(그룹 if-블록 밖) 주입**(1:1·그룹 공통). 3블록: (a) **타임존(B-1)** — 서버 TZ 설정(`@@time_zone` 등)은 저장 datetime 값의 기준 TZ 를 알려주지 않음(MySQL DATETIME 은 TZ 미저장); 서버 TZ 만 보고 "저장값=로컬시각" 단정 금지, 불확실 시 알려진 기준점 데이터 교차검증 + 변환 가정 답변 명시, 미확정 시 임의 offset 금지. (b) **ENUM/코드(D-1)** — 코드 의미 지어내기 금지, GLOSSARY & ENUM VALUES·`get_sample_rows`/`GROUP BY` 분포 grounding 또는 미보유 고백. (c) **분리저장(D-2)** — "전체 X" 요청 시 여러 컬럼/테이블 분리저장 커버리지 명시. `guidance_registry.py` 에 `data-grounding` 항목 등록(관리 콘솔 작동지침 목록 노출).
- **무엇을(2) scratch_sql CSV export(F-5)**: 과거 `scratch.run_sql` 이 미리보기 상한(200행)까지만 fetch·CSV 미저장 → 대량 cross-DS 병합 결과 회수 불가(execute_sql 과 비대칭). 이제 `run_sql` 이 export 상한(`AGENT_SCRATCH_MAX_RESULT_ROWS`=100000)까지 전체 fetch(+`export_truncated`), `_tool_scratch_sql` 이 execute_sql parity 로 `save_csv("scratch_resultset1", …)` → "CSV 저장: <path>" emit + 미리보기(execute_sql 표 포매터 50/adaptive) 절단 + 미열람 행 단정 금지 안내. 웹 UI 는 기존 `CSV_PATH_RE` 로 그 경로를 파싱해 다운로드 링크 생성(**프론트 무변경**).
- **파일**: `src/agent_core.py`(`_DATA_GROUNDING_GUIDANCE` 상수 + 주입 1줄); `src/modules/guidance_registry.py`(`data-grounding` 등록); `src/modules/scratch.py`(`_DEFAULTS['AGENT_SCRATCH_MAX_RESULT_ROWS']`=100000, `run_sql` 전체 fetch + `export_truncated`); `src/modules/tools.py`(`_tool_scratch_sql` save_csv parity + preview stats); `tests/test_gc_dialect_context.py`(grounding 3건), `tests/test_scratch.py`(CSV export 3건); docs(feature-0002 TASK, feature-0022 TASK-0014, FRICTION_LEDGER 3항목).
- **왜**: B-1 은 assistant 가 서버 TZ 설정을 저장값 의미로 오판해 집계 기간 전체를 9h 어긋나게 한 ★최우선 correctness 결함(전 시트 오염 위험). D-1 은 ENUM 코드 환각("3=Stamina", 정본 4). D-2 는 분리저장 부분집계 누락. F-5 는 대량 scratch 결과 회수 불가. 셋 다 게임-무관 일반 개선.
- **호환/안전**: grounding 은 항상 주입되는 advisory 프롬프트(가드/권한/파이프라인 불변, base·product 프롬프트 뒤 last-writer). scratch CSV 는 execute_sql 이 이미 쓰는 `save_csv`/`CSV_PATH_RE` 경로 재사용(신규 유출 표면 0 — scratch_guard·대화격리 불변); save_csv 실패는 try/except 로 미리보기 결과를 막지 않음. export 상한 100000 은 기존 반입 상한과 정합(메모리 bounded). 검증: 변경-특화 로컬 테스트(scratch+guidance) 37 PASS; make test 전체 스위트는 기존 비결정 flake(postgres-replica `--no-deps` DNS + 순서-의존 runtime_settings/attachment)로 main 기준선에도 다른 실패셋 존재 → 내 변경-특화 테스트는 양쪽 실패셋에 부재(회귀 0 확증).
- **Rollback**: `_DATA_GROUNDING_GUIDANCE` 상수·주입 1줄·registry 항목 제거 + scratch/tools 변경 revert + 테스트 제거. 스키마/마이그레이션 변경 없음.

## CHG-20260716-redteam-axis-rederive (자가검증 BLOCK 축 인지 재도출 — 텍스트 다듬기만 하던 revise 를 sql/max-completeness 는 도구 재추론으로 승격, Major §12.3 — core 답변 파이프라인·LLM 비용/지연)
- Date: 2026-07-16. worktree `ai/claude-corp/feature-0002-redteam-rederive`(base main). 사용자 요청(/_template:entry): "자가 검증을 통한 BLOCK 이 확인되었지만 별도의 재추론을 진행하지 않고 이미 구성된 답변을 다듬는 행위만 진행 후 제출". 구성 승인 = 세 요소 모두 취하되 completeness 재도출은 매우높음(max)에서만.
- **무엇을**: red-team 자가검증 revise 경로를 축 인지로 분기. 기존엔 모든 BLOCK을 `_rt_revise`(도구 없는 단발 텍스트 재작성)로만 고쳐, `sql`(틀린 쿼리)처럼 새 근거 필요 결함은 못 고치고 다듬기만 했음. 이제 `sql`(항상)·`completeness`(매우높음)는 `_rt_rederive`(도구 허용 재추론)로 승격.
- **파일**: `src/modules/redteam.py`(`_REDERIVE_ALWAYS_AXES`/`_REDERIVE_LEVEL_GATED_AXES`·`_rederive_enabled`/`_rederive_eligible_axes`/`_block_rederive_axes`·`build_rederive_instruction`·`orchestrate_review(rederive_fn=)` 라우팅 루프+evidence 재계산·`record_review`/meta 확장); `src/agent_core.py`(`_rt_rederive` 상한 도구 루프 신규 — `_run_tool_defs`+`execute_tool` 재사용, `REDTEAM_REDERIVE_MAX_TOOL_ROUNDS` 상한, 마지막 라운드 tools=None, 라운드당 도구 3개 cap, 보안 `_datamark_untrusted`+4000자 truncation 미러, evidence 호환 step, fail-open + 배선); `shared/runtime_settings.py`(`REDTEAM_REDERIVE_ENABLED`1·`_MAX_TOOL_ROUNDS`3·`_COMPLETENESS_MIN_LEVEL`3 live); `alembic/.../20260716_0043_redteam_rederive_columns.py`+MAX_MIGRATION+`scripts/agent_runtime_schema.sql` 미러(redteam_reviews 3컬럼 additive).
- **왜**: `sql`/`completeness` BLOCK을 다듬기로 "고치면" 헤징 강등·BLOCK 미해소·근거없는 정정(새 grounding 위반 주입) 중 하나로 귀결. 실제 도구 재실행 재추론만 정정 가능.
- **호환/안전**: grounding/permission/honesty 는 기존 텍스트 재작성 유지(무회귀). 재추론 무산출/비활성(`REDTEAM_REDERIVE_ENABLED=0`)/예외는 텍스트 재작성으로 폴백(fail-open 불변). completeness 는 사용자 결정대로 max(ordinal 3)에서만 승격 — 모호축 비용/드리프트 위험을 최대사양 티어로 국한. migration additive expand-safe·GRANT 불필요(ADD COLUMN 상속). 검증: 전체 스위트(0002+0003) 2145 passed/2 skipped/RC=0 회귀 0.

## CHG-20260716-graph-search-content-match (그래프 뷰 검색 매칭 확장 — 컨텐츠 카테고리 + AI 능동 분석 본문, Minor §12.3; 교차 feature-0016 정본)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0016-graph-search-content`(base main). 사용자 요청(/_template:entry): "그래프 뷰 내부에서 검색을 진행할 때, '테이블, 컬럼, 용어' 뿐만 아니라, 컨텐츠 카테고리 및 AI 능동 분석을 통해 얻은 내용 또한 매칭될 수 있도록 구성해주세요."
- **컨텍스트**: 그래프 뷰 검색은 서버사이드 정본이다 — 프론트 `_metaGraphSearch`(feature-0003 `graph-ctxmenu.js`)는 `/api/admin/metadata/graph?q=` 를 호출하고 반환 노드를 그대로 렌더·글로우한다. 실제 매칭은 `search_nodes()` Cypher 가 담당하며 기존엔 `n.name`/`n.fqn` CONTAINS 만이었다. "컨텐츠 카테고리" = §78~81 컨텐츠 단위 그룹(= AGE 노드 `semantic_cluster_label`, sim-group LLM 라벨). "AI 능동 분석 내용" = `node_analysis_jobs.analysis`(feature-0016 §69/ADR-034 — agent_kb 관계형 테이블, AGE 정점 아님). 프론트가 임의 매칭 노드를 이미 처리하므로 **백엔드 단독 변경**으로 요청 충족(활성 세션 `graph-ctxmenu.js` 편집과 스코프 충돌 회피).
- **변경**: `src/modules/metadata_graph.py`
  - `search_nodes()`: Cypher WHERE 를 `((toLower(n.name) CONTAINS q OR toLower(n.fqn) CONTAINS q OR toLower(n.semantic_cluster_label) CONTAINS q){key_clause}){scope_clause}` 로 확장. (1) `semantic_cluster_label` CONTAINS = 컨텐츠 카테고리 매칭(AGE 노드 프로퍼티; `toLower(null)`=null 은 openCypher OR 에서 무시 → 비클러스터 노드 오포함 없음). (2) `key_clause` = 아래 분석 매칭 `node_key` 를 `n.key IN [ '<key>', ... ]`(`_cq` 인용, injection-safe) 로 합류. RETURN 9컬럼(+`semantic_cluster_label`), `_cypher(..., 9)`.
  - 신규 `_analysis_match_keys(cur, query, scope, limit)`: **동일 `_ro_conn` 커넥션**(AGE 그래프 `metadata_kb` 와 `node_analysis_jobs` 둘 다 agent_kb DB)으로 `SELECT DISTINCT node_key FROM node_analysis_jobs WHERE status='done' AND analysis IS NOT NULL AND position(%s in lower(analysis::text))>0 [AND scope_key=%s] LIMIT %s`. 전부 psycopg bind param(injection-safe), `position()`=LIKE 와일드카드/ESCAPE 없는 대소문자 무관 부분일치, `::text` 로 text/json/jsonb 저장형 무관, 1자 질의 스킵(노이즈·풀스캔 방지), 권한/컬럼 부재·실패 시 `[]`(graceful degrade → 이름/카테고리 매칭만 유지).
  - `_node_dict`: row[8] 존재 시 `cluster_label` 부여(len(row)>8 가드 — 다른 호출처 없음, search_nodes 전용).
  - 매칭 근거 `match_via`(name/category/analysis 다중) 노드에 부여 — 이름/카테고리는 반환값 재확인, 분석은 key 집합 판정. pg_trgm score 를 `GREATEST(similarity(name,q), similarity(fqn,q), similarity(cluster_label,q))` 로 확장(카테고리 매칭이 이름 매칭에 밀려 cap 절단되지 않도록 랭킹 보정; analysis-only 매칭은 score≈0 이나 결과·글로우 유지).
- Why: 사용자가 컨텐츠 카테고리·AI 분석에서 발견한 개념으로 노드를 찾을 수 있어야 하는데, 검색이 이름/FQN 만 봐서 그 축이 사각지대였다. 두 정보 모두 검색 응답 payload 에 없었으므로 매칭은 반드시 백엔드(Cypher/직렬화·분석테이블 조인) 확장이 선행돼야 한다.
- Impact: 검색 경로만 확장(neighborhood/scope_roots/schema_tables 등 다른 모드 무변경). name/fqn-only 매칭 동작 보존(회귀 0). 모든 검색이 `node_analysis_jobs` position() 스캔 1회 추가(admin 읽기·300ms 디바운스·`status='done'` 필터·1자 스킵 — 허용, 필요 시 후속 trigram GIN 인덱스). `_SEARCH_CAP`(80) 불변 — 매칭 소스 증가로 상한 도달 확률↑(UI '결과 상한' 안내 기존).
- Rollback: `search_nodes` Cypher/RETURN revert + `_analysis_match_keys`·`_node_dict` row[8] 제거 + 테스트 제거. 다른 경로 영향 0. 스키마/alembic 변경 없음.
- Deploy: web 재빌드(metadata_graph 는 web import). alembic/스키마 변경 없음.
- Cross-ref: feature-0016-metadata-graph(그래프 뷰 정본, §78~81 컨텐츠 카테고리 / §69 node_analysis) TASK/REPORT cross-ref · feature-0003 `graph-ctxmenu.js` `_metaGraphSearch`(프론트 소비, 무수정) · REV-20260716T010620-graph-search-content-match.

## CHG-20260715-llm-probe-thinking-budget (LLM provider 헬스 probe 오탐 — stale "요청량 한도/사용량 소진" 배너 고착 해소, Major §12.3 — LLM 라우팅·외부 비용)
- Date: 2026-07-15. 별도 worktree `ai/claude/feature-0002-llm-health-probe`(base main). 사용자 요청(/_template:entry): "assistant 가 내부 인사이트·답변 시 claude-corp 계정 사용량 소진 메시지가 뜨는데 실제로는 허용량이 남아있다 — 원인 파악·수정".
- **근본원인(재현 확정)**: `probe_provider`(active health probe, web `/api/llm/health` 60s 폴링)가 `OPENAI_MODEL`(운영값 `claude-haiku-4-interactive`)로 `max_tokens=1` ping 을 보낸다. 그러나 이 alias 는 litellm config(`feature-0007 litellm_config.yaml`)에서 `thinking.budget_tokens: 5000` 을 강제 → Anthropic 제약(`max_tokens > thinking.budget_tokens`) 위반 → **항상 400**. `classify_llm_provider_error` 는 이 400 을 **None** 으로 반환(실제 실행 검증: 대표 400 3종 모두 None) → probe 가 `record_provider_ok` 도 `record_provider_restricted` 도 못 남긴다. 결과: 배너를 끄는(clear) 유일한 자동 경로(probe)가 무력 → claude-corp 이 순간 429(burst)로 sticky `restricted` 를 한번 기록하면(정상), 계정 회복 후에도 성공 답변이 발생하기 전까지 **배너가 영영 stale 로 고착**. (auto-memory `llm-routing-interactive-split` "thinking budget > max_tokens 오진" 함정과 일치.)
- **변경**: `src/modules/llm_provider_health.py`
  - 모듈 상수 `_PROBE_THINKING_BUDGET = 1024`(Anthropic budget 하한) 추가.
  - `probe_provider`: `create` 인자를 `create_kwargs` 로 조립. `model_supports_thinking(model)`(claude-*)이면 `extra_body={"thinking":{"type":"enabled","budget_tokens":1024}}` + `max_tokens=1088`(>budget, 400 회귀 방지)로 **valid ping** → 성공 시 `record_provider_ok` 가 stale 배너를 실제 해소. 비-thinking 모델(로컬 gemma/edge)은 `max_tokens=1` 유지(최저 비용). thinking override 는 `_call_llm` 이 이미 쓰는 검증된 메커니즘(test_reasoning_effort) 재사용.
  - `probe_provider` **recovery-only gate**(적대 리뷰 CONCERN 흡수 REV-20260715): 비-force probe 는 `state=restricted`(복구 감지 필요)일 때만 실제 valid-ping; `ok/unknown` 은 실제 호출 없이 cached 반환. → idle 정상 폴링이 claude-corp 5h rolling 윈도우를 재고정하지 않게(refresh-claude-oauth-token.sh cron-probe 제거 원칙 정합). 정상 상태 새 제한은 reactive(agent_core) 가 잡고, force(사용자 재시도)는 gate 우회.
  - `tests/test_llm_provider_health.py`: `test_probe_thinking_model_sends_valid_max_tokens_over_budget`·`test_probe_non_thinking_model_uses_minimal_max_tokens` + recovery-only gate 4건(ok/unknown skip·restricted ping·force bypass). 파일 **37 passed**.
- Why: probe 는 배너 자동 복구 메커니즘인데 thinking-강제 alias 도입(interactive-split 2026-07-04) 이후 max_tokens=1 이 구조적으로 항상 400 이 되어 그 역할을 못 했다. 유효 요청으로 바꿔 자동 해소 복원 + recovery-only gate 로 정상 시 실호출 억제.
- Impact: classify/영속 스키마/HTTP/TTL·stampede 가드 무변경. probe 실제 claude 호출은 **restricted(outage) 창 또는 force 일 때만**(≤~1088 output) — 정상 idle 폴링은 실호출 0(윈도우 재고정 없음). 비-thinking·정상 경로 무회귀.
- Rollback: probe 의 create_kwargs 분기 revert(→ max_tokens=1) + 상수/테스트 제거. 다른 경로 영향 0.
- Deploy: web 재빌드(agent_core 모듈은 web import). alembic/스키마 변경 없음.
- Cross-ref: REV-20260715T120000-llm-probe-thinking-budget / feature-0007 litellm_config.yaml(thinking budget) / CHG-20260625T045450-limit-subject-msg(동일 배너 메시지 계보).

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
## CHG-20260714T161500-mssql-crossdb-structured-discovery (MSSQL 구조화 발견 도구 DB(catalog) 인지 — Critical §12.3)
- Date: 2026-07-14. **conversation_audit** 진단(FR-mssql-crossdb-structured-discovery). **증상**: SQL Server 제품에서 assistant 가 실제로 존재하는 객체(테이블/컬럼/루틴)를 "검색 결과 없음/빈 구조"로 오판하고 give-up(product 117 대화 20260714065456-d705e0c7 외 다수 — 사용자 "다시, 제대로 검토해주세요" 명시 불만).
- **근본원인(RC-1, L4↔L8 + L1/L2)**: SQL Server 의 `INFORMATION_SCHEMA`/`sys` 카탈로그 뷰는 **DB(catalog)별**이라(MySQL 의 인스턴스-전역 information_schema 와 비대칭), 구조화 발견 도구(`search_tables`/`describe_table`/`describe_schema`/`list_schemas`/`get_sample_rows`/`get_table_indexes`/`get_foreign_keys`/`describe_routine`)가 pin 된 primary DB(`allow_dbs[0]`, SortOrder 첫 DB)의 카탈로그 하나만 조회했다. 제품 데이터는 수십 개 DB(product 117 = `Shop`/`9DRAGONS_ITEM`/`CASHITEMDB`… 30여 개, 전부 allowlist 멤버·freeform 3-part 로 도달 가능)에 분산 → primary 밖 객체는 도구로 발견 불가. `schema_name` 파라미터가 DB 를 스키마로 오인하게 만듦(관측: describe_table 빈-헤더 schema 인자가 대부분 DB명 — Shop/dk_game_release_233/9dragons_community…). 빈 결과에 교정 힌트 부재로 give-up 유발. **삼각측량**: 코드(도구 SQL 스코프) + PG 대화집계(MSSQL 29대화 중 11 ~38% describe_table 빈-헤더, 오늘까지 structural) + **라이브 QA 서버 재현/수정검증**(mssql-web-qa: primary `_INDY_STATISTIC` 에서 `Shop.dbo.T_ItemInfo`(15컬럼)·`L_Item_Buy_Log` 미발견 → `[Shop].INFORMATION_SCHEMA` 3-part 로 발견 확인).
- **봉인(재발경로=capability gap → 도구를 실제 도달 가능하게)**: 구조화 발견 도구를 **DB(catalog) 인지**로 전환. (1) `dialects.py` MSSQLDialect 전 발견 메서드에 `db`(catalog) 파라미터 + `_cat(db)` 3-part 접두(`[db].sys.*`/`[db].INFORMATION_SCHEMA.*`, describe_columns 는 실스키마 미상 시 스키마 필터 생략·테이블명 매칭, routine_definition 은 OBJECT_ID 3-part). base/MySQL dialect 은 `db=""` 무시(information_schema 인스턴스-전역 — 골든 회귀 0). (2) `tools.py`: `_mssql_resolve_catalog`(schema_name↔DB 재해석·`database` 인자·`db.schema` 분해·허용DB 검증·시스템/내부 DB fail-closed), `_mssql_effective_allow_dbs`, `_mssql_resolve_table_schema`, `_mssql_struct_target`, `_mssql_crossdb_hint`(빈결과 L2 교정). `search_tables` 는 대상 DB 미지정 시 **허용 DB 전체 검색**(per-DB graceful, CAP 40·초과 명시) → DB-qualified 반환. describe/schema/sample/indexes/fk/routine/list_schemas catalog-aware. (3) TOOL_DEFINITIONS 에 `database` 파라미터 + 설명. (4) `agent_core.py` `_MSSQL_DIALECT_GUIDANCE` 에 다중 DB 발견 지침(L1 정합). **보안 경계 불변**: 유효 허용 DB(allowlist − 시스템 − 내부)만 도달(freeform 3-part 가 이미 도달하는 범위와 동일 — RO GRANT backstop), 시스템 DB/스키마·agent_memory 차단 유지, `_safe_ident`+allowlist 이중 방어.
- **검증**: 신규 `tests/test_mssql_crossdb_discovery.py`(33 test — dialect 3-part 생성·MySQL 골든 db-무시·resolver 재해석/거부·cross-DB 검색·교정힌트·describe_table 3-part) + 전체 회귀 **1967 passed/2 skipped/0 failed**. 라이브 QA(mssql-web-qa): `describe_columns([Shop],T_ItemInfo)`=15컬럼·`search_tables('Buy',Shop)`=`L_Item_Buy_Log`(사용자 작업 참조 테이블) 발견. **라이브 대화 실측**(실제 리뷰 대화에서 발견 성공)은 배포 후 다음 audit corroboration(MSSQL describe_table 빈-헤더율 감소) 재측정 시 `verified`.
- 위험등급 **Critical**(§12.3 데이터소스 접근 모델) — 사용자 AskUserQuestion 승인(2026-07-14, "완전 DB인지"). §18.8 적대 패널(security+backend+qa) 결과 REVIEW.md 기록.
- Cross-ref: FRICTION_LEDGER `FR-mssql-crossdb-structured-discovery` · REVIEW REV-20260714T161500-mssql-crossdb-discovery · ANCHOR 0002 §1~§3(core LLM tool 경로·모듈 배치) 무충돌.

## CHG-20260714T171000-mssql-crossdb-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-14. CHG-20260714T161500-mssql-crossdb-structured-discovery 후속 — PR #790 merge(main `b364e964`) 후 배포 완료.
- 배포: `sudo -E bin/deploy-web.sh`(=deploy-all) 무중단 롤아웃 — web-a/web-b 롤링(git_commit=b364e964, soak 90s 통과·롤백 0) + insight-worker/ask-worker 재빌드(mysql-ai-agent:b364e964) + gateway reconcile(드리프트 0). **4서비스 GIT_COMMIT=b364e964 healthy**. **배포 이미지 baked end-state 실증**(deployed `/app/modules/dialects.py` 직접 로드, mssql-web-qa): `describe_columns([Shop],T_ItemInfo)`=15컬럼 · `routine_definition(schema='',db='Shop')`=1345자(`[Shop].sys.sql_modules` cross-DB) · sys.sql_modules 사용 True.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(MSSQL 발견 빈결과율 감소)은 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-mssql-crossdb-structured-discovery · REV-20260714T171000-mssql-crossdb-deploy.
## CHG-20260714T063200-partial-evidence-grounding (부분 증거 전수 단정 환각 봉인: 절단 미리보기 epistemics + byte-bounded 확장 + grounding 계약, Major §12.3, conversation_audit FR-partial-evidence-false-verification)
- Date: 2026-07-14. `/_dqa:conversation_audit "첨부파일과 실제 DB 비교 검증"` — 사용자 보고: 첨부파일↔답변 간 환각 극심.
- Reason(RC, 코드+DB+전사 삼각측량 high): 진단 대화 …e6add7f1 에서 ① `execute_sql` 50행 미리보기 절단이 분석 과업에 비가시(안내문이 표시 지침 "CSV 링크 제공"뿐) → 183행 중 gunzlog 전량 미열람 상태로 "전수 검증" 서술 + 첨부에 실재(141행)하는 `TRUNCATE charactermakinglog` 를 "누락" 오진(ground truth sha256 대조 확증) ② 정정 턴도 61행/50행 절단으로 동일 기전 반복 ③ `@@lower_case_table_names` denylist 거부에 교정 힌트 부재 → 문서상 기본값(0) 추측 → 실측(1)과 반대 결론(대소문자 CRITICAL 오진). 재발경로 = model limit → **입력·거부 피드백 정형화(L2) + 표시 캡 구조 보정 + 프롬프트 grounding 계약(L1)**. corroboration: 30d tool 대화 46 중 절단 노출 8(17%) structural surface; '환각' 명시 불만은 90d 내 이 대화가 최초.
- 사용자 승인: **PLAN-APPROVED A+B+C+D 전부 + PR/배포 인가**(AskUserQuestion 2026-07-14). Major(코어 LLM 경로; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님). **rebase 재평가로 D 는 출하 철회**(아래 dead-code 사유).
- Changes(feature-0002):
  - `src/modules/tools.py` — (A) execute_sql 절단 안내문을 epistemic 자기교정형으로 확장(실표시 행수 명시·미열람 행 단정 금지·WHERE/집계/NOT IN 재조회 유도·CSV 모델 비가독·기존 "답변에 전체 표 삽입 금지 + CSV 링크" 표시 계약 유지). `_format_result_sets` 절단 마커에 "미열람·단정 금지" 부기.
  - `src/modules/tools.py` — (B) `_format_result_sets(expand_rows, expand_char_budget, stats)` 확장: 소형 결과는 캡(50) 너머 char-budget(12,000자)·행수 상한(500) 내 전부 표시 — 목록 대조·누락 검증이 미리보기 안에서 종결. 광폭/대형은 기존 캡 유지(컨텍스트 보호 의도 불변). 다른 caller(get_sample_rows 등) 는 expand 미전달로 종전 동작.
  - `src/agent_core.py` — (C) SYSTEM_PROMPT "HANDLING RESULTS — NEVER FABRICATE" 4규칙 추가: PREVIEW-TRUNCATED(미열람 행 단정 금지·재조회)·ABSENCE/COMPLETENESS(완전 근거 없으면 "미확인" 명시)·COMPARING attachment↔DB(양측 조회 선행)·SERVER OPTIONS(문서 기본값 추측 금지 — `@@var`/SHOW VARIABLES 로 실제 값 조회).
  - **~~(D) `_server_variable_redirect`~~ — 출하 철회(정직)**: 애초 계획은 `@@` denylist 거부에 SHOW VARIABLES 유도 힌트였으나, 본 cycle rebase 시점에 병렬 세션 **CHG-20260714T153113-sysvar-select-guard (FR-sysvar-select-denylist-overblock)** 가 MySQL `@@` denylist 를 아예 제거해 `SELECT @@var` 가 sql_guard 를 통과(거부 안 됨) → "거부 시 힌트" 분기가 **dead 경로**. dead code 출하 대신 함수·호출·테스트 삭제. 애초 진단 ③번(@@lower_case_table_names 거부→기본값 추측)은 그 가드 허용 + 본 (C) "실제 값 조회" 계약으로 커버. 회귀 가드 `test_server_variable_redirect_removed`.
- Recurrence sealing: 부분 증거(절단)가 전수 단정의 입력이 되는 경로를 3면에서 봉인 — 구조(B: 소형 결과는 애초에 절단 없음) + 피드백(A: 절단이 자기교정 정보를 동봉) + 계약(C: 부재/전수 단정에 근거 요구·서버 옵션 실측). **보안 회귀 0**: sql_guard 허용범위·denylist·CSV 저장 경로·표시 계약 불변.
- 검증: `tests/test_partial_evidence_grounding.py` 신규 10 PASS(D 테스트 3 제거·회귀가드 1 추가) + 전체 회귀 pytest EXIT=0(feature-0002+0003, mysql-ai-agent 컨테이너). §18.8 적대 패널 → REV-20260714T063200-partial-evidence-grounding.
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification · **FR-sysvar-select-denylist-overblock**(병렬 세션이 같은 대화 …e6add7f1 의 ③번 @@ 근본을 가드-허용으로 처리 — 본 D 철회의 근거) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260714T210000-attach-review-grounding (첨부-답변 정합성 실데이터 감사 후속: 첨부섹션 grounding 모순 제거 + LLM 오류 분류 2종 확장, Major §12.3)
- Date: 2026-07-14. 계기: 사용자 요청 "실제 파일첨부 대화에서 답변이 첨부 내용과 정합한지" 실데이터 감사(PG `agent_runtime.core_attachments` 411첨부/81대화 + MinIO 대조).
- Reason(RC, 코드+DB+대화 삼각측량): 감사 결과 **컨텍스트-초과 에러 0건**(전 첨부 소형 — text 최대 12.7KB / 대화 누적 최대 58KB ≈ 15K토큰 vs ~200K). 선행 "토큰-초과 대응방안(청킹/RAG/1M모델)"은 현 마찰 미해소(존재하지 않는 문제) — 지적 정직 전환. 실 정합성 실패의 진짜 축: ① ingest/kind 라우팅(최근 대체로 해소) ② 접근·세션창(보안 민감) ③ 환각(파일↔실DB 미검증 단언) ④ 모델 alias/오류 raw 표면화. 자율 우선순위로 ③(모순 제거분)·④ 착수.
- 사용자 승인: **PLAN-APPROVED** (사용자 "우선순위 자율 선정 + 개선 계획 수립 + cycle-finalize 까지 진행", 2026-07-14). Major(코어 LLM 프롬프트·오류 경로; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님).
- Changes(feature-0002):
  - `src/agent_core.py` — (③) `_build_attachment_context_section` 첨부 리뷰 INSTRUCTION 에서 전역 SYSTEM_PROMPT grounding 규칙(L103 "COMPARING an attachment against the live DB: fetch BOTH sides ... Never narrate the current-DB side from assumption or memory", 병합 PR #793 CHG-20260714T063200)과 **직접 모순**되던 억제 문구("answer about it directly and do NOT run execute_sql against your own database unless the user explicitly asks")를 제거. 순수 코드리뷰=DB 불필요 유지, 실 DB 상태 주장=전역 규칙 위임(검증 선행·기억 단정 금지). **전역 grounding 을 중복 신설하지 않고** 첨부 섹션이 이를 무력화하던 latent 모순만 봉인.
  - `src/modules/llm_provider_health.py` — (④) `classify_llm_provider_error` 요청-레벨 400 버킷 2종 신설: `KIND_BAD_MODEL`(`_BAD_MODEL_PAT` — litellm "Invalid model name passed in model=auto/core/edge"·OpenAI model_not_found), `KIND_CONTEXT_LENGTH`(`_CONTEXT_LEN_PAT` — Anthropic "input length and max_tokens exceed context limit"·OpenAI "maximum context length"·Bedrock "input is too long" 통합). raw 400 덤프 → 친절 한국어 메시지(bad_model=관리자 라우팅 설정 안내, context_length=첨부 분량 축소 유도). 판정 순서 cred→bad_model→context_length→auth→throttle→unavail. provider 장애 아님 → `persist_health=False`(`_REQUEST_LEVEL_KINDS`) 로 글로벌 health 미오염(기존 confirmed=False skip 과 이중 안전망).
  - `src/agent_core.py` — (④ caller) ask 루프 오류 핸들러에 `if _restr.get("persist_health", True): record_provider_restricted(...)` 게이트 — 요청-레벨 오류가 글로벌 provider 배너를 오탐 점등하지 않게.
- Recurrence sealing: ③ 첨부 섹션이 전역 grounding 규칙을 무력화하던 모순 제거(파일↔실DB 미검증 단언 경로 봉인, FR-partial-evidence 전역 규칙과 상보). ④ raw provider 400 덤프가 사용자에 노출되던 경로를 분류-치환으로 봉인 + 요청-레벨 오류의 글로벌 health 오염 차단. **보안 회귀 0**: 첨부 datamark 센티널·RBAC·sql_guard·error_tag 비밀 비유출 불변(친절 메시지는 정적 한국어 상수).
- 검증: `tests/test_attach_grounding.py` 신규 5 + `tests/test_llm_provider_health.py` 확장 8 PASS. feature-0002 전체 회귀 로컬 EXIT=0(신규 실패 0). §18.8 적대 패널(security/prompt-injection + backend/correctness) → REV-20260714T210000-attach-review-grounding.
- Cross-ref: **CHG-20260714T063200-partial-evidence-grounding**(③ 전역 규칙 정본 — 본 변경은 그 규칙을 무력화하던 첨부 섹션 모순을 마감, 상보) · ANCHOR 0002 §1~§3 무충돌 · deferred(별도 cycle): ④근본 alias 누출 추적 · ① text-inline 회귀테스트 · ② share-window 접근·세션창.

## CHG-20260714T221500-attach-case-insensitive-grounding (라이브 실측 잔존 false-missing 봉인: 식별자 대소문자 정규화 비교, Major §12.3)
- Date: 2026-07-14. 계기: **라이브 실측(FR-partial-evidence 직접 재현)** — 원 마찰 입력(첨부 2개·conv …e6add7f1·P-119)을 배포본(ask-worker `GIT_COMMIT=244e6bec`, Cycle A grounding)의 실 `agent_core`+실 gunzgame/gunzlog DB 로 격리 재현. 원 증상(`charactermakinglog` "누락 ❌")은 소멸했으나 **잔존 false-missing 1건 발견**: `gunzlog.LoginEventLog`(첨부 162행 활성 `TRUNCATE` 실재)를 "초기화 쿼리에 없는 누락"으로 오판·중복 추가 권장.
- Reason(RC, 코드+첨부+DB 삼각측량): `LoginEventLog` 는 첨부 활성 131개 TRUNCATE 중 **유일한 CamelCase** 테이블(나머지 전부 소문자). 실 DB 는 `lower_case_table_names=1` 로 `logineventlog`(소문자) 반환 → 모델이 DB 소문자명을 첨부 CamelCase 표기와 **대소문자 구분 비교** → case-only 차이를 absence 로 귀결. 유일 오판 테이블 = 유일 CamelCase 라는 상관이 근본을 지시. SYSTEM_PROMPT grounding 계약(L102 ABSENCE 근거·L103 양측 조회·L104 서버옵션 실측)에 **식별자 대소문자 정규화 비교 지침 부재**(L250-251 은 "표기 보존"=쿼리 작성용이라 매칭 시 case-fold 미안내).
- 사용자 승인: 라이브 실측 결과 표면화 후 **"잔존 먼저 조사·수정 후 함께 배포"** 명시 선택(AskUserQuestion 2026-07-14). Major(코어 LLM 프롬프트 grounding; sql_guard·RBAC·PII 불변 → Critical 아님).
- Changes(feature-0002):
  - `src/agent_core.py` — SYSTEM_PROMPT grounding 계약(L102 ABSENCE 규칙 직후)에 "IDENTIFIER CASE" 규칙 신설: SQL 식별자는 서버가 흔히 case-fold(MySQL `lower_case_table_names=1` → 소문자)하므로 같은 객체가 첨부에선 `LoginEventLog`, 도구에선 `logineventlog` 로 나타날 수 있음 → case-only 차이는 **그 자체로 absence 근거 아님**. "누락/missing/파일·쿼리에 없음" 단정 전 첨부를 **case-insensitive(case-fold) 검색**(또는 targeted probe) — exact-case 스캔만으로 absence 결론 금지. 동일시(equating)는 lower_case_table_names=1 실측 확인 시로 **조건화**(lcase=0 서버 거짓 동일시 방지·L105 SERVER OPTIONS 정합, REV-20260714T221500 NIT).
  - `src/agent_core.py` — (패널 MAJOR-driven, ③ 완결) 정적 SYSTEM_PROMPT `## ATTACHED FILES` 섹션(L112-116)의 잔존 억제("Do NOT run execute_sql ... unless the user explicitly asks" + "These attachment instructions take precedence over the general 'query the database' guidance")를 제거·전역 규칙 위임으로 교정. **적대 패널이 CHG-20260714T210000 ③ 의 불완전성 적발** — 동적본만 고치고 이 정적본("takes precedence")을 남기면 verify 지시를 이겨 환각 경로 유지. 이제 정적·동적 양쪽 정합(REV-20260714T210000 MAJOR).
  - `src/modules/llm_provider_health.py` — (패널 MINOR-driven, ④ 강화) `classify_llm_provider_error` status 게이트 `_req_ok` 에서 `status is None` fallback 제거 → status 잃은 throttle/auth 예외가 토큰/모델 어휘로 요청-레벨 오분류돼 provider-health 배너를 억제하던 gap 봉인(REV-20260714T210000 MINOR-1).
- Recurrence sealing: model-limit(대소문자 구분 스캔)로 인한 false-missing 을 grounding 계약의 case-fold 비교 규칙으로 봉인 + ③ 정적/동적 억제 모순 완전 제거 + ④ status 게이트 강화. 프롬프트/분류 레버(첨부↔DB 대조는 모델 추론이라 결정론적 코드 lever 부재). **보안 회귀 0**: sql_guard 허용범위·RBAC·PII·datamark 센티널·error_tag 비밀 비유출 불변.
- 검증: `tests/test_attach_grounding.py` +5(case 3 + 정적억제 제거·전역위임 2) = 파일 10 PASS · `tests/test_llm_provider_health.py` +3(status 게이트 회귀) PASS. 로컬 대상 테스트 41 PASS. **`make test`(agent 컨테이너 feature-0002+0003 전체)**: 이 cycle 자체 테스트 전부 PASS, **무관 4건 pre-existing/환경 실패**(`postgres-replica` DNS 미해석[--no-deps DB 부재] 2 · `AGENT_TIMEOUT_SEC=300` 컨테이너 env vs 테스트 기대 60 2) — 이 cycle changeset 8파일에 해당 코드경로(config/node_analysis/runtime_settings) 무포함 → base 57f21121 byte-동일 실패로 연역 확정, **신규 회귀 0**. §18.8 적대 2렌즈 패널 → REV-20260714T221500 + REV-20260714T210000(MAJOR1·MINOR2 전건 수정).
- Cross-ref: **FR-partial-evidence-false-verification**(라이브 실측 결과 원장 기록 — 본 수정이 그 잔존 false-missing 계열을 봉인) · **CHG-20260714T210000**(같은 cycle·함께 배포) · ANCHOR 0002 §1~§3 무충돌.
## CHG-20260714T233000-attach-table-coverage (라이브 실측 잔존 false-missing 결정론적 코드 봉인: 첨부↔실DB 테이블 커버리지 도구, Major §12.3)
- Date: 2026-07-15. 계기: CHG-20260714T221500(case 프롬프트 레버) 배포 후 **라이브 재-재현(배포본 ee3424c3)** 에서 잔존 확인 — 모델이 case 를 인지하기 시작했으나(diff 에서 `LoginEventLog`↔`logineventlog` 언급) 여전히 요약표에 `LoginEventLog` 를 '누락'으로 오기재 + `lower_case_table_names` 미실측으로 불필요 정규화 제안. 프롬프트 레버는 확률적 완화에 그침(model-limit).
- Reason(RC): 첨부↔DB 테이블 집합 대조가 **모델 추론**으로 수행돼 대소문자 처리가 비결정적. 결정론적 코드 lever 부재가 근본. 사용자 결정 = **"코드로 결정론적 봉인"**(AskUserQuestion 2026-07-14) → 대조를 코드로 이관.
- Changes(feature-0002):
  - `src/modules/tools.py` — 신규 tool **`check_table_coverage(schema_name, attachment_id?)`**: 실 DB 테이블명(정본, `describe_schema_tables`+`_raw_execute_sql`, sql_guard-safe·이름만) 기준으로, 첨부 SQL 이 그 테이블을 **실제 조작(operate-on: TRUNCATE/DELETE FROM/DROP TABLE/INSERT INTO/UPDATE/ALTER/RENAME)** 하는지 대소문자 무시로 분류(`_operated_tables` — 조작 동사 뒤 식별자만; 단순 이름 등장≠조작). `_split_sql_active_comment` 로 블록`/* */`·라인/인라인 `--`·`#` 주석을 분리(주석 조작=의도적 보존 별도 집계). 첨부 `truncated` 플래그 감지 시 '미조작' authoritative 격하. USE/schema-qualifier 로 cross-schema 귀속. 첨부는 deferred import `agent_core._load_attachment_inline_texts()`(ContextVar-aware·순환 회피). 접근은 기존 `_struct_schema_access_error`(내부 스키마·미허용 DB 차단·`_safe_ident`) 재사용. TOOL_DEFINITIONS(LLM 노출 base)+`_TOOL_HANDLERS` 등록.
  - `src/agent_core.py` — SYSTEM_PROMPT 라우팅: 커버리지 비교는 `check_table_coverage` 사용, '조작' 결과를 눈으로 뒤집지 말되 **truncated 경고 시 미확인·원본 재요청**(COMPARING 규칙 직후) + reason/work narration 2곳 분기.
- Recurrence sealing: false-missing 의 핵심 대조를 모델 추론 → **코드 결정론**으로 이관. 대소문자만 다른 조작 대상(첨부 CamelCase ↔ DB 소문자)을 코드가 '조작'으로 정확 집계 → '누락' 오판 소멸. 프롬프트 레버(CHG-20260714T221500)와 상보(도구 호출 유도=프롬프트, 대조 로직=코드). **보안 회귀 0**: 테이블 **이름만** 노출(행/컬럼 데이터 없음)·`_struct_schema_access_error` 게이트 동일·`re.escape` ReDoS-safe·첨부는 현재 run scope 만.
- §18.8 적대 2렌즈 패널이 v1 순진설계 적발(REV-20260714T233000): **B1**(절단 미인지→false-missing authoritative 재도입)·**B2**(블록/인라인/# 주석 누출→false-coverage)·**M1**(이름 아무데나 등장→컬럼/함수 동명 오집계·실누락 은폐) BLOCKING/MAJOR → **조작-동사 추출 + 주석 분리 + 절단 캐비엇 + USE 스키마 귀속**으로 전면 재설계 봉인. 보안 5벡터 REFUTED.
- 검증: `tests/test_check_table_coverage.py` **12 PASS**(seal `LoginEventLog`↔`logineventlog`=조작 집계·미조작 아님 + B1 절단격하·B2 주석분리·M1 컬럼오탐방지·m1 cross-schema 회귀 + 헬퍼). feature-0002 전체 `make test` 신규 회귀 0. §18.8 적대 2렌즈 패널 → REV-20260714T233000-attach-table-coverage(BLOCKING2·MAJOR1·MINOR2 전건 수정).
- Cross-ref: **CHG-20260714T221500**(case 프롬프트 레버 — 본 도구가 그 잔존을 코드로 마감·상보) · **FR-partial-evidence-false-verification**(원장) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T104500-friction-ledger-reconcile (docs-only: FR-partial-evidence 원장 상태 arc 정합, 코드 변경 0)
- Date: 2026-07-15. 런타임 코드·테스트 무변경. `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-partial-evidence-false-verification 엔트리의 잔존-결함 문구가 "별도 triage 대상"(PR #800 시점)에 머물러, 완료된 후속 봉인 arc(case 프롬프트 레버 CHG-20260714T221500 부분작동 → 결정론 도구 CHG-20260714T233000 배포 `3c8e78df`)를 반영하도록 정합 + status enum(`fixed:deployed:unverified-live`) 불변 명시.
- Recurrence sealing: N/A(문서 정합). 코드 봉인은 CHG-20260714T221500·CHG-20260714T233000, 적대검증은 REV-20260714T221500·REV-20260714T233000.
- 검증: docs-only(§18.4 META 인접) — verify-completion #9 = REV-20260715T104500 [SKIPPED:post-deploy-ledger-reconciliation].
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification · CHG-20260714T233000 · REV-20260715T104500.
## CHG-20260715T050000-conv-alias-leak-guard (대화 답변 model alias 누출 Bedrock 400 봉인 — deferred ④ 근본, Major §12.3)
- Date: 2026-07-15. 계기: 첨부-답변 정합성 실데이터 감사의 deferred 축 ④(선행 CHG-20260714T210000 이 friendly-message bad_model 로 표면만 완화). 서브에이전트 근본 추적.
- Reason(RC): 대화 답변 경로 `_call_llm` 은 고정 Bedrock 클라이언트로 나가며 model 별 tier-resolve 를 하지 않는다(FR-edge-fallback: 대화는 gemma 강등 금지). `conversation_answer_model()`(shared/model_catalog.py)이 미매핑 alias 를 identity 로 통과시켜, 로컬 게이트웨이 alias(auto/edge/core/code)·미등록 bare 'claude' 가 Bedrock 프록시로 raw 전달 → `Invalid model name passed in model=...` 400(실측: 다수 대화 `LLM 호출 오류` + `__ask_worker__`). 운영 `.env` `OPENAI_MODEL=auto`(config.py:741-742 주석) 가 대표 트리거 — model 미지정 job → OPENAI_MODEL → auto → 400.
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Major(대화 답변 outbound model 라우팅; 인증·PII·파괴 불변 → Critical 아님). 변경은 **현재 400 나던 케이스만** 바꿈(정상 케이스 무회귀 = 순개선).
- Changes(shared + feature-0002; §13.2.2 F2 shared/ 단일-mutator = 본 cycle):
  - `shared/model_catalog.py` — `conversation_answer_model()`: 기존 `claude-haiku-4→claude-haiku-4-chat` 매핑 유지 + 로컬 alias(`is_local_llm_model`: auto/edge/core/code)·bare 'claude' 를 `_CONVERSATION_ANSWER_DEFAULT_CHAT`(`claude-haiku-4-chat`)로 fail-loud(warn log) 해소. 등록 Claude(claude-sonnet-4)·이미 해소된 chat alias·공백/None 은 identity(무회귀). `logging` import + `_log` 추가.
  - `src/agent_core.py` `_call_llm` — **(적대 패널 CONFIRMED-DEFECT#1 수정)** `budget_model = model if model_supports_thinking(model) else outbound_model` 도입: **max_tokens 산정만** outbound(-chat) 기준(`agent_max_output(claude-haiku-4-chat)=20000`). 초기 fix 는 outbound model 만 해소하고 max_tokens 를 원본(auto→local cap 2048 / bare claude→None) 기준으로 잡아, outbound `-chat` 의 config 고정 thinking budget(5000) 대비 `2048<5000` → Anthropic max_tokens>budget 위반 = **2차 400**(프로덕션 트리거 auto 에서 400→400)이던 결함 봉인. **thinking 주입 게이트는 원본 model 유지**(비-thinking 누출 alias 는 client thinking 미주입 → config 5000 적용, 20000>5000 안전). `model_supports_vision`·`_record_llm_usage` 는 원본 유지. 정상 claude-haiku-4/sonnet-4 경로 budget_model=원본 → 24000/40000 무회귀.
  - **거부한 대안**(중요): `_call_llm` 에 `_get_llm_client(model=...)` tier-resolve 미러링 — 대화 `model=auto` 를 로컬 gemma 게이트웨이(ctx 4096)로 라우팅해 FR-edge-fallback 이 금지한 silent context-truncation 강등을 재도입하므로 채택 안 함. tier-resolve 는 insight/aux 전용, 대화 답변엔 부적합.
- Recurrence sealing: 대화 outbound alias 를 choke-point(`conversation_answer_model`) 단일점에서 등록 chat 모델로 강제 해소 → raw alias 가 Bedrock 으로 새는 경로 봉인. G6 invariant(해소 대상이 litellm model_list 등록명)로 미래 기본모델 변경 시 재-누출 방지. **보안 회귀 0**: 대화는 Claude 유지(gemma 미도달, G5 체인 invariant 불변), 표시/저장/usage 는 원본 model 유지.
- 검증: `tests/test_conversation_answer_no_edge_alias.py` — 기존 `edge→edge` identity(옛 버그 인코딩) → 새 계약 갱신 + G2b(auto/edge/core/code/claude→chat 파라메트릭)·G6(등록명 invariant)·G7(`_call_llm` model='auto'→아웃바운드 chat, 기록은 원본)·**G8**(패널 회귀: 누출 alias 예산이 outbound=chat 기준·`max_tokens>5000`, agent_max_output 스파이) 추가. 파일 15 PASS. 회귀 `test_reasoning_effort.py`(edge→thinking 미주입) 재통과. **컨테이너 `make test`(feature-0002+0003 정본)**: cycle 자체 테스트 전부 PASS, **무관 4건 실패=신규 회귀 0**(실증) — 2 env(`test_runtime_settings::test_missing_snapshot_is_fail_open`·`test_runtime_settings_api::test_get_returns_registry`: base main 격리에서도 동일 실패=환경 pre-existing) + 2 순서오염(`test_routine_dbanalysis::…status_aggregation_failure`·`test_item11_batch8::test_auto_happy_200`: base·worktree **격리 실행에선 PASS**, 전체 스위트에서만 실패 → 테스트 순서 오염, 내 diff 미참조·model 라우팅 무관). §18.8 적대 패널(CONFIRMED-DEFECT#1 수정 + 5축 REFUTED + 2 PLAUSIBLE-RISK 수용) → REV-20260715T050000-conv-alias-leak-guard.
- Cross-ref: **CHG-20260714T210000-attach-review-grounding**(같은 축 ④ friendly-message 계층 — 본 CHG 는 그 근본 봉인) · feature-0007 MODIFY(litellm model_list source-of-truth) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T060000-attach-inline-honesty (text-inline 회귀테스트 + 첨부 cap-note 정직화 — deferred ①+②-backend, Minor §12.3)
- Date: 2026-07-15. 계기: 첨부-답정합 실데이터 감사의 deferred ①+②-backend. ② 서브에이전트 진단으로 share-window 는 라이브-ask 첨부 경로 밖(비보안)임을 확인 — 마찰은 프론트 라벨 비대칭(Cycle C)과 backend cap-note.
- Reason(RC): ① text kind 첨부(.sql 등)는 sandbox 아닌 raw content 직접 인라인이 정상 경로(TASK-0124)인데 이를 직접 검증하는 회귀 테스트가 없었다(과거 2026-05 다수 대화가 text SQL 을 "sandbox ingest 대기/실패"로 오인). ② 인라인 개수/크기 상한(_TEXT_INLINE_COUNT_CAP=20 + 64KB/file)을 넘겨 map 에 없는 text 파일에 붙던 노트 `(content unavailable — check MinIO connectivity)` 가 원인을 MinIO 로 오귀속 → 모델이 인프라 장애를 fabrication(관측 대화 20260615061233·FRICTION_LEDGER text-inline count cap).
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(프롬프트 note 문구 + 회귀 테스트; 비파괴·행동개선).
- Changes(feature-0002):
  - `src/agent_core.py` `_build_attachment_context_section` — 인라인 map 부재 text 파일 노트를 정직화: MinIO 오귀속 제거. **적대 패널(REV-20260715T060000) 3정정 반영** — (a) "size cap" 삭제(크기초과 파일은 truncate 되어 여전히 인라인됨 → 부재 원인은 count cap 또는 판독실패만) (b) `len(map)`을 cap·"N most recent" 로 단정하지 않음(판독실패로 top-20 에 구멍 가능) (c) 회복경로 = **재첨부**(높은 Id → 최신 → 인라인; 선택은 `ORDER BY Id DESC LIMIT` 이라 "파일명 지정 우선순위" 메커니즘 부재 = 거짓약속이었음) (d) `len==0`(인프라 실패 가능성 最高)은 cap 귀속·downplay 금지("cause is not confirmed", 재첨부/재시도). `len>0`("currently N loaded" + "Do NOT claim a specific MinIO/system failure" + 재첨부) vs `len==0` 분기.
  - `tests/test_attach_inline_honesty.py` **신규** — ①(text content 인라인·sandbox 미라우팅·content_len) + ②(len==0/len>0 노트에 MinIO 오귀속 부재·count 보고). `_load_attachment_inline_texts` monkeypatch, DB 없이 fake conn.
- Recurrence sealing: ① 인라인 경로 회귀 봉인(text→sandbox 오라우팅 재발 시 테스트 적색). ② cap-omit 노트의 MinIO 오귀속 제거로 모델의 인프라-장애 fabrication 차단. **보안 회귀 0**: 노트는 code-authored 안내(datamark 밖·주입면 무변경), 접근/스코프 불변.
- 검증: 신규 4 PASS. 다른 테스트 옛 노트 참조 0(grep, CHECK#3 무회귀). feature-0002 전체 회귀 신규 실패 0. §18.8 적대 패널 → REV-20260715T060000-attach-inline-honesty.
- Cross-ref: ② 서브에이전트 진단(share-window 비관여) · Cycle C(②-frontend app.js 라벨 대칭, 후속) · FRICTION_LEDGER text-inline count cap · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T082345-schema-name-case-drift (스키마명 서버-실제-case 해소 — A 런타임 canonicalize + grounding, Critical §12.3 데이터소스 바인딩)
- Date: 2026-07-15. 계기: `/_dqa:conversation_audit` "테이블 구조 정합성 검토"(product 97 대화 20260715070720-c202bcf8) — assistant 가 데이터소스 참조 불가·유효 테이블 조회 0행 → 요청 수행 불가.
- Reason(RC, 3-source 삼각측량 high): allowlist `WebProductDatabases.SchemaName` 이 서버 실제 대소문자와 다르게 소문자 저장(서버 `DEV_1_1_1_20`, 63테이블 ↔ 저장 `dev_1_1_1_20`). case-sensitive MySQL(`lower_case_table_names=0`, Linux)에서 구조화 도구가 저장 case 를 literal 로 써 전부 0행/빈결과 → '테이블 없음' 오판·give-up. `_datasource_allow_schemas`(agent_core.py:3153)는 저장 case 를 **의도적 보존**(case-sensitive 대응)이라 코드는 옳으나 저장 데이터가 소문자 → grounding·쿼리 모두 잘못된 case. 이전 casing 프롬프트 lever(모델 소문자화 금지)로는 미해결(데이터 자체가 소문자). 재발경로 = **data/config drift**(allowlist casing ≠ 서버 casing) → 코드 권위선 봉인.
- corroboration: **structural** — allowlist 205 중 85 case mismatch; MySQL 실패확정 클래스(소문자 stored → 서버 대/혼합) ~18행·4 product(94/97/110/121)·다수 MySQL datasource. (MSSQL 67 은 case-insensitive → 무해 거짓양성 기각.)
- 사용자 승인: **Critical → attended AskUserQuestion(2026-07-15) = "A + B(ingestion)"**. A(런타임 resolution seal)+B(web-UI write 정규화).
- Changes(feature-0002 primary):
  - `src/modules/tools.py`:
    - `_mysql_schema_case_map(conn)` — 라이브 `SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA` 로 {소문자→서버실제case} 맵. conn 속성 캐시(dict 만 신뢰 — MagicMock/래퍼 auto-vivify 방어). 대소문자만 다른 동명 복수는 **모호→제외**(fail-safe). 조회 실패=빈 맵(no-op).
    - `_canonical_schema_name` / `_canonicalize_schema_args_mysql` — schema_name 을 서버 실제 case 로(유일 매칭 시만).
    - `execute_tool` — 라우터·비라우터 양 경로에서 handler dispatch **직전** schema_name 정규화(MySQL 한정, MSSQL/비-MySQL no-op). 라우터 경로는 `conn_for → refresh_case → activate` 순.
    - `_DatasourceRouter.refresh_case(label, conn)` — 그 datasource(MySQL) `_allow_schemas`(grounding·DISPLAY allowlist)를 서버 실제 case 로 정규화. idempotent(`_allow_schemas_case_fixed`). MSSQL no-op.
  - `src/agent_core.py` — 멀티-ds primary 연결 직후 `refresh_case(resolve_label(None), db_conn)` → run-start grounding 이 실제 case 노출.
- **보안 불변식(회귀 0)**: 접근 게이트 `_ACTIVE_SCHEMA_ALLOWLIST`(소문자 set)는 canonicalize 전후 판정 동일(`'DEV_1_1_1_20'.lower()=='dev_1_1_1_20'`) — 미허용 스키마 접근 확장 0, 내부(agent_memory)/시스템 스키마 차단 불변. canonicalize 는 이미 authorize 된 스키마의 *표기*만 서버 실제값으로 교정.
- 검증: 신규 `tests/test_schema_name_case_drift.py` 15 PASS(case-map·canonicalize·refresh_case·execute_tool choke·보안불변·MSSQL no-op). feature-0002+0003 전체 **2107 passed, 2 skipped**. §18.8 적대 패널 → REV-20260715T082345-schema-name-case-drift.
- 라이브 실측 필요분(§정직): 코드/유닛은 "정규화 로직 정확·게이트 불변" 증명. "실제 대화 마찰 소멸(describe/search 가 DEV_1_1_1_20 63테이블 반환·give-up 소멸)" 은 배포 후 원 입력 재현분(미수행) → 배포 후 `unverified-live`, 다음 audit corroboration 재측정.
- 적대 패널 후속(REV-20260715T082345): 초기 grounding(primary-only)·poison-cache·Part B(picker) 결함을 §18.8 3렌즈가 적발 → grounding graph 교정(전 datasource·live-fixed skip)·프로브 실패 재시도·**B write-path 정규화 재설계**로 봉인, 재검증 READY-TO-SHIP. 상세 REVIEW.md.
- Cross-ref: **B = feature-0003 admin_products.py write-path 서버-실제-case 정규화**(CHG-20260715T082345-picker-case-preserve, admin.js/수기 입력 무관 chokepoint) · FRICTION_LEDGER FR-schema-name-case-drift · 이전 FR-nl2sql casing 프롬프트 lever(모델 소문자화 금지 — 별개 축) · ANCHOR 0002 §1~§3 무충돌(allowlist 격리 불변식 유지).

## CHG-20260715T234757-probe-throttle-monotonic-flake (LLM 헬스 probe throttle 센티넬 — 갓-부팅 spurious throttle(CI flake + 잠복 버그) 해소)
- Date: 2026-07-15. 계기: 무관 PR #832(프론트 graph)의 CI 를 `test_probe_pings_when_restricted_for_recovery` 가 flaky 하게 red 화. 같은 base #831 green → flaky 확증.
- 근본원인: `probe_provider` throttle `now - _PROBE_STATE["ts"] < min_gap`(now=`time.monotonic()`, min_gap=5|TTL60). 미-probe 센티넬 `ts=0.0` + monotonic()<min_gap(갓-부팅 러너/워커) → `now - 0 < min_gap` → 첫 probe spurious throttle. 러너 uptime 의존 flake + 잠복 프로덕션 버그(첫 restricted-복구 probe 누락).
- Changes(feature-0002):
  - `src/modules/llm_provider_health.py` `probe_provider`: throttle 판정을 `last_ts = float(_PROBE_STATE["ts"]); if last_ts > 0.0 and now - last_ts < min_gap:` 로 — ts=0.0(미-probe)은 monotonic 무관 non-throttle(첫 probe 항상 허용), 실 스탬프 후에만 throttle. 정상 TTL/5s throttle·running 가드·M2 PG throttle·recovery gate 불변.
  - `tests/test_llm_provider_health.py`: `_run_probe` 에 `ts` 파라미터(기본 0.0) 추가 + `import time`; 회귀 잠금 2종(`test_probe_sentinel_ts_zero_not_throttled_regardless_of_monotonic`·`test_probe_recent_ts_within_ttl_throttles`).
- 비변경: 분류기·record/read health·recovery-only gate·thinking budget·RBAC/스키마/마이그레이션 0.
- 검증: `test_llm_provider_health.py` 39 PASS · flake 조건 재현(monotonic=10<60·ts=0.0·restricted → 수정 1 ping, 구 0) · §18.8 [SKIPPED] 적대 자가검토.
- Cross-ref: 원천 flake=무관 PR #832 CI · 선행 CHG(1c1889e4, TASK-20260715-llm-probe-thinking-budget, recovery-only gate 도입) · REV/TEST-20260715T234757-probe-throttle-monotonic-flake · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260722T050006-branch-chain-race (20260722T050006-branch-chain-race — 재답변 브랜치 체이닝 동시성 경합 수정, Major §12.3, PLAN-APPROVED)
- 계기: 사용자 신고 — 재답변 편집 후 보낸 메시지가 화면에서 사라지고 assistant 답변만 쌓임(라이브 대화 20260722015229-79da15cb).
- 근본원인: 브랜치 대화 새 메시지 parent 를 대화-공유 `active_leaf`/`active_display_leaf` 를 매 write 재-read 로 결정 → 동시 재답변 setup/overlap 으로 분기점(M.parent)/타 turn 값 리셋 시 답변이 user 형제로 붙어 active-path 에서 user 누락(read-modify-write race).
- 변경(`src/modules/runtime_backend.py`, +46): thread-local run-cursor API — `branch_run_begin(active)`/`branch_run_end()`/`branch_run_active()`/`branch_chain_get(store)`/`branch_chain_set(store,id)`. store∈{core,disp} 각 id-space 독립.
- 변경(`src/agent_core.py`): `_save_message`(core store) — 브랜치 run(`branch_run_active()`)이면 active_leaf 재-read 대신 run 커서(직전 write id)에 체인(첫 write 만 active_leaf 1회 read)·leaf 전진·커서 갱신, 반환 id 추가. `_run_agent_core` — user write 직전 `branch_run_begin(has_branches)`, teardown(스레드 재사용 stale 정리 지점)에 `branch_run_end()`.
- 변경(`src/modules/memory.py`): `save_memory_message`(display store) — 동일 커서 체인('disp').
- 비변경(회귀 0): 비분기 대화(has_branches=false, `branch_run_active()`=false)는 기존 auto append 경로 byte-identical(feature-0019 ANCHOR INV-1 보존). 엔드포인트 sibling 생성(명시 parent/edit_version>1)·비-run 호출자 무영향. 백엔드/RBAC/스키마/마이그레이션 0.
- Verification: `py_compile` 3파일 · 단위 `tests/test_branch_chain_race.py` 4 PASS · feature-0002 전체 pytest PASS(마운트, 0 fail) · §18.8 subagent 적대 리뷰(REVIEW). POST-DEPLOY 라이브 PB-0008 + 데이터 복구(오염 5행) 예정.
- Files: `src/agent_core.py`, `src/modules/memory.py`, `src/modules/runtime_backend.py`, `tests/test_branch_chain_race.py`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`.
- landing/배포: verify-completion → commit → push → PR/머지=자동 동기화. 배포(deploy-all, 워커 코드 변경)=외부 영향 confirm. 데이터 복구=POST-DEPLOY.

## CHG-20260722T055000-branch-chain-race-postverify (branch-chain-race POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·데이터 복구 실증 기록 + TASK 체크박스 완료. 코드/자산 0.
- 배포: PR #874 → main 5a32a480 → `deploy-web.sh` 전체(web 롤링 soak PASS + insight/ask-worker mysql-ai-agent:5a32a480 healthy + gateway 무드리프트).
- 데이터 복구: 대화 20260722015229-79da15cb 오염 5행 재링크(트랜잭션 UPDATE 1 display + UPDATE 4 core, dry-run 일치) → active-path 에 user 1299 복귀·오염 잔존 0·`/api/history` 에 "로그 흐름만…" 반환 확인.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/TEST.md`.
## CHG-20260722T033854-enum-schema-grounding (ENUM 자동등록 schema-grounding 게이트 — 환각 DB/테이블 차단, Major §12.3)
- 계기: 메타데이터 거버넌스 "ENUM 검토 큐"에 `scope: mysql-kr-an1-auth`(auth) 기준 없는 `dbLog` DB + 없는 `Currency` 테이블이 자동등록. RC=`_enum_autopropose` 가 LLM 추출 (schema,table,column) 을 실제 카탈로그 대조 없이 verbatim 등록(가드는 비어있음만 검사).
- Changes(feature-0002):
  - `src/agent_core.py` `_enum_known_table_index()` 신설: 활성 datasource 의 `table_insight` fact 카탈로그(`cfg.ds_fact_like` 한정)로 알려진 테이블 인덱스 구성(정규화는 kb_glossary 위임). `_enum_autopropose` 루프에 게이트 삽입 — `AGENT_ENUM_SCHEMA_GROUNDING` on 시 카탈로그 부재 (schema,table) 은 `auto_promote_or_queue_enum` 호출 전 skip + `enum_autopropose_skip_ungrounded` 로깅. 카탈로그 미가용/빈 → fail-open.
  - `src/modules/kb_glossary.py`: 순수 함수 `build_known_table_index`(MySQL/MSSQL 계층 전개·대소문자 무시)·`is_enum_grounded`(idx=None→fail-open) + `sweep_ungrounded_enum`(소급 정리 SQL: source='auto' DELETE + feedback pending/auto_promoted→rejected, manual 보존, scope_key 바인딩).
  - `shared/config.py`: `AGENT_ENUM_SCHEMA_GROUNDING`(기본 "1", `__all__` 등록).
  - `scripts/enum_grounding_sweep.py`: 운영자용 소급 정리(dry-run 기본·`--execute`·`--scope`, common scope=active None 정합).
  - `tests/test_kb_enum_grounding.py`(14: 정규화·판정·재현 시나리오·sweep) + `tests/test_enum_autopropose_gate.py`(3: wiring 환각 차단·flag off·fail-open).
- 자가수리(self-heal, 사용자 추가 요청):
  - `src/modules/insight.py` `_enum_self_heal(swept_scopes, *, engine, known_schemas, scanned)` 신설 + `run_insight_cycle` per-(scope,db) `else` 블록 배선(카탈로그 refresh 직후·scope 유효·`_ds_key is not None` 가드 앞→기본 MySQL 커버) + cycle-local dedup `_enum_swept_scopes`. 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`) 기준 '없는 DB' enum 회수. `scan_started` 게이트 + grounding flag 결합 + MSSQL 제외.
  - `src/modules/kb_glossary.py` `sweep_unknown_schema_enum(conn, scope_key, known_schemas, *, dry_run, confirm_lower)` 신설(schema_name ∉ 실제목록 제거·bare-schema 미터치·source='auto' DELETE·scope 바인딩·case-insensitive·`confirm_lower` catalog-shrink 가드=2회 연속 관측 시에만 삭제).
  - `shared/config.py` `AGENT_ENUM_SELF_HEAL`(기본 "1", `__all__` 등록).
  - `tests/test_enum_self_heal.py`(10) + `sweep_unknown_schema_enum`(4).
- 비변경: manual promote/create 경로·검토 큐 승인/거부(admin_metadata)·enum_dictionary/enum_feedback 스키마·마이그레이션·RBAC·ask-worker(예방 게이트로 이미 커버) 0. label 내용·column-레벨 검증 미포함(범위 밖).
- 검증: 신규 37 PASS(예방 20 + self-heal 계열 17) · 기존 enum/glossary 35 PASS · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- Cross-ref: REV/TASK/TEST-20260722T033854-enum-schema-grounding · 선행 CHG-20260629-glossary-conv-autoreg(대칭 용어사전 경로)·0039 enum autopropose · cross-ref feature-0003 admin_metadata(검토 큐 UI, 무편집) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260722T033854-enum-self-heal (ENUM 자가수리 — insight-worker 주기 소급 정리, 사용자 추가 요청, Major §12.3)
> 예방 게이트(CHG-20260722T033854-enum-schema-grounding)에 이은 후속(같은 cycle·같은 branch). 사용자 추가 요청 "재발해도 insight/ask-worker 동작에 따라 자가수리". 예방 게이트 commit(87b06a1f) 이후 self-heal 을 별도 change set 으로 추가.
- Changes(feature-0002):
  - `src/modules/insight.py` `_enum_self_heal(swept_scopes, *, mem_conn, engine, known_schemas, scanned)` 신설 + `run_insight_cycle` per-(scope,db) `else` 블록 배선(스캔 성공·scope 유효·`_ds_key is not None` 가드 앞→기본 MySQL 커버) + cycle-local dedup `_enum_swept_scopes`. 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`=load_known_schemas) 기준 '없는 DB' enum 회수.
  - `src/modules/kb_glossary.py` `sweep_unknown_schema_enum(conn, scope_key, known_schemas, *, dry_run, confirm_lower)` 신설.
  - `shared/config.py` `AGENT_ENUM_SELF_HEAL`(기본 "1", `__all__` 등록).
  - `tests/test_enum_self_heal.py`(13) + `tests/test_kb_enum_grounding.py` sweep_unknown_schema_enum(confirm/빈-schema).
- 안전(§18.8 적대 패널 2 라운드 — 파괴적 자동 DELETE): Round1 BLOCKER1(부분 카탈로그 오삭제)+MAJOR2(매8s·decoupling) → 재설계 Round2 RESOLVED — 완전 실제 스키마 목록 기준·MySQL allowlist·`scan_started` 게이트·grounding flag 결합. 잔여 MINOR-A(권한회수 축소) → catalog-shrink 가드(2회 연속 관측 KV persistence). NIT-C/D 정리.
- 비변경: ask-worker(예방 게이트로 이미 커버)·enum 스키마·마이그레이션·RBAC 0. table-레벨/bare-schema 자동 정리는 미포함(운영자 `scripts/enum_grounding_sweep.py`).
- 검증: 신규 self-heal 계열 17 PASS · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- Cross-ref: REV/TASK/TEST-20260722T033854-enum-schema-grounding(self-heal 라운드) · 선행 CHG-20260722T033854-enum-schema-grounding(예방 게이트) · insight-worker(§16.3)·0039 enum autopropose · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260724T123600-csv-download-wiring (cross-cut — cycle home = feature-0003)
- conv-audit(csv-inline-no-download): assistant 가 인라인 ```csv``` 블록으로 결과를 제시하며 "다운로드 가능"이라 안내하나 실제 다운로드 수단이 없던 마찰 수정의 백엔드 몫.
- `src/agent_core.py`: `_collapse_large_csv_blocks(answer, csv_paths)` 신설 — 답변 내 대형 ```csv``` 펜스 블록을 `_collapse_large_tables`(MD표) 와 동일하게 값-토큰 매칭으로 저장 CSV 찾아 미리보기+`/api/file` 링크 주입(매칭 실패 시 원문 유지). 초안·redteam 수정·redteam 최종 3경로에 `_collapse_large_tables` 뒤 체인. 기존 `_collapse_large_tables`/`_csv_signatures`/`_match_csv_for_table` 무변경(재사용).
- `src/modules/tools.py`: execute_sql·scratch_sql 툴 출력 가이던스 — "저장 CSV 는 다운로드 버튼으로 자동 제공(링크 직접 생성 불필요)·전체 데이터 붙여넣기 금지" 항상 안내로 정합(기존 "다운로드 링크를 제공하세요" 폐기).
- 프론트(app.js/share.js/styles.css)·docs·검증·배포 정본 = feature-0003 REPORT/MODIFY/TASK/REVIEW/TEST-20260724T123600-csv-download-wiring. 테스트: `tests/test_collapse_csv_block_download.py`(신규 6) + `test_partial_evidence_grounding.py`·`test_scratch.py` 가이던스 문구 정합. 전체 pytest 2303 passed/2 skipped.

## CHG-20260724T054326-timeout-console-sync (LLM upstream 타임아웃 ↔ 관리 콘솔 'AGENT_TIMEOUT_SEC'(live) 요청 단위 동기화 — cross-feature, primary=feature-0002+feature-0007)
> 사용자 요청(feature-0007 saga 6층): "`request_timeout` 또한 `설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃` 설정값과 동기화되도록 구성". 선행 llm-timeout-align(CHG-20260724T141420, feature-0007)이 gateway `request_timeout` 을 정적 120→300 으로 올렸으나, gateway 는 앱과 **별도 프로세스**라 관리 콘솔에서 값을 바꿔도 정적 config 는 추종하지 못하는 drift 가 남아 있었다.
- 진단(라이브 결정 실험, bedrock-gateway 컨테이너): litellm 은 **요청 body 의 `timeout` 을 per-attempt upstream 타임아웃으로 존중**한다 — 동일 sonnet 호출에 body `timeout=5`→HTTP 408(컷), `timeout=200`→200 @11.7s(성공). 따라서 앱이 요청마다 live 값을 body 에 실으면 gateway 재기동·재배포 없이 즉시 동기화 가능(정적 config 로는 불가능한 실동기화 수단).
- Changes(feature-0002 `src/agent_core.py`):
  - `_call_llm`: extra_body 를 항상 `{"timeout": max(5, int(_rts.get_int("AGENT_TIMEOUT_SEC")))}`(live)로 초기화하고 thinking(budget)/output_config(effort)를 **병합**(이전엔 thinking/effort 있을 때만 extra_body 세팅). 모델·레벨 무관하게 매 호출 live 콘솔 타임아웃이 upstream 으로 전달됨.
  - ask() 진입 client 생성(`OpenAI(timeout=)`): 정적 `config.AGENT_TIMEOUT_SEC`(import 고정) → live `_rts.get_int("AGENT_TIMEOUT_SEC")`. 콘솔 상향 시 client 총-대기가 옛 값에서 조기 컷하던 gap 봉인(body timeout 과 동일 소스 정합).
  - run 예산 `run_timeout_sec`: `AGENT_TIMEOUT_SEC*3`(정적) → `max(5,int(_rts.get_int(...)))*3`(live). 루프 전체 예산도 콘솔 추종.
- Changes(feature-0007 `src/config/litellm_config.yaml`): `request_timeout: 300` 값 무변경 — **주석만** 갱신(앱이 요청마다 live body timeout 전달, config 는 body timeout 미전달 경로의 정적 fallback ceiling 임을 명문화). 정본 CHG = feature-0007 MODIFY.md CHG-20260724T054326-timeout-console-sync.
- Tests(feature-0002): `tests/test_reasoning_effort.py` — extra_body 항상-timeout 대응 위해 `_xb()`(timeout 제외 헬퍼) 도입 + 기존 thinking/effort 정확매칭 회귀 가드 전부 `_xb` 로 유지 + `_call` 에 body timeout 존재/유효(>=5) 상시검증 + 신규 `test_body_timeout_synced_with_console_agent_timeout`(스냅샷 450→body timeout 450, B1 무override 병존)·`test_body_timeout_default_when_no_console_override`. `tests/test_conversation_answer_no_edge_alias.py` G8b — adaptive sonnet '일반'이 이제 extra_body 에 timeout 은 싣되 thinking/output_config 는 미주입임을 확인(누출 가드 유지).
- 비변경: thinking/effort 주입 로직·budget clamp·CC identity·edge-free 라우팅·probe(짧은 8s 헬스 ping 유지)·RBAC·스키마·마이그레이션 0.
- 검증: feature-0002+0003 전체 pytest RC=0(신규 실패 0), 변경 3파일(reasoning_effort/conversation_answer/llm_provider_health) 타겟 전부 PASS. 배포 후 라이브: 콘솔 AGENT_TIMEOUT_SEC 변경→gateway 실행 로그/실제 요청 timeout 추종 확인 예정.
- Rollback: extra_body 를 조건부(thinking/effort 있을 때만) 로 되돌리고 client/run 예산을 정적 `AGENT_TIMEOUT_SEC` 로 복원(단 콘솔↔gateway drift 재발).
- Cross-ref: REV-20260724T054326-timeout-console-sync · feature-0007 MODIFY/REVIEW/TASK-20260724T054326-timeout-console-sync · 선행 CHG-20260724T141420-llm-timeout-align(feature-0007, 정적 300) · shared/config.py AGENT_TIMEOUT_SEC · runtime_settings AGENT_TIMEOUT_SEC(live, apply_mode) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260724T155534-tool-result-cap-raise (도구 결과 4000자 하드캡 → 대형 설정 backstop; 프로시저 정의 절단 해소 — Major §12.3)
> 계기(사용자, /_dqa:conversation_audit): "assistant 가 추론·내부 도구로 프로시저를 분석할 때 텍스트가 길면 내용이 잘려 한 번에 탐색 불가 — 반환 문자열 길이 제한이 없도록". 마찰 = **FR-procedure-analysis-result-truncated**.
- **근본원인(L2 도구 피드백, 코드 file:line 확정)**: 에이전트 도구 루프가 **모든 도구 결과를 4000자로 하드캡**한 뒤 LLM 에 되먹임 — `agent_core.py` 메인 루프(구 4905)·재추론(rederive) 루프(구 4684)·저장 copy(구 4933). 프로시저 정의 전용 도구 `describe_routine`(CHG-20260713T140405)은 핸들러에서 정의 본문을 **전문 반환**하지만 이 루프 캡이 4000자 초과 본문을 다시 잘라 도구 목적을 무력화 → 나머지를 못 채운 assistant 가 반복 재조회/포기(타임아웃). 실무 프로시저 본문은 4000자 초과가 흔함. **describe_routine 개선의 직접 후속 갭.**
- **결정(사용자, 2026-07-24 AskUserQuestion)**: 세 선택지(정의 도구만 무제한 / 전 도구 무제한 / **전 도구 대형 캡**) 중 **전 도구 대형 캡** — 도구별 분기 없이 큰 유한 캡을 전 도구에 적용. 실무 프로시저는 사실상 무제한(전문 도달)이되, 병리적 대량 결과(넓은 표 대량 행 등)의 컨텍스트/토큰 폭주는 유한 backstop 이 계속 막는다.
- **무엇을**: (1) `shared/config.py` `AGENT_TOOL_RESULT_MAX_CHARS` 신설(env override, 기본 **100000**, `__all__` 등록). (2) `agent_core._cap_tool_result(text)` 헬퍼 신설 — cap 초과 시에만 `... (truncated)` note 부착(FR-partial-evidence epistemic 계약: 미열람분 존재/부재/개수 전수 단정 금지 보존), `cap<=0` 은 무제한 sentinel. (3) 세 캡 지점(메인 루프·rederive 루프·저장 copy)을 헬퍼/상수로 치환. 저장 copy 는 이미 캡된 `tool_result` 를 그대로 저장(PG `agent_runtime.core_messages.content`=text 무제한이라 컬럼 overflow 없음).
- **파일**: `shared/config.py`(상수+`__all__`); `unit/feature-0002-agent-core/src/agent_core.py`(`_cap_tool_result` 헬퍼 + 3지점 치환); `tests/test_tool_result_cap.py`(신규 6건).
- **왜**: 프로시저 등 길고 단일-권위 텍스트를 한 번에 못 봐 분석이 타임아웃되던 마찰의 근본 봉인. describe_routine 이 정의를 전문 반환해도 루프 캡이 재절단하던 모순 제거.
- **호환/안전**: sql_guard·RBAC·datasource 바인딩·PII 경로 **불변**(가드 표면 0 변경 — 순수 컨텍스트 사이징 정책). 절단이 실제 발생하는 경우(캡 초과)엔 기존 epistemic note 보존 → 완전성 오단정 회귀 없음. execute_sql/scratch 는 자체 bounding(미리보기 50행·확장 12000자·셀 100자) 유지 — 이 루프 캡은 그 위의 backstop. 스키마/마이그레이션 변경 0.
- **위험등급**: Major(§12.3 — 코어 LLM 루프·전 도구 결과 경로) → 사용자 결정(scope) 후 구현 + PR/deploy confirm.
- **Rollback**: 세 지점을 `[:4000]`/`> 4000` 하드코딩으로 복원 + 헬퍼·상수·테스트 제거(프로시저 재절단 재발).
- **Cross-ref**: FRICTION_LEDGER FR-procedure-analysis-result-truncated · 선행 FR-show-create-routine-blocked(describe_routine 신설) · FR-partial-evidence-false-verification(절단 epistemic 계약) · REV-20260724T155534-tool-result-cap-raise · ANCHOR 0002 §1~§3 무충돌.
## CHG-20260724T181106-attach-new-directive — 신규 스크립트 첨부 전달 프롬프트 지침 (Major §12.3, cross-ref feature-0003 primary)
- **What**: 사용자가 새로 생성한 스크립트/쿼리를 다운로드 첨부/파일로 요청 시 `attachment-new` 블록으로 전달하라는 지침을 base SYSTEM_PROMPT 섹션 + 코드-권위 `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE`(compose_system_prompt parts 항상 주입)로 추가. base "brand-new SQL → inline ```sql" 규칙(line 158)에 "파일/첨부 요청 시 attachment-new 예외" 명시.
- **Why**: FR-brandnew-script-attachment-delivery-gap(conversation_audit) — 마찰 정본·구현 primary 는 feature-0003(materialize 경로). 본 변경은 그 경로를 활성화하는 프롬프트(cross-ref). AUTH-1a 코드-권위 주입으로 운영자 WebSystemPrompts global row drift 봉인(`_ATTACHMENT_DELIVERY_DIRECTIVE` 선례).
- **Files**: `src/agent_core.py`(SYSTEM_PROMPT 섹션 + `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` + line 158 예외 + compose parts 주입).
- **Verification**: test_attachment_new.py PR1/PR2(drift-proof 주입: 운영자 base 가 지침 제거해도 코드-권위로 살아있음) + 전체 2369 PASS. 라이브=POST-DEPLOY(ask-worker 재빌드 후 실 LLM turn).
- **Cross-ref**: primary REVIEW/MODIFY/TASK/REPORT = feature-0003 CHG/REV-20260724T181106-brandnew-script-attachment · 원장 FRICTION_LEDGER FR-brandnew-script-attachment-delivery-gap.
## CHG-20260724T085937-sonnet-reasoning-budget-guide (test-only — sonnet adaptive 죽은 budget 스펙 제거에 따른 runtime_settings 테스트 갱신, 정본 feature-0003+shared)
- Date: 2026-07-24. shared/runtime_settings.py 가 adaptive(Sonnet 5)의 reasoning_budget/model_thinking_budget 스펙을 제거(effort 로 제어 — 죽은 컨트롤 봉인)함에 따라, feature-0002 소유 `tests/test_runtime_settings.py` 의 sonnet-budget 단정을 갱신한다(코드 로직 변경 0, 테스트만).
- Changes(feature-0002 `tests/test_runtime_settings.py`): sonnet budget/clamp 검증을 haiku(budget 계열, native−1024=62976)로 전환 + adaptive sonnet 은 override 항상 None(스펙 제거)·reasoning_budgets haiku-only 3행·`adaptive_models` 표면화 신규 단정. agent_max_output(①) sonnet 검증은 유지(adaptive 도 live).
- 비변경: agent_core 등 src 코드 0. effort/thinking style 매핑·budget 계열 동작 불변.
- Cross-ref(정본): feature-0003 MODIFY/FUNCTION/REVIEW/TASK-20260724T085937-sonnet-reasoning-budget-guide · shared MODIFY 동일 slug · REVIEW-20260724T085937(cross-ref).

## CHG-20260727T105326-worker-attachment-postprocess — 첨부 후처리 소유자를 ask-worker 로 이전 (Major §12.3)
- **What**: 답변의 `attachment-edit`/`attachment-new` 블록 후처리(첨부 materialize + 블록 strip)를 web 동기 핸들러에서 **ask-worker** 로 이전. 성공 경로의 KV terminal(done)을 후처리 뒤로 지연(`defer_terminal_status`)해 "terminal=모든 것이 끝난 시점" 계약 성립.
- **Why(RC)**: 후처리가 web `/api/ask` 에만 있어 worker 모드 장기 run(라이브 11분) 중 연결 단절 시 미실행 → 첨부 미생성 + raw 블록 노출(라이브 실측: attachment-new emit 됐으나 첨부 0건). 답변 완료 시점을 아는 워커가 올바른 소유자.
- **Files(feature-0002)**: `src/modules/ask.py`(`_postprocess_attachment_blocks`·`_record_attachment_step`·`_finalize_deferred_terminal`·`_warm_attachment_postprocess_deps`·`_slim_result` 키 추가·`_payload_to_kwargs` defer 요청·`_execute_job` 배선), `src/agent_core.py`(`defer_terminal_status` kwarg — 성공 경로 KV done 지연, error/cancel 은 즉시 유지).
- **Files(feature-0003 cross-ref)**: CHG-20260727T105326-web-postprocess-gate — `routers/conversations.py`(후처리 4곳 증거 기반 게이팅·worker 결과 forwarding·`_update_assistant_message_content` bool), `routers/_conv_store.py`(worker 결과 shape 첨부 키).
- **§18.8 반영**: BLOCKER1(web strip 미게이팅 → 블록 삭제 후 저장돼 첨부 영영 미생성·본문 소실) BLOCKER2(KV terminal 이 run_agent 내부라 순서계약 무효) MAJOR3(import 워밍업) MAJOR4(혼합 버전 배포 창 → 증거 기반 게이트 self-heal) MINOR(step 기록 패리티·error 경로 strip·update bool) LOW(terminal 유실 방지·pop 순서).
- **Verification**: pytest 2384 PASS(신규 12) · py_compile · 적대 패널 2라운드(2nd pass 에서 BLOCKER 전부 CLOSED 확인).
- **배포 주의**: web 이 worker 의 후처리를 전제하므로 **워커 포함 전체 스코프 배포**(`make deploy-web`, `--web-only` 금지). 증거 기반 게이트가 혼합 창을 self-heal 하지만 순서는 지킨다.

## CHG-20260727T175800-false-truncation-belief — 허위 절단 인식 봉인 + 루틴 정의 offset 이어읽기 (Major §12.3)
> 계기(사용자, `/_dqa:conversation_audit "문서 내부 조회 프로시저 탐색"`): "'도구 한계' 이슈가 나타나는 부분을 해소하고 싶다(`describe_routine`) — 프로시저 본문을 글자수 제한 없이 조회하도록". 마찰 = **FR-false-truncation-belief**.
- **진단 정직 표기**: 사용자가 지목한 "describe_routine 본문 절단" 은 라이브에서 **미발현**이었다. 대상 대화(`20260727081131-1dc26d26`)의 `describe_routine` 결과 11건은 **전부 절단 없이** 전문 반환(모두 ```` ``` ```` 종료, 최대 6,898자)됐고, PG `core_messages` 전 기간 describe_routine 결과 33건 중 100k 캡 초과 0건·`(truncated)` note 0건이다. 절단은 실제로 없었다.
- **근본원인(L2↔L1, 코드 file:line 확정)**: **어휘 충돌 + 신호 비대칭**. (1) `tools.py` execute_sql/scratch_sql 의 CSV 다운로드 안내문이 **절단 여부와 무관하게 항상** "핵심 **미리보기**(수 행)만" 을 담았고, (2) `agent_core.py` SYSTEM_PROMPT PREVIEW-TRUNCATED 규칙의 트리거가 `"... 행 중 N행만 표시" / "미리보기"` 라 **"미리보기" 단어 단독**으로 발동했다. → 완전한 결과를 절단으로 오인. (3) 게다가 절단 경고는 강한데 완전 표시에는 `(N 행)` 뿐이라 **완전성 확인 신호가 없어** 오귀속이 교정되지 않았다. 라이브 귀결: `execute_sql` 이 프로시저 목록 **181행을 전량 렌더**했는데 assistant 가 "총 181개가 발견되었으나 **도구 프리뷰 한계로 전체 목록 확인이 불가능**합니다"(msg 5619)라며 분석을 3건으로 축소(5611 도 "⚠️ 불완전한 결과"). 재발경로 = `model limit` + 도구 피드백 어휘 설계 결함. **FR-partial-evidence-false-verification(2026-07-14) 수정의 2차효과**(절단 epistemic 계약의 역방향 과발동).
- **결정(사용자, 2026-07-27 AskUserQuestion)**: 전역 캡 무제한화는 **범위에서 제외**. 대신 (a) 허위 절단 봉인만 진행하고 (b) 초대형 정의는 **문자열 offset 으로 여러 번 호출해 전량 도달**하도록 구성.
- **무엇을 (4 lever)**:
  - **A1** `tools.py` — execute_sql·scratch_sql CSV 안내문에서 트리거 어휘 제거("핵심 미리보기(수 행)만" → "핵심 몇 행만 인용"). 안내 의미(답변에 전량 붙여넣기 금지)는 불변.
  - **A2** `tools.py` — 절단이 **없을 때** 완전성을 명시(대칭): "(위 표는 이 쿼리가 반환한 N행 **전부**이며 도구는 아무것도 자르지 않았습니다. … '도구 한계/프리뷰 제한 때문에 전체를 볼 수 없다' 고 말하지 마세요 — 단 이 쿼리의 WHERE/LIMIT 범위 밖은 여전히 미확인입니다.)" execute_sql·scratch_sql parity. **완전성 단정은 행·셀·export 3축 모두 미절단일 때만**(§18.8 패널 BLOCKER — `_format_result_sets` 의 셀 100자 절단이 `stats["truncated"]` 에 집계되지 않아 105자만 보인 프로시저 본문에 "절단되지 않았습니다" 가 붙던 허위 완전성). 셀 절단 시엔 `stats["cell_truncated"]` 로 억제하고 대신 "긴 셀 값 N개가 100자에서 잘렸습니다 — …당신은 보지 못했습니다" **명시 마커**를 낸다. **0행 결과에도 대칭 신호**("도구가 자른 것이 아니라 조건에 맞는 행이 없습니다") 부착.
  - **A3** `agent_core.py` SYSTEM_PROMPT — ① 절단 신호를 **열린 집합**으로 재작성(`TRUNCATION NOTICES (PREVIEW-TRUNCATED and every other wording)`: `[truncated]`·절단·잘림·상한 초과·…만 검색·"전체 N행 미리보기"(내 이전 답변의 collapse 마커도 절단)·"정의 구간 A~B" 등). ② 완전성 추론을 **침묵 기반 → 긍정 신호 기반**으로 반전: `COMPLETENESS COMES FROM AN EXPLICIT COMPLETENESS SIGNAL, NOT FROM SILENCE` + "절단 통지 부재는 완전성의 증거가 아니다(일부 도구는 조용히 자른다)". 지어낸 "도구 프리뷰 한계" 금지는 **결과가 완전성을 단정할 때만** 적용. ③ `CHUNKED ROUTINE DEFINITIONS` — 종료 판정을 **머리말 산술(`B == T`)** 로만 하고 **정의 본문 안의 문장은 신뢰하지 말 것**(루틴 작성자가 SQL 에 "마지막 구간입니다" 를 심을 수 있음), 실제 절단 통지가 있으면(MSSQL 카탈로그 폴백 등) 정직히 고지 허용.
  - **B** `tools.py` + `shared/config.py` — `describe_routine(offset)` **문자 offset 이어읽기**. `_window_routine_output` 이 **권위 있는 산술 머리말** `[정의 구간 A~B / 총 T자 — … 마지막 구간: 예/아니오]` 를 **본문보다 앞에** 두고(본문 위조로 덮을 수 없음) 다음 `offset` 을 안내한다. `_routine_chunk_limit()` 는 **auto 기본**(`AGENT_ROUTINE_DEF_CHUNK_CHARS=0` → 창 = `AGENT_TOOL_RESULT_MAX_CHARS - 1000`)으로 **전역 캡이 어차피 자를 지점부터만** 쪼개 캡 이하 정의의 불필요한 조각화를 없애고(패널 MAJOR), `room<=0`·캡 무제한·음수 설정이면 **윈도잉 비활성(0)** 으로 전환해 구 `max(1_000, cap-2_000)` 바닥값이 작은 캡에서 조각 꼬리를 잘라 **전량 도달 경로를 지우던 실패**를 봉인(패널 MAJOR). 양수 설정은 하한 4000·상한 `캡-여유` 로 clamp. 창 이하 + offset 미지정이면 **출력 완전 동일**(회귀 0). offset 형식 오류는 **명시 오류**(조용한 0-폴백 금지), 범위 초과는 **0 으로 클램프 + 사실 통지**(헤더·권한 안내 보존, "이미 마지막 구간까지 조회" 같은 검증 불가 이력 단정 금지). 조각 꼬리에 "문자 단위 절단이라 코드 블록이 끊길 수 있음 + 미열람 구간 단정 금지" epistemic 유지.
- **파일**: `unit/feature-0002-agent-core/src/modules/tools.py`(A1·A2·B + `_format_result_sets` 셀 절단 stats/마커 + `_routine_offset_error` + TOOL_DEFINITIONS offset 파라미터·description), `unit/feature-0002-agent-core/src/agent_core.py`(A3 SYSTEM_PROMPT 3계약 + §ABSENCE 정합), `shared/config.py`(`AGENT_ROUTINE_DEF_CHUNK_CHARS` 신설 + `__all__`), `tests/test_false_truncation_belief.py`(신규 23건), `tests/test_partial_evidence_grounding.py`(stats 키·프롬프트 라벨 계약 반영 2건).
- **왜**: 도구가 완전한 증거를 줬는데 모델이 "도구 한계"를 지어내 분석을 축소하던 마찰의 근본(어휘 충돌·신호 비대칭) 봉인. 동시에 사용자 요구인 "길이 제한 없는 프로시저 본문 조회"를 **캡 완화가 아닌 페이징**으로 충족(컨텍스트 폭주 backstop 유지).
- **호환/안전**: sql_guard·RBAC·datasource 바인딩·PII·datamark 경계 **전부 불변**(순수 도구 피드백 문구 + 출력 윈도잉). §18.8 security 렌즈가 게이트 순서·SQLi·oracle·secret 5축을 실측 반증(윈도잉은 `_safe_ident`→접근게이트→카탈로그 조회→early-return **전부 뒤**의 최종 return 에만 적용, `agent_memory`/allowlist 밖은 DB 쿼리 실행 0회로 차단). 기존 절단 epistemic 계약(FR-partial-evidence)·`(N 행)` 표기·`_cap_tool_result` 동작 미변경. `offset` 은 선택 파라미터라 기존 호출 형태 100% 호환. 스키마/마이그레이션 0.
- **위험등급**: Major(§12.3 — 코어 LLM 프롬프트 + 도구 결과 피드백 경로) → 사용자 scope 결정(AskUserQuestion 2026-07-27) 후 구현 + §18.8 적대 3렌즈 패널 + PR/deploy confirm.
- **수용된 트레이드오프(by-design)**: 초대형 정의 페이징에 회차 예산이 없다(4MB 루틴 ≈ 42회 호출, 조각이 `role=tool` 히스토리로 이후 턴 재전송). **전량 도달이 사용자 명시 요구**라 강제 상한은 요구 위반 → auto 창(호출 수 ~절반)·머리말의 총 문자수 사전 고지·`AGENT_MAX_STEPS`(128) 유한성·음수 kill-switch 로 완화. 선행 CHG-20260724T155534-tool-result-cap-raise 의 동일 축 수용 전례와 정합.
- **Rollback**: `AGENT_ROUTINE_DEF_CHUNK_CHARS` 를 음수로 두면 윈도잉만 즉시 비활성(재빌드 불필요). 전면 롤백은 A1/A2 문구·A3 계약 3줄·`_window_routine_output`/`_routine_chunk_limit`/`_routine_offset_error`/offset 파라미터·`_format_result_sets` 셀 절단 stats·config 상수·테스트 제거(허위 절단 오귀속 + 허위 완전성 + 초대형 정의 도달 불가 재발).
- **Cross-ref**: FRICTION_LEDGER FR-false-truncation-belief · 선행 FR-partial-evidence-false-verification(절단 epistemic 계약 — 본 변경이 그 과발동을 좁힘) · FR-procedure-analysis-result-truncated(`AGENT_TOOL_RESULT_MAX_CHARS` 100k backstop — 유지) · FR-show-create-routine-blocked(describe_routine 신설) · REV-20260727T175800-false-truncation-belief · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260727T185742-false-truncation-belief-deploy-status — 배포 결과 원장 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260727T175800-false-truncation-belief 의 **배포 후 사실 전사**. 코드 변경 0.
- **무엇을**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-false-truncation-belief status `triaged` → `fixed:deployed:unverified-live` + 배포/런타임 실측 증거 기록. `TASK.md` 완료 체크리스트의 배포 항목 체크.
- **근거(측정)**: PR #963 merge main `ef24448c` → `make deploy-web` 전체 스코프 무중단 롤아웃(web-a/web-b + ask-worker/insight-worker + gateway reconcile), post-cutover soak 90s 통과, **4서비스 GIT_COMMIT=ef24448c**, web `/healthz`=ef24448c·mysql_ok·pg_ok. 배포본 ask-worker 런타임에서 신규 계약 실측: 열린 절단신호·"침묵 ≠ 완전"·구 `NO MARKER = COMPLETE` 제거·산술 종료조건·auto 창 99,000·250,000자 정의 머리말·캡 통과 후 `offset=` 안내 생존·60,000자 정의 미분할·셀 절단 stats 분리·offset 형식오류 명시.
- **왜 `verified` 가 아닌가**: 라이브 대화 실측(동일 입력 재현으로 assistant 가 없는 도구 한계를 더는 지어내지 않는지)은 미수행. 원장 규약상 status 는 측정으로만 닫힌다(거짓 done 금지).
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향). **Rollback**: status 문자열 원복.
- **Cross-ref**: CHG/TASK/REV-20260727T175800-false-truncation-belief · REV-20260727T185742-false-truncation-belief-deploy-status · PR #963.

## CHG-20260728T104438-false-truncation-belief-live-verified — 라이브 실측 결과 기록 + 원장 verified 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260727T175800-false-truncation-belief 의 **라이브 실측 전사**. 코드 변경 0.
- **무엇을**: `FRICTION_LEDGER.md` FR-false-truncation-belief `fixed:deployed:unverified-live` → **`fixed:deployed:verified`** + 실측 7항 증거 기록. 실측 중 관측된 별개 축을 신규 항목 `FR-false-absence-zero-row-catalog-scope`(status `triaged`, **미수정**)로 분리 기록. `TASK.md` 라이브 실측 항목 체크.
- **실측 설계**: 배포본 `8db72012`(⊃ `ef24448c`)에서 원 대화와 **동일 조건**(product 117 WEB_QA / `mssql-web-qa`, model `claude-haiku-4`) 재현 대화 `20260728012534-a56ec98e` 3 turn + PG `agent_runtime.core_messages` 로 도구 결과 실물 대조.
- **결과**: ① 오귀속 시그니처 3 turn 전부 **0건**(원 시나리오 동형인 대량 완전 결과 turn 포함) ② 신규 신호 라이브 부착(완전성 4·0행 2·셀절단 3·신규 CSV 안내 9, **구 트리거 어휘 0**) ③ §18.8 BLOCKER 수정 실증(20행 완전 + 셀 13개 절단 → 완전성 **억제** + 마커) ④ 진짜 절단(루틴 482건 목록)엔 기존 경고 유지 — 3축 분기 정확 ⑤ 원 불만 대상 `MSP_SELECT_COMMENT_LIST` 2,386자 전문 수신(`END` 완결) ⑥ corroboration distinct_conv 1→0(**분모 23 assistant msg/4 conv 로 작음** — 결정 근거는 ①③④) ⑦ offset 페이징은 실데이터 미도달(정의 35건 max 7,732자 « 창 99,000, `[정의 구간` 0건) → 동작은 배포본 직접 호출로 검증.
- **정직 표기**: turn1 에서 모델이 2부분 명명 메타뷰 0행을 근거로 "프로시저 0개"라는 **허위 부재**를 단정(실제 482건). **본 변경이 유발한 것이 아님을 baseline 대조로 확인**(배포 전 0행 89건 중 부재 단정 5건 — 기존 base rate). 신규 0행 신호가 불충분했을 뿐이며, 수정은 별도 friction 으로 분리해 사람 결정에 맡긴다.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향, 배포 불필요). **Rollback**: status 문자열 원복 + 실측 절 제거.
- **Cross-ref**: CHG/TASK/REV-20260727T175800-false-truncation-belief · CHG-20260727T185742-…-deploy-status · REV-20260728T104438-…-live-verified · FR-false-absence-zero-row-catalog-scope · PR #963.

## CHG-20260728T114459-false-absence-catalog-scope — 0행→허위 부재 봉인: 루틴 열거 도구 + 카탈로그 스코프 인지 (Major §12.3, 보안 경계 완화 포함)
> 계기: FR-false-truncation-belief **라이브 실측(2026-07-28)** 중 관측된 별개 축. 모델이 `masangsoftweb` 에 "저장 프로시저가 전혀 없습니다 / 0개" 라고 단정했으나 ground truth 는 **472 PROCEDURE + 10 FUNCTION = 482건**. 사용자 지시로 근본원인 규명 후 수정(범위 결정: RC-B 포함).
- **근본원인 (ground truth 대조로 확정, 5층)**:
  - **표층**: 모델이 2-part `INFORMATION_SCHEMA.ROUTINES` + `WHERE ROUTINE_CATALOG='masangsoftweb'` 를 실행. product 117 의 접근 DB 를 `(SortOrder, SchemaName)` 로 정렬한 첫 항목이 `_INDY_STATISTIC`(SortOrder 10)이라 연결은 거기 auto-pin 되고, `masangsoftweb` 은 28개 허용 DB 중 하나다 → 그 메타뷰의 `ROUTINE_CATALOG` 는 항상 `_INDY_STATISTIC` 이므로 **정의상 매치 불가 = 구조적 항상 0행**. 0행은 부재가 아니라 스코프 불일치였다.
  - **RC-A(능력 공백)**: 도구 16종에 **루틴을 열거하는 도구가 없다**(`describe_routine` 은 정확한 이름 필요, `search_tables`/`describe_schema` 는 테이블 전용) → "어떤 프로시저가 있나" 에 답하려면 카탈로그 SQL 을 **손으로 써야** 했다.
  - **RC-B(가드가 정본 경로를 닫음)**: MSSQL 정석인 `sys.objects`·`OBJECT_DEFINITION()`·`db_name()` 이 전부 차단(라이브 msg 5675/5677/5679 실증) → 남는 길이 INFORMATION_SCHEMA 뿐.
  - **RC-C(grounding 공백)**: 프롬프트의 2-part/3-part 규칙이 **user table 기준**이라 메타뷰가 카탈로그 스코프라는 사실이 없었다 → 모델은 규칙을 지킨 쿼리를 썼다.
  - **RC-D(피드백 공백)**: 0행에 스코프 진단 없음. 코드베이스에 `_mssql_crossdb_hint` 관용구가 이미 있고 `describe_schema` 빈 결과엔 쓰는데 freeform 경로엔 미적용.
  - **RC-E(인식)**: 0행 → 부재 단정(배포 전 base rate 89건 중 5건 — 기존 실패 모드).
  - **계보**: 프로젝트는 **이미 같은 실패 모드를 봉인**한 적이 있다(`FR-mssql-crossdb-structured-discovery`, 2026-07-14 — "MSSQL 카탈로그 뷰는 DB별이라 pin 된 DB만 보고 다른 DB 객체를 없음으로 오판"). 그 수정이 **구조화 도구에만** 적용됐고 루틴 열거에는 애초에 도구가 없어 freeform 으로 샜다. 본 변경은 그 봉인의 **누락된 형제**다.
- **무엇을 (5 lever)**:
  - **A** 신규 도구 `search_routines` — `search_tables` 의 cross-DB 패턴 그대로(허용 DB 전체 sweep, `database`/`schema_name` 선택, DB-qualified 반환). MSSQL 은 4000자 절단되는 `INFORMATION_SCHEMA.ROUTINE_DEFINITION` 대신 `sys.sql_modules.definition` 으로 **본문까지** 검색(원 사용자 의도 "문서 조회 프로시저 탐색" 은 이름만으론 불가능). 루틴 타입은 CLR/확장/복제필터 포함(`P,PC,X,RF,FN,IF,TF,FS,FT,AF`). `keyword` **선택**(열거 질의 지원). per-DB 실패·상한 포화를 **항상 명시 고지**.
  - **B(보안 경계)** freeform 의 `sys` **전면 차단** → **DB 스코프 카탈로그 뷰 화이트리스트 21종**(`dialects.safe_sys_views()`)만 허용. 서버 스코프(`databases`/`dm_*`/로그인·주체), `synonyms`(linked server·타 DB 명 노출), `guest`/`db_*` 스키마, 메타데이터 **함수**(문자열 리터럴 인자라 AST catalog 게이트가 못 봄)는 계속 차단. 판정은 `sql_guard.collect_schema_object_refs` 의 `(schema, object)` all-or-nothing 대조.
  - **C** MSSQL 프롬프트에 `CATALOG VIEWS ARE PER-DATABASE` — "2-part 메타뷰 + 다른 카탈로그 필터는 **절대** 행을 반환할 수 없다", 빈 카탈로그 결과는 **스코프의 증거이지 존재의 증거가 아님**, 루틴 열거는 `search_routines`. `sys` 경계 문구는 화이트리스트 SSOT(`_safe_sys_views_phrase`)로 생성해 코드↔프롬프트 불일치를 구조적으로 차단.
  - **D** `_catalog_scope_hint` — 카탈로그 메타뷰를 **catalog 자격 없이** 조회하면 **행 수와 무관하게** 현재 pin DB·다른 허용 DB·대체 경로를 제시. AST 기반이라 `[sys].[objects]` 등 인용 변형을 잡고 문자열 리터럴·주석엔 오발화하지 않으며, 이미 3-part 인 쿼리엔 붙지 않는다. 진단이 붙는 결과엔 완전성 단정을 억제.
  - **E** 0행 문구를 "**0행은 '데이터가 없다'의 증거가 아닙니다**" 우선 프레이밍으로. SYSTEM_PROMPT `ZERO ROWS IS NOT ABSENCE` 는 **메타데이터/카탈로그 조회 또는 스코프 경고 동반 시**로 한정(정당한 업무 0행·표적 probe 는 기존 규칙 유지 — 과교정 방지).
- **파일**: `modules/tools.py`(도구 정의·핸들러·가드 판정·스코프 진단·0행 문구), `modules/dialects.py`(`search_routines` MySQL/MSSQL·`safe_sys_views`), `modules/sql_guard.py`(`collect_schema_object_refs`·`_collect_qualified_func_refs_named`·TSQL forbidden 함수/접두), `agent_core.py`(프롬프트 3곳·SSOT 헬퍼·step 서술 2곳), `feature-0003 routers/_conv_store.py`(step 서술 1곳), 테스트 3파일.
- **호환/안전**: MySQL 경로 **동작 무변경**(`safe_sys_views()` 빈 집합, RC-B 코드는 `engine=="mssql" and active_ds` 블록 안). M1 불변식(시스템 DB catalog 차단)·DB allowlist·pin gate·RBAC·`_safe_ident` 불변. 스키마/마이그레이션 0. 신규 도구는 additive.
- **위험등급**: Major(§12.3 — 코어 프롬프트 + 도구 표면 + **보안 경계 완화**) → 사용자 범위 결정 후 §18.8 적대 3렌즈 **2라운드** + PR/deploy confirm.
- **Rollback**: `safe_sys_views()` 를 빈 집합으로 되돌리면 RC-B 만 즉시 원복(나머지 lever 는 독립). 전면 롤백은 신규 도구·프롬프트 3곳·진단 헬퍼·수집기 확장 제거.
- **Cross-ref**: FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope · 선행 FR-mssql-crossdb-structured-discovery(같은 실패 모드의 구조화-도구 판) · FR-false-truncation-belief(본 축을 실측으로 노출) · REV-20260728T114459-false-absence-catalog-scope.

## CHG-20260728T123229-false-absence-live-verified — 라이브 재실측 결과 기록 + 원장 verified 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260728T114459-false-absence-catalog-scope 의 배포 후 사실 전사. 코드 변경 0.
- **무엇을**: `FRICTION_LEDGER.md` FR-false-absence-zero-row-catalog-scope `fixed:undeployed` → **`fixed:deployed:verified`** + 재실측 증거 기록. `TASK.md` 잔여 항목 체크.
- **근거(측정)**: PR #991 merge main `21b67ade` → `make deploy-web` 전체 스코프(4서비스 GIT_COMMIT=21b67ade, soak 통과, `/healthz` ok). 재현 대화 `20260728031510-16927f9b`(동일 product·모델·질문): 수정 전 "프로시저 0개 / 전혀 정의되지 않았습니다"(실제 482건) → 수정 후 "**총 421개**" + `MSP_SELECT_BOARD_CONTENT` 본문 제시. 오귀속·부재 단정 시그니처 **각 0건**. `search_routines` 루프 실사용 확인. 실행 중 MSSQL 연결 단절 시 **실패 고지가 실전 발동**(구 코드였다면 "검색 결과가 없습니다" 로 위장). 배포본 런타임에서 별칭 그림자·`sys.databases`·`master.sys` BLOCK / `sys.objects`·`sys.partitions`·사용자 UDF `dm_` ALLOW 확인.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향, 배포 불필요). **Rollback**: status 문자열 원복.
- **Cross-ref**: CHG/TASK/REV-20260728T114459-false-absence-catalog-scope · REV-20260728T123229-false-absence-live-verified · PR #991.
## CHG-20260728T133431-alias-shadowed-function-namespace — 별칭 그림자 함수 우회: 증명 가능한 축 봉인 + 열거 oracle 차단 (Major §12.3, 보안 경계)
> 계기: FR-false-absence-zero-row-catalog-scope 의 §18.8 패널이 **pre-existing 구멍**으로 분리 기록한 항목(HEAD 동일). 사용자 지시로 후속 수정.
- **근본원인(구조적)**: T-SQL 에서 `X.Y.f()` 는 **자격 함수호출**(`db.schema.func`)과 **UDT/XML 메서드**(`alias.column.method`)가 문법적으로 동일하다. 종전 수집기 3곳은 UDT 과차단을 피하려고 **leading 토큰이 별칭/테이블/CTE 명이면 무조건 면제**했고, 그래서 DB 명을 별칭으로 선언하는 것만으로 catalog allowlist·4-part 게이트가 무력화됐다. 같은 Dot 워커가 두 의미를 겸용하는 것이 문제의 본질이다.
- **실패한 두 차례 시도(정직 기록 — 왜 이 설계로 왔는지)**:
  1. **이름/토큰 목록 하드닝**: 스키마 슬롯 토큰 목록 + UDT 메서드명 목록. 둘 다 공격자에게 0비용이었다 — 스키마를 임의 사용자 스키마로, 함수명을 `value`/`query`/`st*` 로 바꾸면 통과(§18.8 1R BLOCKER, 20건 이상 실증). 동시에 열거식 목록이 정상 spatial/CLR 29건을 과차단하며 **별칭을 DB 로 오보**했다.
  2. **caller 측 "아는 DB 이름" 대조**: 논리가 뒤집혀 있었다 — `hard_forbidden` 은 애초에 면제 대상이 아니므로 `_bad ⊆ allow_set` 이 되어 **이미 허용된 DB 만 막고 미허용 DB 는 전부 통과**(§18.8 2R BLOCKER). 방어가 약한 쪽으로 기울어 정상 사용자만 막혔다.
- **무엇을 (최종 설계 — 각 계층이 증명 가능한 것만 판정)**:
  - **table-source 위치는 절대 면제 금지**(`_in_table_source`): `CROSS/OUTER APPLY db.schema.tvf(...)` 자리에는 UDT 인스턴스 메서드가 **문법적으로 올 수 없다**(서버는 반드시 `database.schema.TVF` 로 해석) → 면제는 모호성 해소가 아니라 **증명적으로 틀린 해석**이었고, 반환값이 **행 집합**이라 유출 규모가 가장 컸다.
  - **체인 정확히 2토큰만 면제** + **체인 전 토큰**을 보호 네임스페이스와 대조 → 4/5-part linked server 및 그 경유 `master`·`agent_memory`·`msdb` 우회 봉인(종전엔 head 만 검사해 중간 토큰이 무방비).
  - **미지 AST 노드 fail-closed**(`_UNKNOWN_NS` 센티널 + `Paren` 재귀): `(master.dbo).fnLeak()` 은 종전에 namespace 를 못 뽑아 **무판정 통과**였다. 이제 어떤 allowlist 에도 없는 센티널이 들어가 차단된다.
  - **존재 열거 oracle 차단**(`tools._sql_error_message`): 모호 경로로 서버까지 도달한 쿼리의 오류는 원문을 노출하지 않는다. `Msg 916`(DB 접근 불가) ↔ `Msg 4121`(함수 없음) 차이로 **allowlist 밖 DB·객체 존재를 무제한 열거**할 수 있었다(적대 검증이 "전제조건 0 즉시 착취" 로 지목). 모호 경로가 **아닌** 정상 쿼리의 오류는 자기교정에 필요하므로 원문 유지.
  - **오보 제거**: 차단 토큰이 이 문장의 테이블 별칭이면 "허용되지 않은 DB" 대신 별칭 충돌 사실과 해소법을 안내.
- **의도적으로 깨지 않은 계약**: `test_regate7_udt_method_not_overblocked` 는 re-gate(7차)가 **MAJOR 로 못박은 제품 계약**("UDT/CLR/spatial 인스턴스 메서드를 3-part 함수로 오판·차단하지 않는다")이다. 면제를 통째로 제거하면 이 계약이 깨지고, CLR 사용자 정의 타입의 메서드명은 **임의 사용자 코드라 열거가 원리적으로 불가**해 화이트리스트로도 복구할 수 없다. 따라서 계약을 유지했다.
- **미해결 잔여(정직 — 원장 기록)**: **스칼라 위치**의 `alias.col.method()` ↔ `db.schema.func()` 모호성은 SQL 텍스트만으로 해소 불가라 남는다(`SELECT hrdb.dbo.value('a','int') FROM dbo.Orders hrdb`). 다만 **데이터 접근의 권위적 경계는 앱 가드가 아니라 per-DB USER/GRANT** 이며, `bin/datasource-mssql-ro-bootstrap.sql` 이 ① **단일 TARGET_DB 에만** USER 생성 ② `db_datareader` 명시적 제거 ③ 허용 스키마에만 `GRANT SELECT`(EXECUTE 미부여) 로 구성되어 **미허용 DB 에는 로그인 principal 자체가 없다**. 즉 잔여의 데이터 유출 경로는 부트스트랩 준수 하에서 닫혀 있고, 정보 채널(열거 oracle)은 위에서 닫았다. **의존성 명시**: 이 결론은 부트스트랩 준수를 전제한다 — datasource 추가 시 해당 스크립트로만 프로비저닝해야 하고, 수동으로 `db_datareader`/전역 USER 를 부여하면 잔여가 실착취로 승격된다.
- **파일**: `modules/sql_guard.py`(`_in_table_source`·`_alias_exempt` 재설계·`_UNKNOWN_NS`·`Paren` 처리·`collect_alias_shadowed_heads`·`collect_table_alias_names`), `modules/tools.py`(별칭 인지 차단 메시지·`_sql_error_message`), `tests/test_false_absence_catalog_scope.py`(회귀 가드를 **유효 T-SQL exploit 형상**으로 — 종전 2회는 실패 변종(무효 T-SQL)을 assert 해 봉인을 오인증했다).
- **호환/안전**: MySQL 경로 무영향. M1·DB allowlist·`sys` 화이트리스트·서버 스코프 뷰·메타데이터 함수·TVF piggyback·`sys` 별칭 그림자 전부 불변(적대 검증 17건 전수 재측정). re-gate(3차) 4-part 계약·re-gate(7차) UDT 계약 both PASS. 스키마/마이그레이션 0.
- **위험등급**: Major(§12.3 — freeform SQL 보안 게이트) → §18.8 적대 security **2라운드** + PR/deploy confirm.
- **Rollback**: `_alias_exempt` 를 종전 무조건 면제로, `_sql_error_message` 를 원문 반환으로 되돌림(단 우회·oracle 재개통).
- **Cross-ref**: FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope 후속 triage · CHG-20260728T114459-false-absence-catalog-scope · REV-20260728T133431-alias-shadowed-function-namespace · `bin/datasource-mssql-ro-bootstrap.sql`(권위적 경계).
## CHG-20260728T124500-llm-usage-target-scope (llm_usage.target_scope — 사용 기록 데이터소스 귀속 근본 해소)

TASK-20260728T124500-llm-usage-target-scope. branch `ai/claude/feature-0002-llm-usage-target-scope`.

- `alembic/versions/20260728_0047_llm_usage_target_scope.py` **신규** — `agent_runtime.llm_usage`
  에 `target_scope VARCHAR(96)` nullable 추가(`ADD COLUMN IF NOT EXISTS`, 멱등).
  소급 백필 **안 함**(과거 행의 정확한 스코프는 복원 불가 — 추측 백필은 잘못된 귀속 생성).
  `MAX_MIGRATION.txt` 갱신 · `src/scripts/agent_runtime_schema.sql` parity 반영.
- `src/modules/llm.py`
  - `_record_llm_usage(..., target_scope=None)` — 명시 인자 우선, 미전달 시
    `cfg.get_active_datasource()`(ContextVar) 폴백. 96자 클립.
  - INSERT 폴백을 **4단 사다리**(target_scope → step_gap → latency+target → latency)로 재구성.
    종전 3중 중첩 try 를 후보 리스트 루프로 평탄화 — 단계 추가 시 중첩이 늘지 않는다.
    공통 8컬럼 순서·인덱스는 계측 회귀 테스트 계약대로 보존.
  - `llm_schema_insight` · `llm_table_insight` · `llm_node_analysis` · `llm_product_classify` ·
    `llm_cluster_label` 에 keyword-only `scope_key` 추가 → `_record_llm_usage` 로 전달.
    **프롬프트 payload 는 건드리지 않았다** — 모델 입력·semantic_cluster 캐시 키 무영향(§12.3 2차-효과).
- `src/modules/node_analysis.py` — 병렬 `_run_llm` 에서 `scope_key=w.get("scope_key")` 전달.
- `src/modules/semantic_cluster.py` — 직렬·병렬 라벨 호출 모두 `scope_key=datasource_key` 전달.
- `src/modules/product_classify.py` — `scope_key=scope` 전달(`target` 은 표시용 ds 라벨과 별개).
  → 이 3곳은 **스레드 경계**라 ContextVar 가 전파되지 않아 명시 전달이 필수다.
- `unit/feature-0003-agent-web-ui/src/routers/admin_usage.py`
  - 집계 질의가 `COALESCE(u.target_scope,'')` 를 SELECT·GROUP BY. **컬럼 부재 시** rollback 후
    리터럴 `''` 로 같은 인덱스를 채우는 폴백 SQL 재조회(ai_ops `_query_activity` 패턴과 동형).
  - fold 키 `(task, target, actor)` → `(task, target, actor, scope)` — 같은 객체라도 데이터소스가
    다르면 별 행(이 컬럼의 존재 이유). legacy NULL 끼리는 종전대로 하나로 묶인다.
  - 기록된 scope 가 있으면 **역해소를 건너뛴다**(정확한 값을 추정으로 덮지 않음).
    응답에 `scope_source`(`"recorded"` | `None`) 추가 — 기록/추정 구분 관측용.
- 테스트: `test_usage_records_system.py` R1~R4 신규(기록값 우선·legacy 역해소·데이터소스별 행 분리·
  컬럼 부재 폴백) · `test_llm_usage_record.py` 0047 3케이스(명시·ContextVar·96 클립) +
  꼬리 인덱스 계약 갱신 · `test_ai_ops.py` 사다리 단수/인덱스 정합 ·
  테스트 더블 arity 7건 확장(`lambda payload` → `**_kw` 수용).

검증: pytest **2,719 PASS / 2 skipped** · ruff clean · `migrate-lint` expand-safe PASS.
배포 순서 안전(expand-only): 구 코드 INSERT·신 코드 컬럼부재 INSERT·신 웹 컬럼부재 SELECT 모두
자가치유. RBAC·인증 변경 0.

## CHG-20260728T124500-llm-usage-target-scope-postverify (0047 POST-DEPLOY 라이브 실증 종결 — docs-only)

TASK-20260728T124500-llm-usage-target-scope. branch `ai/claude/feature-0002-llm-usage-target-scope-verify`.
코드 변경 없음 — 배포본 `754263ab` 실측 결과를 정본에 반영.

- `docs/test-runs.d/20260728T124500-llm-usage-target-scope.md` — verdict PENDING → **PASS** +
  POST-DEPLOY 절 추가(마이그 적용 · 계측 e2e 양 경로 · API `scope_source`/행 분리 · 원장 위생 ·
  채움률 한계 정직 표기).
- `docs/REPORT.md` — 본 cycle 스냅샷 + POST-DEPLOY 결과.
- `docs/TASK.md` — POST-DEPLOY 체크박스 종결.

## CHG-20260728T150510-alias-shadow-server-resolution-verified — 잔여 착취 불가 확정 + 오류 원문 은폐 철회 (Minor §12.3)
> 선행 CHG-20260728T133431-alias-shadowed-function-namespace 의 잔여를 **라이브 실증으로 확정**. 사용자 결정: "라이브 해석 확인 우선" → 결과 반영.
- **실증(QA SQL Server 2017 / 14.0.3238.1 Web Edition, datasource `mssql-web-qa` / `masangsoftweb`)**:
  - ① 별칭 = **미존재** DB명 → `Msg 207 Invalid column name 'dbo'`
  - ② 별칭 = **실존** DB명(`Shop`·`Web_SR`) → `Msg 207 Invalid column name 'dbo'` — **①과 완전히 동일**
  - ③ 별칭 없음(동일 3-part) → `Msg 4121 Cannot find either column … or the user-defined function "zzz_notadb.dbo.whatever"`
  → SQL Server 는 `alias.col.method()` 를 **별칭 우선(컬럼)** 으로 해석한다. 테이블을 DB 명으로 별칭 지어 cross-DB 함수를 부르는 것이 **불가능**하고(잔여 착취 불가), 오류 문구가 **DB 존재 여부에 불변**이라 열거 oracle 도 성립하지 않는다.
- **무엇을**: 위 oracle 을 막으려 넣었던 `tools._sql_error_message`(모호 경로 서버 오류 원문 은폐)를 **철회**하고 원문 반환으로 되돌렸다. 근거가 반증된 방어이며, 유지하면 `Invalid column name 'dbo'` 처럼 **모델의 자기교정에 필요한 정보만** 가리는 순손실이다. 철회 근거는 코드 주석에 프로브 결과와 함께 남겨 재도입을 막고, 테스트가 그 주석·헬퍼 부재를 지킨다.
- **유지**: APPLY(table-source)·4/5-part·`Paren`/미지 노드 봉인은 그대로 — 그 위치들은 컬럼 해석이 **문법적으로 불가**해 서버가 반드시 `database.schema.함수/TVF` 로 해석하므로(프로브 ③ 경로) 게이트 판정이 서버 동작과 일치한다.
- **판단 정정**: 적대 검증 1R BLOCKER-1 은 **게이트 레벨 ALLOW 만** 근거로 한 판정이었고 서버 동작을 검증하지 않았다. 나 역시 검증 수단이 없어 "위험한 쪽으로 가정" 해 받아들였다. 이 실증이 그 전제를 반증한다 — 보안 판정에서 **가정을 실측으로 대체한 사례**로 기록한다.
- **파일**: `modules/tools.py`(은폐 철회 + 근거 주석), `tests/test_false_absence_catalog_scope.py`(문서화 가드로 교체), `docs/{FUNCTION,TASK}.md`, FRICTION_LEDGER.
- **위험등급**: Minor(정보 노출 **축소가 아니라 복원** — 실증으로 무해 확인). **Rollback**: 은폐 헬퍼 재도입(단 근거 없음).
- **Cross-ref**: CHG/REV-20260728T133431-alias-shadowed-function-namespace · REV-20260728T150510-alias-shadow-server-resolution-verified · FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope.

## CHG-20260728T163000-graph-cypher-volume — 그래프 sync cypher 호출량 감축 (Major §12.3)
> feature-0026 계측이 지목한 최상위 PG 비용(`ag_catalog.cypher` 누적 32,072초 / 696만 호출)의 귀속을 실측하고 지배 항목 2개를 제거.
- **측정(라이브, 2026-07-28)**: 전량 sync 1회 = cypher **158,544 회 / PG 실행 867초**(wall 1,148초의 75%). `pg_stat_activity` 샘플링 프로파일에서 루틴 엣지 연산이 지배(74 샘플 중 62). 전량 sync 는 매일 04:17 cron.
- **W1 정점 중복 MERGE 제거**: Schema 정점이 테이블·루틴마다 재-MERGE 됐다(rag 16,367 + routines 23,053 → distinct ~370). 소속 Table 정점도 컬럼마다(3,135 → 389), 루틴 참조 앵커도 참조마다(28,034 → 7,331) 재-MERGE. feature-0029 의 anchor 캐시를 `sync_table`/`sync_column`/`sync_routine` 으로 확장하고 4단계가 **공유**한다.
  - 마크에 **속성을 포함**(`_vmark`) — 단계마다 Table 에 싣는 속성이 달라(rag=클러스터, tables=description, columns/routine=이름) 키만으로 dedup 하면 먼저 실행된 단계가 뒤 단계의 속성 투영을 영구히 삼킨다. 같은 fqn 을 다르게 분해하는 실제 충돌(`a.b.c` → columns 는 table='b.c', routine 앵커는 table='c')을 테스트로 잠갔다.
  - pending/committed 2단 규약은 feature-0029 그대로. 배치 커밋 실패(`_tick`)·step 롤백(`_run_step`) 양쪽에서 `anchor_cache_reset` — 확정 마크를 남기면 정점이 실제로 사라진 뒤 후속 MERGE 가 생략돼 `_merge_edge` 가 조용히 0행(엣지 소실)이 된다.
- **W2 ROUTINE_USES 조건부 재작성**: routine 마다 참조 엣지를 전량 DELETE 후 재-MERGE 했다(DELETE 23,053 + 엣지 MERGE 28,034 = **전체의 32%**). 실제로 참조가 바뀌는 routine 은 하루 수백 건. `routine_refs_signature`(fqn·kind·cross 정규화 sha1)를 Routine 정점 `refs_sig` 속성에 두고, step 진입 시 **cypher 1회로 전량 선조회**(라이브 23,057 행 / 3.2ms) → 서명 일치 시 재작성 생략.
  - 서명 SET 은 엣지 재작성 **뒤**에 별도로 기록한다. 정점 MERGE 에 함께 실으면 autocommit(비-owned) 모드에서 서명이 엣지보다 **먼저 커밋**돼 '서명은 최신, 엣지는 불완전'이 영구 고착된다(다음 sync 가 skip → 자가치유 상실). 비용은 참조가 바뀐 routine 1건당 1회.
  - 서명 부재(신규·배포 직후)·선조회 실패는 miss → 전량 재작성(종전 동작)으로 graceful.
- **§18.8 적대 패널 2렌즈가 잡은 결함 8건 흡수** (초안은 **최종 그래프 상태가 종전과 달라지는** 결함을 포함하고 있었다 — 초안 문서의 "불변: 그래프 최종 상태 동일" 주장은 그 시점엔 거짓이었고, 아래 수정으로 비로소 참이 되었다):
  - **MAJOR-1 (실행 입증)**: 정점 key `scope:schema.name()` 에 routine_type 이 없는데 SSOT 유일키는 (scope, schema, name, **type**) 이다 — MySQL 동명 FUNCTION/PROCEDURE 가 한 정점을 공유한다. `sig_cache` 는 step 진입 1회 스냅샷이라 두 번째 행이 stale 항목과 일치해 **재작성을 건너뛰고 첫 행의 엣지를 최종 상태로 남겼다**(종전은 마지막 행 우선). 게다가 sync 마다 승자가 뒤바뀌는 **영구 flip-flop**. → `_cache_once(cache, ("ROUTINE_REFS", rkey))` 첫 방문 게이트로 종전 semantics 복원.
  - **MAJOR-2**: 서명 SET 예외를 삼키면 PostgreSQL 이 tx 를 aborted 로 둔 채 `_sync_row_guard` 가 `RELEASE SAVEPOINT` 실패까지 삼키고 **성공(True)** 을 반환 → 다음 step 커밋이 조용히 ROLLBACK 으로 수렴해 **최대 500행 소실 + `ok:true` + 워터마크 전진**. 이 문이 routine 행의 마지막 문이라 오류를 드러낼 후속 문이 없다는 게 핵심. → 삼키지 않고 전파(행 SAVEPOINT 롤백 + errors 집계).
  - **B3/MAJOR-3**: 서명만 보면 `--full` 이 문서상 보장하던 **무조건 재조정**이 사라져, refs 변경을 동반하지 않은 엣지 소실(`_merge_edge` 는 끝점 정점 부재 시 오류 없이 0행)이 영구 고착되고 운영 탈출구가 없었다. → 선조회에 **실제 ROUTINE_USES 차수**(cypher 1회, 라이브 19,870행/74ms)를 추가해 서명이 같아도 차수가 기대치와 다르면 재작성. 안전망을 O(1) 로 복원하면서 전량 재작성 51,087회는 되살리지 않는다.
  - **M3**: autocommit(비-owned) 경로에서 DELETE 커밋 후 엣지 MERGE 중간 실패 시 정점에 **직전 서명이 남아** 있고, 참조 미변경 재작성이었다면 그 값이 현재 서명과 같아 이후 모든 sync 가 skip → 부분 엣지 영구 고착. → 재작성 진입 전 `REMOVE r.refs_sig` 선행(순서: REMOVE → DELETE → 엣지 MERGE → SET).
  - **M1 (교차 feature 회귀)**: 2열 선조회의 튜플 언패킹이 1-튜플을 돌려주는 하네스에서 `ValueError` → rollback → `feature-0016 test_metadata_graph_load_spread` 가 **실제로 깨졌다**(HEAD 1건 → 변경 후 2건). CI 게이트는 feature-0016 을 돌리지 않아 미검출. → 인덱스 기반 방어적 판독으로 수정, 해당 테스트 복구 확인.
  - **M2**: 선조회 실패가 완전 무음이라 최적화가 영구 0이 돼도 신호가 없었다. → `_err_samples` 기록.
  - **MINOR-1**: 중복 fqn 에서 엣지 루프는 마지막이 이기는데 서명은 정렬만 해 순서 무관 → 최종 엣지가 다른데 서명이 같아지는 경우 존재. → 서명도 fqn 기준 last-wins 로 접은 뒤 정렬.
  - **MINOR-2 / 실패지점 이동**: 선조회에 scope 필터 추가(전량 덤프 금지 규약), `routine_refs_signature` 를 JSON 문자열·비-dict 원소에 방어적으로 — 이 함수는 정점 MERGE **이전**에 호출되므로 여기서 raise 하면 종전에는 만들어지던 Routine 정점·HAS_ROUTINE 까지 잃는다.
- **테스트 강화 (QA 패널: 초안 28 변이 중 17 생존)**: 초안은 리프 함수만 문자열 매칭해 **`sync_graph` 배선이 0% 검증**이었고, fake 커서의 `fetchall` 이 항상 빈 리스트라 **선조회 루프가 한 번도 실행되지 않아** 쓰기/읽기 속성명 커플링이 안 잠겼다(prefix 매칭이라 `refs_sig2` 로 바꿔도 통과 — `psycopg.Cursor.__slots__` 선례와 같은 '라이브에서 100% 무효인데 초록' 결함면). → `sync_graph` 를 끝까지 구동하는 harness(`_SyncCur`/`_SyncConn`, `__slots__` 로 속성 부착 금지) 추가, 속성명은 정규식으로 뽑아 **동일성** 검증, 롤백된 행이 캐시를 오염시키지 않는지 end-to-end 확인. 최종 **31건**.
- **역검증**: 초안 4축 + 패널 지적 변이 12종을 각각 되돌려 해당 테스트가 실패함을 확인(생존 0). 첫 시도의 layering 테스트는 캐시 미보호 지점을 찔러 회귀를 못 잡았고, 역검증이 그 결함을 드러내 실제 충돌 형상으로 교체했다.
- **파일**: `modules/metadata_graph.py`, `tests/test_graph_cypher_volume.py`(신규 31건), `docs/{FUNCTION,TASK}.md`.
- **위험등급**: Major(그래프 쓰기 경로 · 잘못되면 엣지 조용한 소실). **Rollback**: 커밋 revert — 스키마 변경 없음, `refs_sig` 속성은 잔존해도 무해(다음 sync 가 재작성).
- **Cross-ref**: feature-0029 churn-e(anchor 캐시 원형 · B-4 규약) · ADR-016(ROUTINE_USES) · feature-0026 계측.

## CHG-20260728T175400-cyvol-scope-prefetch-fix — cyvol 차수 선조회 cypher 조립 결함 수정 (Minor §12.3, 최적화 복구)

`unit/feature-0002-agent-core/src/modules/metadata_graph.py` — cyvol 선조회(feature-0030 W2)의
scope 술어를 **쿼리별로 패턴 뒤에** 붙이도록 조립 변경.

- 종전: `_scope_pred`(` WHERE r.scope_key = '<scope>'`) 를 두 쿼리 모두 **노드 패턴 직후**에 고정
  보간 → 차수 쿼리는 그 뒤에 관계 패턴이 이어져
  `MATCH (r:Routine) WHERE r.scope_key = 'x'-[u:ROUTINE_USES]->() RETURN r.key, count(u)` 가 되고
  PG(AGE)가 `syntax error at or near ":"` 로 거부. `scope_key is None` 경로만 유효했으므로
  **모든 per-datasource sync** 의 차수 선조회가 도입 이래 항상 실패했다.
- 수정: 서명 쿼리는 `MATCH (r:Routine){_sp} RETURN …`, 차수 쿼리는
  `MATCH (r:Routine)-[u:ROUTINE_USES]->(){_sp} RETURN …` — openCypher 의 `WHERE` 는 패턴 전체 뒤에만
  올 수 있다는 규칙을 코드 형태로 고정하고, 발견 경로·영향·재발 방지 근거를 주석에 남겼다.
- **정합성 영향 없음(종전도 fail-safe)**: 실패 시 빈 차수 dict → `_routine_edges_intact` 가 차수
  0 ≠ 기대치로 판정해 전량 재작성으로 강등됐다. 복구되는 것은 ① 스코프 sync 의 cyvol W2 감축
  (실측 전체의 32%) ② B3 재조정 안전망의 차수 판정 ③ 매 스코프 sync 1회씩 돌던 불필요한
  `rollback()` + `anchor_cache_reset()`.

`unit/feature-0002-agent-core/tests/test_graph_cypher_volume.py` — 회귀 잠금 3건 + 하네스 보강:
- `_assert_cypher_parses` 를 `_SyncCur.execute` 에 배선 — mock 이 **PG 대신** malformed cypher 를
  거부한다(한 절의 `WHERE` 이후 `RETURN` 전 구간에 `-[` 가 있으면 문법 오류). 이 가드 없이는
  문자열 단정만 가능해 "그 문장이 라이브에서 죽는다"를 행위로 표현할 수 없었다.
- `test_scoped_degree_prefetch_cypher_is_wellformed` — 구조 단정(`'ds-x'-[` 부재 + `WHERE` 가
  관계 패턴보다 뒤).
- `test_scoped_prefetch_result_actually_skips_rewrite` — end-to-end: 스코프 경로에서도 선조회가
  소비돼 `DELETE u` 가 없고 rollback 이 0.
- `test_unscoped_prefetch_stays_wellformed` — 무-scope 경로 무회귀.

검증: 신규 3건을 **수정 전에 먼저 실행해 2 FAIL 재현**(기존 32건은 전부 통과 — 기존 스위트가 이
결함을 구조적으로 놓쳤음이 실증) → 수정 후 대상 3파일 **86 PASS** · feature-0002 전체 스위트를
main 기준선과 동일 하네스로 대조해 **실패 집합 차집합 양방향 0**(base 32 / fix 32, 전부 마운트
레이아웃 artifact) · **라이브 PG/AGE ground-truth** 로 수정 전 형태의 `syntax error at or near ":"`
재현 + 수정 후 형태의 실제 행 반환 확인. UI 표면 변경 0 · alembic 마이그 0 · RBAC/엔드포인트 무변경.

Cross-ref: REVIEW REV-20260728T175400-cyvol-scope-prefetch-fix ·
`docs/test-runs.d/20260728T175400-cyvol-scope-prefetch-fix.md` ·
선행 CHG-20260728T163000-graph-cypher-volume(도입 cycle) ·
발견 경로 `unit/feature-0016-metadata-graph/docs/REPORT.md` 의 routine-column-edges POST-DEPLOY 절.

## CHG-20260728T182000-cyvol-scope-prefetch-postdeploy (cyvol scope-prefetch 수정 POST-DEPLOY 재확인)

코드·자산 변경 **0**. PR #1022 머지(main `44fe939d`) + 전체 롤아웃(web 롤링 + 워커 + gateway
reconcile, soak 통과) 이후 라이브 배포본에서 결함 소실을 재확인한 기록.

- 배포: web-a/web-b/ask-worker/insight-worker 전부 `44fe939d`. `metadata_graph.py` 는 워커(sync)와
  web(그래프 조회 API) 양쪽이 쓰므로 전체 스코프 롤아웃(`--web-only` 아님).
- 오류 소실: 스코프 지정 backfill(`--scope mysql-ddae8975d793` — 결함이 항상 발동했던 경로)의
  sync_graph 리포트가 `errors=6`(routine_prefetch SyntaxError 포함) → **`errors: []`**,
  워커 로그의 `routine_prefetch`/`syntax error` **0회**.
- 데이터 무손상 + 멱등: mysql-local scope `ROUTINE_USES` 601 엣지 / `ref_columns` 370 ·
  스코프 backfill 연속 2회 `with_cols` 257 불변.
- 커버리지(귀속 분리): `cols` 보유 routine 5,807 → **7,377**, AGE `ref_columns` 엣지 2,725 → **9,269**,
  `cols` 보유 scope 5 → **8**. 같은 창에서 backfill 재실행·워커 cadence·본 수정이 함께 작용했으므로
  **본 수정 단독 효과로 주장하지 않는다**(기여 분리 미측정).

미해결 관측(§8.1 기록만): 1차 전체 backfill(수정 전 이미지) 이후 mysql-local `with_cols` 가 6 으로
불변이었는데 수정 후 스코프 실행에서 257 로 수렴했다. 파서(`routines.py`)는 두 이미지 간 바이트
동일이고, 본 결함의 rollback 은 그래프 커넥션에만 작용해 `routine_objects` 미persist 의 원인일 수
없다(코드 독해). 유력 후보는 `introspect_and_store` 의 예외 삼킴("0/부분 카운트 반환")으로 고부하
창에서 컬럼 인벤토리 실패가 **커버리지를 조용히 줄인 채 exit 0** 이 되는 경로다. 1차 리포트가
유실되어 확정하지 못했다. 개선 후보(미실행): 부분 실패를 반환값·리포트에 구분 신호로 남기고
per-schema `cols` 채움 수를 리포트에 포함.

Cross-ref: REVIEW REV-20260728T182000-cyvol-scope-prefetch-postdeploy ·
`docs/test-runs.d/20260728T182000-cyvol-scope-prefetch-postdeploy.md` ·
수정 cycle CHG/REV-20260728T175400-cyvol-scope-prefetch-fix.

## CHG-20260729T110000-dataplane-conn-liveness (데이터플레인 연결 liveness + 같은 좌표 재연결)

**무엇을**: run-scoped 데이터플레인 연결을 tool 에 넘기기 직전 liveness 를 확인하고, 죽었으면
**같은 좌표로만** 재연결한다. 라우터 경로(`_DatasourceRouter.conn_for`)는 label 캐시를 갱신하고,
단일 datasource 경로는 새 소유자 `_DataplaneConn`(agent_core 가 등록)이 갱신을 보유한다.

**왜**: run 시작에 1회 수립한 연결이 그 run 의 모든 tool 호출에 재사용되는데 liveness 검사·재연결이
없어, 연결이 죽는 두 경로 어느 쪽이든 **남은 tool 전부**가 드라이버 문구로 실패했다.
- (a) 유휴 사망 — 첫 tool 까지 LLM 추론이 수 분(실측 232초). 라이브 실험에서 대상 datasource 는
  60~120초 유휴에 절단됐고(대조 datasource 는 생존), 사망 순간 `DBPROCESS is dead`,
  그 이후 모든 사용이 `Not connected to any MS SQL server` — 사고 전사와 같은 순서.
- (b) in-run 사망 — 쿼리 타임아웃이 세션을 죽인 뒤 4초 만에 온 다음 tool 부터 전부 실패.

**어느 RC**: `FR-dataplane-conn-stale-no-reconnect` (L4↔L8). 원장 정본은
`docs/improvements/conversation-audit/FRICTION_LEDGER.md`.

**재발 봉인 방식**: 재발 경로가 *infra idle-timeout drift* + *모델 지연 drift* 라 우리가 통제할 수
없다 → **코드가 권위선**. 데이터 row·설정 조정이 아니라 재사용 choke-point 에 liveness 계약을 둔다.

### 변경
- `shared/config.py` — `AGENT_DS_CONN_PING_IDLE_SEC`(기본 30초, ping 생략 임계. 0=항상 ping).
- `unit/feature-0002-agent-core/src/modules/tools.py`
  - `_ping_conn` / `_mark_conn_used` / `_mark_conn_suspect` / `_conn_needs_ping` / `_ensure_live_conn`
  - `_DataplaneConn` + `set/reset_active_dataplane_conn`(단일 경로 소유자, ContextVar)
  - `_DatasourceRouter.conn_for` — 캐시된 죽은 연결 교체
  - `execute_tool` 양 경로 — 사용 직전 확보 + 결과/예외로 연결 상태 갱신(`_note_conn_outcome`)
  - `is_dead_conn_error` / `_dataplane_error_text` — 끊김 문구 정직화
  - `_tool_execute_sql` 부하게이트 — 추정 실패 원인을 liveness 로 구분(연결 문제면 "쿼리를 좁혀라" 금지)
  - `_search_tables_mssql` — per-DB 실패 삼킴 제거(형제 `_search_routines_mssql` 과 대칭)
  - `_search_routines_mssql` — 끊김 시 suspect 표시 + 짧은 원인 문구
- `unit/feature-0002-agent-core/src/agent_core.py` — 단일/eval 경로에 재연결 클로저 + holder 등록·해제,
  종료 시 holder 를 통한 close(재연결됐으면 살아있는 쪽을 회수).

### 보안 불변식 (변경 없음)
- 재연결은 **호출측이 준 인자 없는 콜백 하나**로만 — 좌표를 여기서 재해석하지 않아 다른
  datasource/DB 로 새는 경로가 구조적으로 없다. 콜백은 `connect_with_retry(database=…, datasource=…)`
  라 회로차단기·`database=None`(schema-prefixed 강제, M-1)·allowlist 게이트가 그대로 유지된다.
- 재연결 실패는 삼키지 않고 전파(fail-closed) — 폴백 연결 없음.
- 부하게이트는 두 분기 모두 **실행하지 않고 차단**한다(fail-closed 강도 불변).
- 세션 스코프 상태(`SET SESSION max_execution_time`)는 `_apply_query_cap` 이 매 호출 재-SET 이라
  재연결 후에도 재적용된다.

### 실패한 문장은 재시도하지 않는다
(b) 는 서버에 도달했을 수 있어 자동 재실행이 부하를 2배로 만든다. 그 tool 만 정직히 실패시키고
**다음 tool 부터** 자동 복구한다 — 유휴 사망 (a) 는 애초에 문장이 서버에 닿지 않아 완전 봉인된다.

Cross-ref: TASK-20260729T110000-dataplane-conn-liveness ·
REVIEW REV-20260729T110000-dataplane-conn-liveness ·
원장 `FR-dataplane-conn-stale-no-reconnect`.

## CHG-20260729T160000-test-live-pg-isolation — 테스트 라이브 PG 격리 완결 + PG 연결 저하 계약 단일화

**동기**: `make test` 가 라이브 Postgres 를 실제로 읽어(운영 `.env` 상속 + compose 네트워크 도달)
attachment 계열 13건이 고정 실패하고, 반대로 라이브 PG 생존에 의존해 통과하던 테스트도 생겨
"main 기준선과 동일한 N건 실패" 가 세션마다 다른 N 으로 반복 관측됐다. 상세 = TASK 동명 섹션.

### 변경
- `Makefile` — `TEST_ISOLATION_ENV` 에 `AGENT_KB_PG_PORT=1` · `AGENT_KB_PG_PORT_RO=1`(PG 도달
  차단) + `AGENT_RUNTIME_READ_BACKEND` · `AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND` ·
  `AGENT_KB_READ_BACKEND` = `mysql`(운영 cutover 스위치 중립화). 유보 주석 갱신.
- `conftest.py` (신규, 저장소 루트) — 같은 격리를 하네스 밖에서도 강제하는 2중 방어. module-level
  적용(모듈이 import 시점에 `os.environ` 을 굳히므로 fixture 로는 늦다).
  escape = `AGENT_TEST_ALLOW_LIVE_BACKENDS=1`.
- `shared/db.py` — `_pg_conn_pair_ro` / `_pg_conn_pair_rw` 신설. `(conn, owned)` 페어의 정본.
  **RO 는 접속 실패도 `(None, False)` 로 저하**(warning 1줄, traceback 없이 사유만),
  **RW 는 설정 미비만 저하하고 접속 실패는 전파**(비대칭은 의도 — 아래 "동작 변경" 참조).
- `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis,relationships,routines,
  semantic_cluster,kb_metadata,kb_glossary,sample_queries}.py` — 각자 복제하던 `_ro_conn`/`_rw_conn`
  11곳을 위 정본으로 위임. 함수 자체는 남긴다(테스트가 모듈 속성을 monkeypatch 한다).

### 동작 변경 (프로덕션) — 읽기만, 쓰기는 불변
**RO(읽기)**: PG 접속 실패 시 예외 전파 → **빈 결과 저하**로 바뀐다. 읽기 호출부는 전부 이미
`if c is None:` 저하 분기를 갖고 있었으므로 코드 경로는 새로 생기지 않고, 그 분기가 비로소
의도대로 도달된다. docstring("실패/라벨 부재 시 [] 로 저하 — 비차단")과 실제 동작이 처음으로 일치.

**RW(쓰기)**: **동작 변경 없음**(설정 미비만 저하, 접속 실패는 전파 — 기존과 동일). 초안에서는
쓰기도 저하시켰으나 커밋 전 자체 검토에서 회귀를 발견해 되돌렸다: `sync_graph` 는 접속 실패 시
초기 리포트(`errors=0, step_failures=0`)를 그대로 반환하고 `scripts/metadata_graph_sync.py:55,64`
가 이를 `ok=True` → `return 0` 으로 해석하므로, **cron(`bin/metadata-graph-sync.sh`)이 PG 순단을
exit 0 으로 받아 그래프가 stale 해져도 아무도 모르게 된다.** 읽기 저하는 데이터 정합성을 훼손하지
않지만 쓰기 실패 은폐는 관측성 손실이라, 비대칭을 의도적으로 남겼다.

### 안전성
- 자격증명·SSRF allowlist·회로차단기 경로 불변 (`_pg_connect{,_ro}` 본문 무수정, 호출만 감쌈).
- RO 저하는 silent 아님 — `agent_core.db` 로거에 warning. 순단 시 로그 폭주 방지로 traceback 생략.
- 쓰기 경로(`_rw_conn`) 는 접속 실패를 계속 전파 — sync 실패가 성공으로 보고되는 경로 없음.
- 테스트가 운영 DB 에 쓰기를 시도하던 경로(product PATCH)가 구조적으로 차단됨.

Cross-ref: TASK-20260729T160000-test-live-pg-isolation ·
REVIEW REV-20260729T160000-test-live-pg-isolation.

## CHG-20260729T183000-test-live-pg-isolation-postdeploy — 배포 후 라이브 실증 기록 (문서만)

**실행 코드·정적 자산 변경 0줄.** 선행 CHG-20260729T160000-test-live-pg-isolation 이 바꾼 PG 연결
계약(RO 저하 / RW 전파)이 배포본 `c16e3a84` 에서 설계대로 동작함을 확인하고 기록한다.

### 변경
- `unit/feature-0002-agent-core/docs/TASK.md` — POST-DEPLOY 실증 섹션(실측 항목 + 검증 방법 함정).
- `unit/feature-0002-agent-core/docs/REVIEW.md` — REV-20260729T183000 항목.

### 실증 요지 (repo-web-a-1)
정상 경로 RO 연결·`SELECT 1`·그래프 읽기 3건 정상 / PG 도달 불가 시 RO 는 `(None, False)` + warning
1줄, RW 는 `OperationalError` 전파. 후자가 `sync_graph` 실패의 exit 0 위장을 막는 지점이다.

Cross-ref: TASK-20260729T183000-test-live-pg-isolation-postdeploy ·
REVIEW REV-20260729T183000-test-live-pg-isolation-postdeploy.

## CHG-20260730T160000-ask-redeploy-handoff — 재배포 인계: 고아 ask job dead-air 봉인

**무엇을**: 배포가 ask-worker 를 재생성할 때 진행 중이던 답변이 통째로 사라지고, 회수까지
수백 초가 비던 경로를 봉인한다. 사용자 체감으로는 "요청이 도중에 중단"으로 나타났다.

**왜**: `bin/deploy-web.sh` 는 워커를 `--force-recreate` 한다. 그런데 worker 소유자 id 가
`gethostname()`(=컨테이너 id) 기반이라 재생성 후 `reclaim_worker_jobs_on_boot` 의
`claimed_by = worker_id` 정확일치가 **항상 0행**이었다. 즉 "배포로 죽은 job" 은 자가회수가
구조적으로 불가능했고, 전역 stale sweeper 의 `AGENT_ASK_WORKER_STALE_SEC`(런타임 실측 450s)
창을 통째로 기다렸다. 60일 실측 8건/8대화, 생성→재시작 dead-air 142~1,649초, 3건 최종 error.
재실행은 사용자 메시지를 한 번 더 저장해 화면에 같은 말이 두 줄 보였다(9대화).

**어느 RC**: conv-audit `FR-ask-orphan-redeploy-dead-air` RC-1(회수 지연)·RC-2(중복 저장).

**재발 봉인 방식**: 재발경로는 `infra`(배포마다 재생성)이고 우리 통제 안이므로 **코드를
권위선**으로 둔다 — 죽기 전에 반납하고(A), 못 반납했으면 다음 인스턴스가 짧은 창으로
회수한다(B). 임계 추측이 아니라 소유권 인계 계약이다.

### 변경
- `shared/config.py` — `AGENT_ASK_WORKER_DRAIN_SEC`(기본 60, compose `stop_grace_period` 70s
  보다 작아야 반납이 SIGKILL 前에 끝난다) · `AGENT_ASK_WORKER_ROLE_STALE_SEC`(기본 60)
  신설, `__all__` 등록.
- `modules/ask_jobs.py` — `release_worker_jobs_on_shutdown()`(자기 소유 + `#slot` prefix
  매칭 requeue) · `reclaim_role_orphan_jobs()`(같은 role 의 **다른** 인스턴스 + 짧은 heartbeat
  창) · `_like_prefix()`(LIKE 와일드카드 이스케이프). 둘 다 기존 requeue 와 **동일한 상태
  전이**(pending + `lease_epoch++` fencing)를 쓴다 — 새 status 없음. `attempts` 미변경.
- `modules/ask.py` — `_worker_role()`/`_worker_role_prefix()`/`_worker_id()` 를 재생성 불변
  role 기반으로 분리(우선순위 `AGENT_WORKER_ROLE` > `AGENT_SESSION` > hostname —
  feature-0025 T0c 선례) · `_release_own_leases()` · SIGTERM 타이머
  `_arm_shutdown_lease_release()`(직렬 모드는 메인 스레드가 블록되므로 이것이 유일한 반납 창) ·
  drain deadline 을 하드코딩 65s → knob · 종료 경로/부팅/주기 유지보수에 회수 배선 ·
  재시도면 `dedup_user_message_since` 주입.
- `modules/runtime_backend.py` — `PgRuntimeBackend.user_message_persisted_since()` +
  core/display 2쿼리(`created_at >= since` 로 **job 수명 이후만** 판정).
- `agent_core.py` — `run_agent`/`_run_agent_core` 에 `dedup_user_message_since` 추가(기본
  None = 종전 동작) · `_user_message_already_persisted()` helper · 사용자 메시지 저장부가
  core/display 각각 판정 후 저장.
- `unit/feature-0002-agent-core/tests/test_ask_redeploy_handoff.py` — 신규 17건.

### 안전 경계
- 보안 경계 **불변** — RBAC·가드·allowlist·PII 경로 무변경. 큐 상태기계도 기존 전이만 쓴다.
- 오회수 방지: role 창은 자기 자신/자기 슬롯을 제외하고 `heartbeat_at` 이 `ROLE_STALE_SEC`
  이상 끊긴 행만 본다. heartbeat 는 시간 기반(10s 주기, step 무관)이라 이 창을 넘겼으면 그
  프로세스는 죽은 것이다. 전역 `STALE_SEC` 은 그대로 보수적으로 유지.
- 중복 억제는 **근거 기반 fail-open** — 조회 불가/PG 정본 아님이면 종전대로 저장한다(중복 1행이
  요청문 유실보다 안전).

Cross-ref: TASK-20260730T160000-ask-redeploy-handoff ·
REVIEW REV-20260730T160000-ask-redeploy-handoff ·
원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md` `FR-ask-orphan-redeploy-dead-air`.

## CHG-20260730T172000-dedup-param-cast — 중복 억제 판정 SQL 파라미터 캐스트 (봉인 C 활성화)

**무엇을**: `user_message_persisted_since` 의 두 판정 쿼리에 파라미터 타입 캐스트 추가.

**왜**: `%(mirror_sender)s IS NULL` 은 타입 컨텍스트가 없어 PostgreSQL 이 쿼리를 거부하고
(`could not determine data type of parameter $4`), `_read_runtime_pg` 가 그 예외를 흡수해
호출부가 fail-open 으로 저장한다 → **선행 CHG 의 봉인 C 가 배포본에서 통째로 무력**이었다.
배포 후 라이브 job 485 재시도에서 사용자 메시지가 다시 중복 저장되며 실증됐다(6301↔6322).

**어느 RC**: conv-audit `FR-ask-orphan-redeploy-dead-air` RC-2 (중복 저장) — 선행 수정의 결함 보정.

**재발 봉인 방식**: fail-open 자체는 유지가 옳다(중복 1행 < 요청문 유실). 대신 그 fail-open 이
**조용한 전면 무력화**로 번지지 않도록 캐스트를 회귀로 고정한다.

### 변경
- `modules/runtime_backend.py` — `_PG_USER_MESSAGE_EXISTS_DISPLAY` 의 `mirror_sender` 양쪽에
  `::text`, `_PG_USER_MESSAGE_EXISTS_CORE` 의 `sender_account_id` 에 `::bigint`. 캐스트가 왜
  필수인지 주석에 실측 근거 명시.
- `tests/test_ask_redeploy_handoff.py` — `test_dedup_sql_casts_bare_parameters` 신규.

### 검증 (실 PG 포함 — 선행 cycle 의 공백을 메움)
배포본 워커에서 RO 연결로 두 쿼리를 직접 실행: core hit/miss, display 그룹 hit/miss, display 1:1
NULL hit **5케이스 전부 계약대로**. 전체 회귀 `make test` EXIT=0 · ruff clean.

Cross-ref: TASK-20260730T172000-dedup-param-cast · REVIEW REV-20260730T172000-dedup-param-cast ·
선행 CHG-20260730T160000-ask-redeploy-handoff.
