---
doc_type: DQA_ROADMAP
initiative: dba-ai-nl2sql
created_at: 2026-06-19
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — dba-ai-nl2sql (NL→SQL 정확도·구조·성능·기능)

> 경로는 모두 **repo-상대**(`policy_root` = repo 체크아웃 / worktree root 기준). `repo/` prefix 는 wrapper checkout 전용이라 본 문서에선 쓰지 않는다(0-맥락 세션이 worktree 안에서 그대로 열 수 있게).

## 0. 맥락 (context-free 진입)

본 로드맵은 사내 **DBA AI Assistant**(자연어 → LLM tool-call loop → MySQL·MSSQL read-only 분석)의 NL→SQL 품질·UX 개선 백로그다. 당근페이 BroQuery / AWS SageMaker / Wren·Vanna·Dataherald 벤치마크(→ `./RESEARCH.md`)에서, **우리에 이미 없는 빈 곳만** 정합성 review 후 채택했다.

- **대상 제품**: 온프레미스(사내 폐쇄망) NL→SQL DBA Assistant. Bedrock(Claude) + Postgres/pgvector KB + FastAPI + ask-worker 큐 + 멀티 데이터소스 registry.
- **정본 진입**: `AGENTS.md` · `docs/PROJECT.md` · `docs/ARCHITECTURE.md` · `docs/SECURITY.md`. 코어 코드: `unit/feature-0002-agent-core/src/`. 웹/관리콘솔: `unit/feature-0003-agent-web-ui/src/`.
- **측정 기반**: **ITEM-01(평가 harness)이 선행 측정 수단** — 성능 항목은 이걸로 효과를 증명한다(측정 없이 done 금지).
- **feature_id 매핑**: 각 항목은 구현 대상 `feature_id` 를 갖는다. cycle 은 그 값을 cycle-init `--feature` / verify-completion `<feature-id>` 양쪽에 쓴다. 대부분 기존 `feature-0002-agent-core`(코어/KB) 또는 `feature-0003-agent-web-ui`(웹/관리콘솔) 확장이다.
- **핵심 통찰**: ITEM-01+02+03 은 한 덩어리(flywheel — 측정 + 샘플 자산 + 피드백 환류). BroQuery 자체측정상 "샘플쿼리 유무 = 정확도 ±90%"가 최대 레버.

## 1. 종속성 그래프 (requires = 실선, enables = 점선)

```
ITEM-01 (eval harness, P0)
   ├┄enables┄▶ ITEM-02, ITEM-05, ITEM-06, ITEM-12 (효과 측정 게이트)
ITEM-02 (sample store) ──requires▶ (none)
   └──enables──▶ ITEM-03, ITEM-11
ITEM-03 (feedback flywheel) ──requires▶ ITEM-02
ITEM-04 (DS context field) ──requires▶ (none)        # 조기 착수 가능
ITEM-05 (hybrid search) ──requires▶ ITEM-01
ITEM-06 (reranker) ──requires▶ ITEM-01, ITEM-05
ITEM-07 (self-reflection loop) ──requires▶ (none)    # 조기 착수 가능
ITEM-08 (fix-with-AI) ──requires▶ ITEM-07
ITEM-09 (heavy-query plan+approve) ──requires▶ (none) # 조기 착수 가능
ITEM-10 (glossary/ENUM) ──requires▶ (none)
ITEM-11 (governance portal) ──requires▶ ITEM-02, ITEM-10
ITEM-12 (retrieval tuning) ──requires▶ ITEM-01, ITEM-05
```
DAG 검증: 순환 없음. 측정(ITEM-01)이 모든 성능항목의 선행.

## 2. Phase 시퀀스

| Phase | 포함 ITEM | 병렬? | 진입 조건 | 왜 이 순서 |
|---|---|---|---|---|
| **P0 측정기반** | ITEM-01 | — | 없음 | 측정 없이는 나머지 효과 증명 불가 |
| **P1 정확도 flywheel** | ITEM-02 → ITEM-03; ITEM-04 | ITEM-02/04 병렬, ITEM-03 은 02 후 | P0 권장 선행 | 최대 레버(±90%) + 사용이 정확도를 키우는 순환 |
| **P2 검색 정합** | ITEM-05 → ITEM-06; ITEM-12 | ITEM-05 후 06/12 | ITEM-01 done | 측정 위에서 retrieval 개선 |
| **P3 견고성·UX** | ITEM-07 → ITEM-08; ITEM-09 | ITEM-07 후 08; 09 병렬 | 없음(조기 가능) | 실패율↓·UX↑, KB 독립 |
| **P4 메타 자산** | ITEM-10 → ITEM-11 | 순차 | ITEM-02 done | 지식 자산 성숙(입력 UI) |

> Phase 는 **권장 순서**(improve_cycle 선택의 1순위 정렬키)이지 강제 배리어가 아니다. deps 가 비어 즉시 ready 인 ITEM-04/07/09 는 자원이 남으면 조기 병렬 착수 가능. improve_cycle 의 ready 선택 = (status=pending ∧ depends_on 전부 done) 중 (Phase asc → risk_grade asc → id asc).

## 3. 항목 (각 1 cycle)

### ITEM-01 · NL→SQL 평가 harness (RAGAS + LLM-as-Judge)
- **status**: done
- **note**: harness 코드 완성+단위검증(스모크 14, fixture 멱등, ground-truth 검산, end-to-end 리포트/회귀 산출) + 적대리뷰 BLOCKER 흡수(생성SQL root 재실행 제거→agent 샌드박스 CSV 비교). **measured generation accuracy 는 스택 Bedrock 인증 다운(2026-06-19 IAM 제거)으로 보류 — 자격증명 복구 후 `make eval` 로 AC-1602/1603 라이브 수치 산출.** CHG/REV-20260619T172843-eval-harness.
- **feature_id**: feature-0002-agent-core
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: []
- **enables**: [ITEM-02, ITEM-05, ITEM-06, ITEM-12]
- **why**: F-003. 현재 smoke test 만 → NL→SQL 품질 정량지표 0. 이게 없으면 후속 성능항목 효과를 증명 못 함(메타-레버).
- **fit_verdict**: adopt. (정합: 비파괴 offline harness. 제약 충돌 없음. fixture DB 로 폐쇄망 유지.)
- **what**: (a) golden set 포맷 — `(datasource, nl_question, expected_sql, expected_result_signature)` JSON/YAML. (b) reference fixture datasource — docker MySQL 에 결정적 스키마+시드(prod 무관). (c) runner — golden 질문을 agent 파이프라인에 흘려 생성SQL/결과 수집. (d) metrics — RAGAS(retrieval precision/recall) + LLM-as-Judge(SQL 동치·결과 일치). (e) 회귀 리포트(`../../artifacts/` timestamp 격리).
- **entry_points**: 신규 `unit/feature-0002-agent-core/tests/eval/`(harness) + 기존 agent 진입(`unit/feature-0002-agent-core/src/agent_core.py` run 경로) 재사용. fixture 는 `docker-compose` 보조 서비스 또는 기존 MySQL 의 별 schema.
- **acceptance**: golden set ≥20 질문에 대해 harness 가 retrieval/generation metric 수치를 산출하고 회귀 리포트를 남긴다. 같은 입력 2회 실행 시 결정적(temperature 0 경로). `make` 타깃 1개로 호출 가능.
- **guards**: golden 질문은 fixture DB 대상만(prod 데이터 평가 금지 — 폐쇄망/PII). LLM-as-Judge 비용 cap.
- **effort**: 中
- **notes**: 이후 모든 성능 cycle 의 acceptance 가 이 harness 수치를 인용. 배포 불필요(개발 도구).

### ITEM-02 · 샘플쿼리(NL↔SQL) few-shot 저장소
- **status**: done
- **note**: 2026-06-23 드레인(PR-A). 저장소(sample_queries 테이블+마이그0014, 임베딩 vector(1536), approved∧active∧weight cosine 검색, ## EXAMPLE QUERIES 예시-only 주입, flywheel-ready 필드+신선도 validate_sample_sql) 완료. 단위 12 + 라이브 pg16 dry-run + register(::vector)→search sim=1.0, 적대 backend+security 리뷰 BLOCKER(embedding ::vector) 흡수 SHIP. **AC-d A/B 측정은 titan-embed(임베딩) 다운으로 보류 — 복구 후 harness off/on.** 등록 UI 는 ITEM-03 PR-B/ITEM-11. CHG/REV-20260623T145444-sample-flywheel-core.
- **feature_id**: feature-0002-agent-core
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: []
- **enables**: [ITEM-03, ITEM-11]
- **why**: F-001. BroQuery 최대 정확도 레버(±90%). 현재 전무.
- **fit_verdict**: adopt-with-guard. **guard**: ① 샘플은 datasource-scoped(교차오염 차단, insight `ds_fact_like` 패턴 재사용) ② 샘플은 프롬프트 예시로만 주입(직접 실행 아님) ③ 등록 경로는 큐레이션 게이트 통과분만(ITEM-03 검수).
- **what**: PG 신규 테이블 `sample_queries(id, datasource_id, nl_question, sql, domain, weight, embedding vector(1536), created_by, approved, created_at)`. 등록 시 nl_question 임베딩. 검색: 사용자 질문 임베딩으로 top-K(예 3-5) 유사 샘플 → 시스템 프롬프트 `## EXAMPLE QUERIES` 주입. approved=true 만 검색 대상.
- **entry_points**: 스키마 `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql`. 검색 `unit/feature-0002-agent-core/src/modules/kb_retrieval.py`(`_embed_query_vector` 재사용). 주입 `unit/feature-0002-agent-core/src/agent_core.py:1126-1186`(`_build_knowledge_context` 에 EXAMPLE 섹션). backend `unit/feature-0002-agent-core/src/modules/kb_backend.py`(PgKbBackend 검색 메서드).
- **acceptance**: 샘플 N개 등록 후 동일 도메인 질문에 top-K 샘플이 프롬프트 주입됨을 단위검증. **ITEM-01 harness 로 샘플 유무 A/B → generation metric 유의 상승**(수치 기록). ds 격리(타 datasource 샘플 비주입) 검증.
- **guards**: (상동) ds-scope + approved-only + 주입-only.
- **effort**: 中
- **notes**: pgvector·임베딩·KB 검색 경로 재사용 → 신규 비용 낮음. 배포 = ask-worker(+ 등록 UI 시 web, ITEM-11 과 묶음 가능).

### ITEM-03 · 피드백 → KB 환류 flywheel
- **status**: done
- **note**: 2026-06-23 드레인. PR-A(코어 record/promote/reject, CHG-20260623T145444) + **PR-B(web: 신규 RBAC `kb.sample.curate` + 피드백 endpoint(👍/👎/등록) + 검수 큐 admin UI + audit, CHG-20260623T090440)** 완료. titan-embed(bge-m3 1024) 복구로 승급 샘플 임베딩·주입 가능. 단위 27(curation 15+flywheel 12) + 적대 security 리뷰 REV-20260623-0334 **SHIP-WITH-FIXES**(MAJOR-1 rate-limit·MAJOR-2 promote FOR UPDATE·MINOR-1 nl_question PII 흡수). 잔여: PB-0008 Windows-browser UI 실렌더(WARN-only).
- **feature_id**: feature-0003-agent-web-ui   <!-- primary(UI+endpoint). 코어 환류는 feature-0002 — MODIFY.md cross-ref -->
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-02]
- **enables**: []
- **why**: F-002. 사용이 정확도를 키우는 순환. 현재 피드백 수집·환류 0.
- **fit_verdict**: adopt-with-guard. **guard**: ① PII 마스킹(SQL literal) — `kb_scope.py` 마스킹 재사용 ② 신규 RBAC `kb.sample.curate`(도메인 전문가만 승인) ③ 모든 피드백/승급 audit(WebAuditEvents) ④ 승인 큐 경유(자동 학습 금지 — poisoning 방지).
- **what**: 답변에 👍/👎 + "샘플로 등록" 액션 → `sample_feedback` 적재 → 검수 큐 → 승인 시 ITEM-02 `sample_queries`(approved=true)로 승급, 👎는 negative example 태깅. 검수 큐는 관리콘솔.
- **entry_points**: 피드백 endpoint `unit/feature-0003-agent-web-ui/src/app.py`(WebAuditEvents 인접). UI `unit/feature-0003-agent-web-ui/src/static/app.js`(diff 블록 `enhanceDiffBlocks` 인접). 검수 큐 `.../static/admin.js` + admin endpoint. 승급 → ITEM-02 저장소.
- **acceptance**: 답변 피드백이 적재되고, 승인 1건이 `sample_queries` approved 로 승급되어 다음 동일 질문 프롬프트에 주입됨(end-to-end). 비승인 미주입. 모든 단계 audit. RBAC 미보유 승인 403.
- **guards**: (상동) PII·RBAC·audit·승인큐.
- **effort**: 中
- **notes**: 배포 = web+ask-worker. 코어 환류 코드(feature-0002)는 primary unit MODIFY 에 cross-ref.

### ITEM-04 · 데이터소스 비즈니스 컨텍스트 필드
- **status**: done
- **note**: 2026-06-23 드레인. read-side+schema 완료(WebDatasources Description/DomainTags → _row_to_ds → describe() → 멀티DS 그라운딩 주입). 단위 43 통과, 적대 backend 리뷰 SHIP. write-path(admin 편집 UI) 는 ITEM-11(거버넌스 포탈) follow-up — 현재 nullable·SQL 설정 가능. 라이브 그라운딩 e2e 는 bedrock-auth 복구 후. CHG/REV-20260623T101031-ds-business-context.
- **feature_id**: feature-0002-agent-core   <!-- registry primary. admin 편집 UI 는 feature-0003 — cross-ref -->
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: F-010. 멀티DS 라우팅·그라운딩에 "이 DS 가 무슨 사업데이터인가" 부재.
- **fit_verdict**: adopt.
- **what**: `WebDatasources` 에 `Description`, `DomainTags`(plaintext) 컬럼 추가 → registry 병합(`_row_to_ds`) 포함 → 멀티DS 그라운딩 프롬프트 + DS picker 주입.
- **entry_points**: 마이그레이션(MySQL agent_memory WebDatasources). `unit/feature-0002-agent-core/src/modules/datasources.py:132-183`(`_row_to_ds`). 멀티DS 그라운딩 `unit/feature-0002-agent-core/src/agent_core.py`. 관리콘솔 DS 편집 `unit/feature-0003-agent-web-ui/src/static/admin.js`.
- **acceptance**: DS 에 설명 입력 후 멀티DS 질문에서 그 설명이 그라운딩 프롬프트에 노출. 단일DS 제품 무영향.
- **guards**: 멱등 마이그레이션.
- **effort**: 小
- **notes**: deps 없어 조기 착수 가능(Minor → 무인 cycle 자율 진행 가능). 배포 = web+ask-worker.

### ITEM-05 · 하이브리드 검색 (벡터+키워드 score fusion)
- **status**: done
- **note**: 2026-06-24 마감(PR#TBD). fusion 구현 + 적대 backend 리뷰(SHIP-WITH-FIXES: MAJOR 병합키·MINOR-1 trigram floor·MINOR-2 span-0 전부 흡수) + KB retrieval eval set(evalkb/evalkb_adv). **acceptance("precision/recall 유의 상승")는 충실 측정 결과 반증(REFUTED)** — 적대 corpus(24 docs/12 질문 fusion-favorable 설계) + 파라미터 sweep 에서도 Δ 전부 +0.0000(MRR 1.0). 근본: bge-m3 가 subword/char 인지라 질문 rare token 이 정답 cosine 도 함께 끌어올려 fusion 이 바꿀 top rank 없음(fusion-favorable·vector-miss 양립 불가). 사용자 결정: **gated-OFF dormant** — `AGENT_KB_HYBRID_ENABLED` 기본 OFF(운영 거동 불변), 코드·eval 자산은 비회귀 안전 + 임베더-장애 폴백 보험으로 보존. 실가치 재측정은 라이브 운영 질의 로그 필요(ITEM-12 튜닝 근거 현 corpus 론 없음).
- **feature_id**: feature-0002-agent-core
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: [ITEM-01]
- **enables**: [ITEM-06, ITEM-12]
- **why**: F-004. 현 2-tier fallback(벡터 OR trigram) → 융합으로 한국어 키워드 정확매칭 보강.
- **fit_verdict**: adopt.
- **what**: `kb_retrieval` 검색을 `score = α·vector_sim + β·trigram_sim`(또는 RRF) 단일 랭킹으로. α/β 기본값 + env override. 벡터 미임베딩 row 는 trigram-only 폴백 유지.
- **entry_points**: `unit/feature-0002-agent-core/src/modules/kb_retrieval.py:435-497`. backend 점수 노출 `unit/feature-0002-agent-core/src/modules/kb_backend.py:816-971`.
- **acceptance**: **ITEM-01 harness 로 fusion vs 2-tier → retrieval precision/recall 유의 상승**(수치). 회귀 없음.
- **guards**: 벡터 부재 시 안전 폴백 보존.
- **effort**: 中
- **notes**: 배포 = ask-worker(+ insight 공유 이미지).

### ITEM-06 · Reranker 2차 단계 (selective)
- **status**: blocked (deferred — measurement substrate gap)
- **note**: 2026-06-24 사용자 결정(드레인) — defer(ITEM-12 와 동일 사유). acceptance("rerank on/off → 정밀도↑ vs 지연 trade 측정")가 합성 harness 로 충족 불가: bge-m3 가 합성 KB 에서 이미 MRR=1.0 → 재정렬할 1차 오류 없음 → 정밀도 lift 측정 불가. guard "측정으로 on/off 정책 결정" 미충족 + cross-encoder/LLM rerank 지연·비용. **재개 트리거**: 라이브 운영 질의 로그(임베더 헛짚는 케이스) 확보 후 selective reranker(gated, 지연 cap) 착수. select_next_ready 제외(blocked).
- **feature_id**: feature-0002-agent-core
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: [ITEM-01, ITEM-05]
- **enables**: []
- **why**: F-005. top-K 후보 재정렬로 정밀도↑.
- **fit_verdict**: adopt-with-guard. **guard**: selective 발동(벡터/fusion confidence 낮을 때만) + 지연·비용 cap(단일 직렬 ask-worker 예산·circuit breaker 존중).
- **what**: fusion top-K(예 30) → cross-encoder(경량 로컬) 또는 경량 LLM rerank → top-5. 발동 조건 env gate.
- **entry_points**: `unit/feature-0002-agent-core/src/modules/kb_retrieval.py`(랭킹 후단). reranker 모듈 신규.
- **acceptance**: **ITEM-01 harness 로 rerank on/off → 정밀도 상승 vs 지연 증가 trade 측정**. selective gate 저신뢰에서만 발동 검증. p95 지연 회귀 한도 내.
- **guards**: (상동) selective + latency/cost cap.
- **effort**: 中
- **notes**: 지연 민감 — 측정으로 on/off 정책 결정.

### ITEM-07 · Self-Reflection 명시 자가수정 루프
- **status**: done
- **note**: 2026-06-23 드레인(chat). execute_sql 수정가능 실패에 cap(2) 걸린 구조화 자가수정 넛지(분류+원SQL+표적힌트, 보안가드 제외, env gate). 단위 7 + prompt-injection 회귀 10, 적대 backend+security 리뷰 MAJOR(M1 실제 'SQL 실행 오류:' prefix 미매칭) 흡수 SHIP. **AC-b 정량 회복률 보류** — describe-first agent 가 단순 fixture 에서 1차 실패 거의 없어 측정 불가(에러유발 production traffic/error-injection harness 모드 필요, follow-up). 메커니즘+실제 에러경로 매칭 검증 완료. CHG/REV-20260623T151643-self-reflection.
- **feature_id**: feature-0002-agent-core
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: []
- **enables**: [ITEM-08]
- **why**: F-006. 현재 에러 되먹임은 LLM 자율 의존 → 명시 bounded loop 로 성공률↑.
- **fit_verdict**: adopt-with-guard. **guard**: retry cap(N≤2-3) + 비용/timeout/circuit-breaker 예산 + max_steps 연동(무한루프·폭주 차단).
- **what**: SQL 문법/실행 오류 감지 시 "(에러+원SQL+스키마힌트) → 같은 LLM 정정 요청"을 N회 한정 루프로 구조화. 성공 또는 cap 도달 시 종료.
- **entry_points**: `unit/feature-0002-agent-core/src/agent_core.py:2890-3166`(tool 실패 경로) + `unit/feature-0002-agent-core/src/modules/tools.py`(execute_sql 에러 분류).
- **acceptance**: **ITEM-01 harness 로 on/off → 1차 실패 후 성공 회복률 상승**(수치). cap 초과 시 안전 종료(폭주 없음). 비용 증가 cap 내.
- **guards**: (상동) retry cap·예산.
- **effort**: 中
- **notes**: deps 없어 조기 착수 가능. 배포 = ask-worker.

### ITEM-08 · "Fix with AI" 표적 재수정 버튼
- **status**: done
- **note**: 2026-06-24 드레인(chat, PR#TBD). 실패 execute_sql 결과 카드의 "AI 로 고치기" 버튼 → 신규 `POST /api/conversations/{cid}/fix-with-ai`(가드 = sample-feedback 동형: access 404·rate-limit 429·`conversation.ask` 403·audit)가 **서버 구성 정정 지시문**(client SQL/error 는 nonce-봉인 데이터 블록)을 **동일 cid 로 기존 `/api/ask` 에 1회 재dispatch** → ITEM-07 self-reflection(agent_core 무변경)이 표적 정정. 원본 NL 재질문 회피. 적대 backend+security 리뷰 SHIP-WITH-FIXES — **MAJOR M1(인젝션 방어가 백틱만 막고 개행/라벨 탈출 허용) → nonce-봉인 흡수**, MINOR(rate-bucket·검증순서)는 house-consistent 수용, `_make_internal_ask_request` 안전 확인. test 10/10. **UI 라이브 렌더 검증(PB-0008)은 배포 후**(web). CHG/REV-20260624T105228.
- **feature_id**: feature-0003-agent-web-ui
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-07]
- **enables**: []
- **why**: F-011. 실패 쿼리에 전체 재질문 대신 표적 정정 1클릭(ITEM-07 루프의 사용자 트리거).
- **fit_verdict**: adopt.
- **what**: 실패 결과 카드에 "AI 로 고치기" 버튼 → ITEM-07 self-reflection 을 사용자 트리거로 1회 발동.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/static/app.js`(결과/에러 렌더) + ask endpoint.
- **acceptance**: 실패 쿼리에서 버튼 클릭 시 표적 정정 1회 발동·결과 갱신(새 run 전체 재질문 아님).
- **guards**: ITEM-07 cap 상속.
- **effort**: 小
- **notes**: Minor → 무인 cycle 자율. 배포 = web.

### ITEM-09 · 무거운 쿼리 → 경량 대안 plan + 승인
- **status**: rejected (subsumed)
- **note**: 2026-06-23 드레인. **shipped TASK-0299/0304 와 충돌·subsumed** → reject. 무거운 쿼리 처리는 이미 main 에 구현됨(agent_core.py:120-128: 부하 gate 감지 → LLM 이 tool 루프에서 자동으로 더 가벼운 동등 쿼리로 재작성, "user only sees final efficient answer, never a blocked message", confirm_heavy 최후수단). ITEM-09 의 "경량 대안 사용자 노출 + 1클릭 승인"은 TASK-0304 의 사용자-승인된 **silent-rewrite 결정("최종 사용자엔 차단 미노출")을 역전**하는 것이라, 설계 충돌. 사용자 결정(2026-06-23): subsumed 로 종료. §4 기록. 승인-UX 재도입을 원하면 별도 plan-ceo/eng-review 로 TASK-0304 결정 재검토.
- **feature_id**: feature-0002-agent-core   <!-- gate primary. 승인 UI 는 feature-0003 — cross-ref -->
- **dimension**: functional
- **risk_grade**: Major
- **depends_on**: []
- **enables**: []
- **why**: F-009. 현 부하 gate 는 거부만(사용자 미노출) → 경량 대안 제시+승인으로 전환.
- **fit_verdict**: adopt. (기존 gate 인프라 확장 — TASK-0299/0304.)
- **what**: 부하추정 gate 초과 시 LLM 이 경량 대안 쿼리(기간/WHERE 좁힘) 생성 → 사용자 노출 + 1클릭 승인 → 실행.
- **entry_points**: gate `unit/feature-0002-agent-core/src/modules/tools.py:903-1030`(부하추정·gate) + `unit/feature-0002-agent-core/src/agent_core.py`(승인 라운드트립 상태) + `unit/feature-0003-agent-web-ui/src/static/app.js`(승인 UI).
- **acceptance**: gate 초과 질문에서 경량 대안 노출, 승인 시 대안 실행, 미승인 시 미실행. 기존 gate 차단 안전성(read-only·estimation fail-closed) 유지.
- **guards**: 승인 전 원 무거운 쿼리 미실행. gate fail-closed 보존.
- **effort**: 中
- **notes**: deps 없어 조기 착수 가능. 배포 = web+ask-worker.

### ITEM-10 · 용어사전 + ENUM 코드사전 (semantic-lite)
- **status**: done
- **note**: 2026-06-23 드레인(PLAN-APPROVED). 구조부(kb_glossary/enum_dictionary PG 테이블+마이그 0013 + ds-scoped upsert/read + `_build_knowledge_context` datamark 주입) 완료. 단위 9 + KB회귀 26 + 라이브 pg16 DDL dry-run, 적대 backend 리뷰 BLOCKER(ds-scope 격리) 흡수. write-path(admin UI)·반자동 ENUM 추출·ENUM 정확도 측정(ITEM-01 harness)은 follow-up(측정은 bedrock-auth 복구 후). CHG/REV-20260623T105344-kb-glossary-enum.
- **feature_id**: feature-0002-agent-core
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: []
- **enables**: [ITEM-11]
- **why**: F-007. 도메인 용어·상태코드 매핑 부재.
- **fit_verdict**: adopt. (Wren 풀 semantic 은 기각 — subset 만.)
- **what**: PG `kb_glossary(term, definition, datasource_id)` + `enum_dictionary(datasource_id, schema, table, column, code, label)`. 질문/스키마 매칭 시 프롬프트 주입. ENUM 은 describe_table+sample_rows 반자동 추출 + 사람 보정.
- **entry_points**: 스키마 `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql`. 주입 `unit/feature-0002-agent-core/src/agent_core.py`(`_build_knowledge_context`). 추출 헬퍼 `unit/feature-0002-agent-core/src/modules/`(describe/sample 재사용).
- **acceptance**: 용어/ENUM 등록 후 관련 질문에서 프롬프트 주입 확인. **ITEM-01 harness 로 ENUM 관련 질문 정확도 상승**(수치). ds-scope 격리.
- **guards**: ds-scope. 유지보수 부담 → 반자동 추출.
- **effort**: 中
- **notes**: 배포 = ask-worker(+ 등록 UI 는 ITEM-11 과 묶음).

### ITEM-11 · 메타데이터 거버넌스 포탈 (CRUD UI)
- **status**: done (MVP-1 + Phase 2)
- **note**: 2026-06-24 드레인(chat, PLAN-APPROVED). **MVP-1(용어/ENUM CRUD) 마감** — admin "메타데이터" 탭(용어·ENUM 2 서브뷰: scope 드롭다운+목록+생성/수정/삭제) + backend 8 엔드포인트(`/api/admin/metadata/{glossary,enums}`) + 신규 RBAC `kb.ingest.manual`(admin seed) + audit + cross-DB conn 분리. 기존 PG 테이블 재사용(마이그 없음). 적대 backend+security 리뷰 SHIP. test 13/13. CHG/REV-20260624T130000. **Phase 2 마감(2026-06-24, PLAN-APPROVED 2a+2b)** — 테이블/컬럼 설명 CRUD + KB datamark 주입 + describe_table overlay(native 빈 comment) + RO 스키마 부트스트랩(미영속) + 샘플 admin 검수(하이브리드 C). 신규 테이블 `table_descriptions`/`column_descriptions`(alembic 0017, 단일 head·멱등). RBAC `kb.ingest.manual`/`kb.sample.curate`. 적대 패널 2회 SHIP(B1 부트스트랩 SQLi + M2 alembic 위치 흡수 → BLOCKER/MAJOR 0). test 27/27 + 회귀 25(MVP-1 13 + sample_flywheel 12). CHG/REV-20260624T133000-item11-phase2. UI 라이브 검증(PB-0008)은 배포 후(WARN-only).
- **feature_id**: feature-0003-agent-web-ui
- **dimension**: structural / functional
- **risk_grade**: Major
- **depends_on**: [ITEM-02, ITEM-10]
- **enables**: []
- **why**: F-008. insight/샘플/용어/ENUM 편집 UI 부재(현재 등록만).
- **fit_verdict**: adopt. (dbt 대신 describe_table/AST 부트스트랩으로 적응.)
- **what**: 관리콘솔에 메타데이터 탭 — 테이블/컬럼 설명·샘플쿼리(ITEM-02)·용어/ENUM(ITEM-10) CRUD. describe_table/AST 로 스키마 골격 자동 부트스트랩, 사람이 설명 보강.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/static/admin.js` + admin endpoints `unit/feature-0003-agent-web-ui/src/app.py`. RBAC `kb.ingest.manual` 재사용(+ITEM-03 의 curate).
- **acceptance**: 콘솔에서 샘플/용어/ENUM/테이블설명 CRUD 동작 + KB 반영. RBAC 게이트(미보유 403). 부트스트랩이 describe_table 로 스키마 골격 생성.
- **guards**: RBAC. 편집 audit.
- **effort**: 大
- **notes**: ITEM-02/10 의 입력 허브. 배포 = web.

### ITEM-12 · Retrieval 파라미터 튜닝 (측정 기반)
- **status**: blocked (deferred — measurement substrate gap)
- **note**: 2026-06-24 사용자 결정(드레인) — defer. 이 항목의 guard "측정 선행 · 추측 튜닝 금지"가 현 합성 harness 로는 **충족 불가**: ITEM-05 마감 측정에서 ① 하이브리드 α/β sweep 7조합 전부 flat(fusion no-lift) ② ivfflat/top-K 는 합성 KB(12~24 docs)에서 sub-scale(ivfflat 사실상 exact)·saturated(recall 1.0)라 **측정 신호 0**. 즉 ITEM-05 와 동일한 substrate gap. 추측 튜닝은 guard 위반이므로 강행 안 함. **재개 트리거**: 라이브 운영 질의 로그 / 실규모 corpus 확보(임베더가 실제로 헛짚는 케이스) → 그 위에서 grid 탐색. select_next_ready 에서 제외(blocked).
- **feature_id**: feature-0002-agent-core
- **dimension**: performance
- **risk_grade**: Minor
- **depends_on**: [ITEM-01, ITEM-05]
- **enables**: []
- **why**: F-005 note(BroQuery ANN/boosting 튜닝). 추측 금지 — 측정 위에서만.
- **fit_verdict**: adopt.
- **what**: ivfflat/HNSW 파라미터·하이브리드 α/β·top-K 를 ITEM-01 harness 측정으로 grid 탐색·확정.
- **entry_points**: `unit/feature-0002-agent-core/src/modules/kb_retrieval.py`·`kb_backend.py` 파라미터 + PG 인덱스 설정.
- **acceptance**: harness 수치 기준 최적 파라미터 선정·기록. 회귀 없음.
- **guards**: 측정 선행(추측 튜닝 금지).
- **effort**: 小
- **notes**: ITEM-01·05 후. Minor → 무인 cycle 자율. 배포 = ask-worker.

## 4. 보류·기각 (재논의 방지 기록)

| finding | verdict | 사유 |
|---|---|---|
| F-012 (명시 planner/DAG, LangGraph) | **reject(전면)** | ask-worker 큐+ReAct 로 충분. 전면 그래프 재작성은 복잡도 과다·blast radius 큼. 필요한 "복잡 질문 분해"는 ITEM-09 로 좁게 흡수. 재검토 트리거: ITEM-01 측정에서 다단계 질문 실패율이 구조적으로 높을 때. |
| F-013 (자동 리포트/스케줄/품질알림) | **defer** | 신규 스케줄러 subsystem(규모 大). 현 flywheel·정확도 우선. 재검토 트리거: P1~P3 안정화 후. insight-worker 패턴 재사용 가능. |
| F-014 (결과 차트 시각화) | **defer** | frontend Minor·가치 중간. 정확도 항목 후순위. 재검토 트리거: 사용자 요청 누적 시. |
| **ITEM-09** (무거운쿼리 경량대안+승인) | **reject(subsumed)** | shipped TASK-0299/0304 가 무거운쿼리를 LLM tool-루프 silent rewrite 로 이미 처리(agent_core.py:120-128). ITEM-09 의 사용자-노출 승인 라운드트립은 TASK-0304 의 사용자-승인된 "차단 미노출(효율적 답변만)" 결정을 **역전**하는 설계 충돌 → 임의 구현 안 함. 사용자 결정(2026-06-23) subsumed. 재검토 트리거: 승인-UX 가 silent-rewrite 보다 낫다는 근거 + TASK-0304 재논의(plan-ceo/eng-review). |

## 5. 진행 현황 (improve_cycle 가 갱신)
- 총 12 항목 · done 9 · rejected 1 · in-progress 0 · pending 0 · blocked 2
- 완료: **ITEM-01**(harness, A/B 측정 보류) · **ITEM-02**(샘플 저장소) · **ITEM-03**(피드백 flywheel PR-A코어+PR-B web, security SHIP-WITH-FIXES) · **ITEM-04**(DS 컨텍스트) · **ITEM-05**(하이브리드 fusion — 구현·리뷰 done, acceptance 반증→**gated-OFF dormant**) · **ITEM-07**(self-reflection, 회복률 측정 보류) · **ITEM-08**("AI 로 고치기" 표적 정정, 적대 리뷰 SHIP-WITH-FIXES M1 흡수) · **ITEM-10**(용어/ENUM) · **ITEM-11**(메타데이터 거버넌스 포탈 — MVP-1 용어/ENUM CRUD + Phase 2 테이블/컬럼 설명·주입·overlay·부트스트랩·샘플 admin, 적대 패널 2회 SHIP, RBAC `kb.ingest.manual`/`kb.sample.curate`).
- 진행중: 없음 (ITEM-11 Phase 2 마감으로 in-progress 0).
- 기각: **ITEM-09**(subsumed — shipped TASK-0304 silent-rewrite, §4).
- 보류(blocked, select_next_ready 제외): **ITEM-12**(retrieval 파라미터 튜닝) · **ITEM-06**(reranker) — 둘 다 measurement substrate gap(bge-m3 가 합성 KB 포화 → 측정 신호 0), 라이브 운영 질의 로그 확보 후 재개.
- ✅ **환경 (2026-06-23, 갱신)**: chat(claude-*, Anthropic-direct OAuth) ✓ · **임베딩 titan-embed→로컬 Ollama bge-m3(1024) 복구 ✓**(end-to-end 검증, PR#385). 임베딩 클러스터 차단 해소.
- **드레인 종료 상태(2026-06-24, ITEM-11 Phase 2 마감 갱신)**: ready(pending ∧ deps done) 0 — 전 항목이 done(9)·blocked(2, 측정 gap)·rejected(1). 추가 진행은 ① ITEM-06/12 는 라이브 질의 로그 확보 후 재개 ② 측정 보류분(ITEM-01/02 A/B·05 실가치) 라이브 로그 의존.
- 보류 측정(임베딩 복구로 이제 가능): ITEM-01/02 A/B·retrieval precision/recall — 해당 후속 측정 시 함께. ITEM-05 fusion 실가치·ITEM-06/12 는 라이브 질의 로그 필요(합성 KB 반증).
- 잔여 flag(별도 cleanup): kb_backend:940 주석 stale `vector(1536)`(정본 1024; schema.sql:68 texts 는 CHG-20260623T180000 으로 1024 정정 완료). bge-m3 provenance(embedding_model alias 기록).
