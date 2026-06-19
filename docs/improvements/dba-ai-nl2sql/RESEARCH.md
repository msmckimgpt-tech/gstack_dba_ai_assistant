---
doc_type: DQA_RESEARCH
initiative: dba-ai-nl2sql
created_at: 2026-06-19
focus: NL→SQL 정확도·구조·성능·기능 (상용/사내 서비스 벤치마크)
status: draft
---

# 개선 리서치 — dba-ai-nl2sql

> 2026-06-19 세션 산출. 당근페이 BroQuery · AWS SageMaker · Wren/Vanna/Dataherald 벤치마크 + 현 코드 매핑.
> 본 문서는 `/_dqa:improve_research` 1단계 산출 형식의 worked example 이자 실제 시드.

## 0. 현재 상태 요약 (재발명 금지선)

**이미 보유 (추가 제외)**:
- 다층 시스템 프롬프트 (global/product/role/account 4-scope + 동적 주입) — `unit/feature-0002-agent-core/src/agent_core.py:658-836`
- 도구 8종 (execute_sql·describe_table·search_tables·get_sample_rows·explain_query·indexes·FK 등) — `.../modules/tools.py:400-570`
- SQL 4단 가드 (AST allowlist sqlglot + 스키마 allowlist + read-only + 부하추정 EXPLAIN/SHOWPLAN) — `.../modules/sql_guard.py`, `.../modules/tools.py:903-1030`
- 벡터+trigram 검색 (pgvector 1536D + pg_trgm fallback) — `.../modules/kb_backend.py:816-971`, `.../modules/kb_retrieval.py:435-497`
- 대화 컨텍스트 (origin_request/thread_goal 3-state + account recall + 스키마 인사이트, ds별 필터) — `.../agent_core.py:1437-2746`
- 데이터소스 레지스트리 (envelope 암호화 KEK/DEK) — `.../modules/datasources.py:132-237`
- 관리콘솔 manual KB 등록 + RBAC + 감사(WebAuditEvents)

**빈 곳 (후보 영역)**:
- few-shot 샘플쿼리(NL↔SQL) 저장소 / 피드백 환류 / 평가 harness / 하이브리드 검색·reranker / 용어·ENUM 사전 / Self-Reflection 명시 루프 / 무거운 쿼리 plan-승인 / 메타데이터 거버넌스 CRUD UI

## 1. Findings

### F-001 · 샘플쿼리(NL↔SQL) few-shot 자산화
- **dimension**: structural
- **source_kind**: internal-build (BroQuery)
- **source**: https://aws.amazon.com/ko/blogs/tech/daangnpay-text-to-sql-2/ — "샘플쿼리 유무에 따라 정확도 90% 이상 차이", 도메인 전문가가 NL-SQL 쌍 직접 등록
- **무엇을**: PG `sample_queries`(datasource_id, nl_question, sql, domain, weight, embedding) 신설 → 질문 임베딩 top-K 유사 샘플 검색 → 프롬프트 `## EXAMPLE QUERIES` 주입
- **현재 상태**: 없음 — 프롬프트 엔지니어링만 의존 (`kb_retrieval.py`)
- **raw_impact**: ★5
- **confidence**: high
- **note**: pgvector·`_embed_query_vector()`·KB 검색 경로 이미 존재 → 신규 비용 최소. ds-scoping 재사용 필요(insight 의 `ds_fact_like` 패턴). 샘플은 실행이 아닌 예시 주입 → 큐레이션 게이트 필요(F-002 연동)

### F-002 · 피드백 → KB 환류 (flywheel)
- **dimension**: structural
- **source_kind**: internal-build + commercial (BroQuery "지식베이스 영속성" + Dataherald 원클릭 등록)
- **source**: BroQuery Part 2(상동); https://www.bytebase.com/blog/top-text-to-sql-query-tools/ (Dataherald)
- **무엇을**: 답변 👍/👎 + "이 쿼리를 샘플로 등록" → 승인된 (질문,SQL)이 F-001 저장소로 승격, 👎는 negative example. 도메인 전문가 검수 큐
- **현재 상태**: 없음 — 대화는 저장되나 피드백 수집·환류 0 (`app.py` WebAuditEvents 는 감사용)
- **raw_impact**: ★5
- **confidence**: high
- **note**: F-001 없이는 무의미(동반 설계). PII 마스킹(kb_scope.py) 필요 — SQL literal 에 PII 가능. 신규 RBAC(`kb.sample.curate`)·audit 필요

### F-003 · NL→SQL 정확도 평가 harness
- **dimension**: performance (메타-레버)
- **source_kind**: internal-build (BroQuery)
- **source**: BroQuery Part 2 — RAGAS + LLM-as-a-Judge + Retrieval/Generation metrics
- **무엇을**: golden query set(질문·기대SQL·기대결과) + RAGAS(검색) + LLM-as-Judge(SQL/결과 정합) 회귀 harness
- **현재 상태**: 없음 — smoke test 만 (`unit/feature-0002-agent-core/tests/`)
- **raw_impact**: ★5
- **confidence**: high
- **note**: 이게 없으면 F-001/004/005/008 효과 증명 불가 → 측정 선행. golden set 용 fixture/reference datasource 필요(docker MySQL 활용 가능)

### F-004 · 하이브리드 검색 (벡터+키워드 score fusion)
- **dimension**: performance
- **source_kind**: internal-build (BroQuery)
- **source**: BroQuery Part 2 — OpenSearch hybrid + keyword boosting
- **무엇을**: 현 2-tier fallback(벡터 OR trigram) → `0.6×vector + 0.4×trigram`(또는 RRF) 단일 랭킹 융합
- **현재 상태**: 부분 — 벡터/trigram 둘 다 있으나 융합 안 함 (`kb_retrieval.py:435-474`)
- **raw_impact**: ★4
- **confidence**: high
- **note**: 한국어 키워드 정확매칭 보강. F-003 으로 효과 증명 전제

### F-005 · Reranker 2차 단계
- **dimension**: performance
- **source_kind**: internal-build (BroQuery), commercial (Wren 피드백 rerank)
- **source**: BroQuery Part 2 (reranker)
- **무엇을**: top-K(예 30) 후보 → cross-encoder 또는 경량 LLM rerank → top-5 압축
- **현재 상태**: 없음 — weight/updated_at 정렬만 (`kb_retrieval.py:288-297`)
- **raw_impact**: ★3
- **confidence**: med
- **note**: 지연·비용 증가 → selective 발동(벡터 confidence 낮을 때만). F-003/004 후

### F-006 · Self-Reflection 명시 자가수정 루프
- **dimension**: performance / functional
- **source_kind**: internal-build + commercial (BroQuery Self-Reflection + SageMaker "Fix with AI")
- **source**: BroQuery Part 1; https://aws.amazon.com/blogs/big-data/accelerate-sql-development-with-sagemaker-data-agent-in-query-editor/
- **무엇을**: SQL 문법/실행 오류 감지 시 "에러+원SQL → 같은 LLM 정정 요청"을 N회 한정 루프로 구조화
- **현재 상태**: 부분 — 에러를 tool_result 로 되먹이나 명시 bounded loop 없음, LLM 자율 의존 (`agent_core.py`)
- **raw_impact**: ★4
- **confidence**: high
- **note**: retry cap(N≤2-3) + 비용/timeout/circuit-breaker 예산 가드 필수(max_steps 연동)

### F-007 · 용어사전 + ENUM 코드사전 (semantic layer-lite)
- **dimension**: structural
- **source_kind**: internal-build + commercial (BroQuery 용어/ENUM + Wren semantic layer)
- **source**: BroQuery Part 2(ENUM 을 소스코드/위키에서 추출); https://www.getwren.ai/post/wren-ai-vs-vanna-the-enterprise-guide-to-choosing-a-text-to-sql-solution
- **무엇을**: `kb_glossary`(term, definition, datasource_id) + `enum_dictionary`(table, column, code, label) → 매칭 시 프롬프트 주입. Wren 풀 semantic 모델링은 과함 → subset 만
- **현재 상태**: 없음
- **raw_impact**: ★4
- **confidence**: high
- **note**: ENUM 은 describe_table+sample_rows 반자동 추출 가능. 유지보수 부담 → 반자동화로 완화

### F-008 · 메타데이터 거버넌스 포탈 (CRUD UI)
- **dimension**: structural / functional
- **source_kind**: internal-build (BroQuery)
- **source**: BroQuery Part 2 — dbt 자동추출 + 중앙저장소 + 웹 UI 편집 + 거버넌스 포탈
- **무엇을**: 관리콘솔에 테이블/컬럼 설명·샘플쿼리·용어·ENUM CRUD 탭. dbt 대신 describe_table/AST 로 스키마 부트스트랩
- **현재 상태**: 부분 — 첨부 등록만(`/api/kb/ingest`), insight 편집·삭제 UI 없음
- **raw_impact**: ★3
- **confidence**: high
- **note**: F-001/F-007 의 입력 UI(허브 의존). RBAC `kb.ingest.manual` 재사용

### F-009 · 무거운 쿼리 → 경량 대안 plan + 승인
- **dimension**: functional
- **source_kind**: commercial (SageMaker Data Agent step-plan + 승인)
- **source**: SageMaker Data Agent(상동) — 복잡요청 step-plan 후 승인
- **무엇을**: 부하추정 gate 초과 시 LLM 이 경량 대안(기간·WHERE 좁힘) 제시 → 1클릭 승인 → 실행
- **현재 상태**: 부분 — 부하 gate 는 있으나(TASK-0299/0304) 거부만, 사용자 노출 승인 라운드트립 없음(memory: gate 메시지 tool_result 채널=미노출)
- **raw_impact**: ★3
- **confidence**: high
- **note**: 기존 gate 인프라 확장. TASK-0304 "gate→LLM 재작성" 의 사용자 노출판

### F-010 · 데이터소스 비즈니스 컨텍스트 필드
- **dimension**: structural
- **source_kind**: commercial (Wren semantic)
- **source**: Wren AI(상동)
- **무엇을**: `WebDatasources` 에 Description/DomainTags 컬럼 → 멀티DS 라우팅·그라운딩 프롬프트 주입
- **현재 상태**: 없음 — 좌표·자격만 (`datasources.py:132-183`)
- **raw_impact**: ★2
- **confidence**: high
- **note**: 소규모 마이그레이션(MySQL agent_memory WebDatasources). 비밀 아님→plaintext

### F-011 · "Fix with AI" 표적 재수정 버튼
- **dimension**: functional
- **source_kind**: commercial (SageMaker "Fix with AI")
- **source**: SageMaker Data Agent(상동)
- **무엇을**: 실패 쿼리에 표적 정정 버튼(F-006 루프를 사용자 트리거로 노출)
- **현재 상태**: 부분 — 전체 재질문만(새 run)
- **raw_impact**: ★2
- **confidence**: med
- **note**: F-006 위에 얹음

### F-012 · 명시 planner/DAG 단계 (LangGraph 식)
- **dimension**: structural
- **source_kind**: internal-build (BroQuery LangGraph) + commercial (SageMaker step-plan)
- **source**: BroQuery Part 1 (LangGraph 노드/엣지)
- **무엇을**: 복잡 질문에 명시적 multi-step plan
- **현재 상태**: 없음 — 순수 ReAct (`agent_core.py:2890-3166`)
- **raw_impact**: ★2
- **confidence**: med
- **note**: 전면 도입은 ask-worker+ReAct 대비 복잡도 과다 우려 → listup 에서 기각/축소 검토 권고(F-009 로 좁게 흡수 가능)

### F-013 · 자동 리포트 / 스케줄 쿼리 / 데이터 품질 알림
- **dimension**: functional
- **source_kind**: internal-build (BroQuery 향후계획)
- **source**: BroQuery Part 2 (향후계획)
- **무엇을**: 저장 쿼리 스케줄링 + 결과 알림 + 이상감지
- **현재 상태**: 없음
- **raw_impact**: ★3
- **confidence**: med
- **note**: 규모 큼(신규 스케줄러 subsystem). insight-worker 패턴 재사용. 장기

### F-014 · 결과 시각화(차트) 강화
- **dimension**: functional
- **source_kind**: internal-build (BroQuery)
- **source**: BroQuery Part 1 (표/차트 1분 내)
- **무엇을**: 결과 자동 차트 추천/렌더
- **현재 상태**: 부분 — 대형표 CSV 링크
- **raw_impact**: ★2
- **confidence**: med
- **note**: frontend Minor. 후순위

## 2. 출처 목록 (Sources)
- [당근페이 Text-to-SQL Part 1 — 기획/아키텍처](https://aws.amazon.com/ko/blogs/tech/daangnpay-text-to-sql-1)
- [당근페이 Text-to-SQL Part 2 — 메타데이터 수집/관리](https://aws.amazon.com/ko/blogs/tech/daangnpay-text-to-sql-2/)
- [SageMaker Data Agent in Query Editor (AWS Big Data Blog)](https://aws.amazon.com/blogs/big-data/accelerate-sql-development-with-sagemaker-data-agent-in-query-editor/)
- [Generative SQL — SageMaker Unified Studio (AWS Docs)](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/generative-sql.html)
- [Wren AI vs Vanna — Enterprise Text-to-SQL Guide](https://www.getwren.ai/post/wren-ai-vs-vanna-the-enterprise-guide-to-choosing-a-text-to-sql-solution)
- [Top Text-to-SQL Query Tools — Bytebase](https://www.bytebase.com/blog/top-text-to-sql-query-tools/)
- [Best SQL AI Tools in 2025 — text2sql.ai](https://www.text2sql.ai/best-text-to-sql-tools-2025)
