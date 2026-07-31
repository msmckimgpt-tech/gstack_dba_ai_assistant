---
doc_type: DQA_ROADMAP
initiative: analysis-orchestration
created_at: 2026-07-30
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — AI 능동 분석 구조 재설계

> 사용자 원 요청(2026-07-30): "AI 능동 분석이 단발성 + 유사 노드 재귀의 일차원 구조다. 오케스트레이터
> 중심으로 파견·집계할 수 있는가, 아니면 더 좋은 구조가 있는가. 웹 리서치로 찾아 이 프로젝트에 녹여라."
> 진단·리서치·설계·리뷰 전문은 [`RESEARCH.md`](./RESEARCH.md).

## 0. 맥락 (context-free 진입)

관리 콘솔 그래프 뷰의 'AI 능동 분석'은 노드 하나를 분석한 뒤 관련도 게이팅으로 이웃을 재귀 분석하는
**지역 탐색**이다. 라이브 실측상 노드 1만 건을 분석했지만(월 10,620 LLM 콜) 그 분석문이 상위 의미로
접히는 층이 없고(727 클러스터에 32자 라벨만), 분석 입력에 데이터 증거가 없어 **이름 규칙 추측**이
사실상 정본이다(summary 평균 94자).

- 대상 제품: 사내 DBA AI assistant — 자연어 → SQL + 메타데이터 지식그래프
- 정본 진입: `repo/AGENTS.md` · `docs/PROJECT.md` · `docs/ARCHITECTURE.md` ·
  `unit/feature-0016-metadata-graph/docs/*`(그래프 정본) ·
  코드 거주 `unit/feature-0002-agent-core/src/modules/{node_analysis,semantic_cluster,insight}.py`
- 측정 기반: `RESEARCH.md` §1.2(라이브 PG 실측) · `bin/perf-snapshot.sh` §12(워커 공유 자원)

**핵심 결론 2가지** (리뷰 2채널로 확정 — `RESEARCH.md` §2·§4.9):
1. 오케스트레이터 방향은 맞지만 **LLM 오케스트레이터는 최선이 아니다** — fan-out 은 이미 결정적 큐로
   구현돼 있고, 2026 프로덕션 패턴도 "결정적 백본 + 특정 스텝만 LLM"이다. LLM 이 실제로 필요한 곳은
   계획이 아니라 **집계(합성)와 검증**이다.
2. 가장 근본 문제는 계층 요약 부재가 아니라 **접지 부재**다 — 접지 없이 상위 요약을 얹으면 "추측의
   요약"이 되어 틀린 내용을 더 권위 있게 만든다. 따라서 순서는 **접지 → 합성**이다.

## 1. 종속성 그래프

```
ITEM-01 ─┐
ITEM-02 ─┼─requires──▶ ITEM-04 ──▶ ITEM-05 ──▶ ITEM-06
ITEM-03 ─┘  (T0 자원)     (L0 증거)   (L1 주입)   (thin 재정의)
                             │
                             ├──enables──▶ ITEM-07 ──▶ ITEM-08 ──▶ ITEM-09
                             │             (L2 요약)   (L3 lazy)   (소비 배선)
                             └──enables──▶ ITEM-10 · ITEM-11
                                           (검증층)   (플래너)
```

- `ITEM-01/02/03 → ITEM-04`: L0 은 운영 DB 를 읽는다. `ds` 자원 게이트가 없으면 부하 제어가 강제
  수단 없는 선언이 된다.
- `ITEM-04 → ITEM-07/10`: 접지 없는 합성은 추측의 요약이고, 접지 없는 검증은 추측의 검증이다.

## 2. Phase 시퀀스

| Phase | 포함 ITEM | 병렬? | 진입 조건 |
|---|---|---|---|
| T0 | ITEM-01·02·03 | 순차 | (없음) |
| T1 | ITEM-04·05·06 | 순차(한 cycle) | T0 done |
| T1.5 | ITEM-12 | — | (없음) — T2 게이트 |
| T2 | ITEM-07·08·09 | 07→08 순차, 09 병렬 | ITEM-05 done + ITEM-12 done |
| T3 | ITEM-10·11 | 병렬 | ITEM-05 done |

Phase 는 권장 순서이지 강제 배리어가 아니다 — `depends_on` 이 충족되면 후행 Phase 항목도 ready 다.

## 3. 항목 (각 1 cycle)

### ITEM-01 · 공유 자원 예산(LLM) + 전역 kill-switch + 워커 계측
- **status**: done
- **feature_id**: feature-0025-worker-parallelism
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: [ITEM-04]
- **why**: RI-0 — 워커 4종이 동시에 LLM·소스DB·PG 를 무제한으로 잡아 서로를 굶긴다. 분석층을
  키우기 전에 자원 상한이 없으면 증설이 곧 장애다.
- **fit_verdict**: adopt
- **what**: `shared/resource_budget.py` — 자원 종류 단위 세마포어(`llm`), `available()` 조회,
  fail-soft 게이트(획득 실패 시 다음 tick 이월), `AGENT_BACKGROUND_ANALYSIS_ENABLED` 전역 kill-switch,
  JSON 스냅샷 flush.
- **entry_points**: `shared/resource_budget.py` · `shared/runtime_settings.py` `_PERF_SPECS`
- **acceptance**: 게이트 통과/거절이 telemetry 에 계측 · kill-switch off 시 claim 단계에서 차단 ·
  래퍼/`_*_inner` 분리로 반납 누수 구조적 차단
- **effort**: 中
- **notes**: PR #1078 머지·배포 완료. ADR-0025-05·06·07 확립.

### ITEM-02 · 커넥션 축 게이트(`ds`·`task`) + 콘솔 노출
- **status**: done
- **feature_id**: feature-0025-worker-parallelism
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: [ITEM-01]
- **enables**: [ITEM-04]
- **why**: RI-0 — LLM 만 막으면 소스 DB 커넥션이 무제한이라 운영 DB 가 병목·장애 지점이 된다.
- **fit_verdict**: adopt
- **what**: `ds`/`task` 자원 추가 + `node_analysis`·`semantic_cluster`·`product_classify`·
  `routine_backfill` 배선, 워커 자원 현황을 공유 볼륨 JSON → 관리 콘솔 'AI 운영 현황' 표로 노출.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py` `_worker_resources()` ·
  `src/static/admin.js` · `bin/perf-snapshot.sh` §12
- **acceptance**: 콘솔에서 자원별 peak/limit/거절 수 확인 가능 · ds 슬롯 누수 없음(connect 를 try 안)
- **effort**: 中
- **notes**: PR #1079. ADR-0025-08. `AGENT_WORKER_PG_BUDGET` 은 게이트 불가라 **의도적으로 미노출**.

### ITEM-03 · 워커 스냅샷 identity 안정화
- **status**: done
- **feature_id**: feature-0025-worker-parallelism
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: [ITEM-02]
- **enables**: [ITEM-04]
- **why**: 스냅샷 파일명이 재배포마다 누적돼 콘솔이 stale 파일을 읽을 수 있었다.
- **fit_verdict**: adopt
- **what**: role 기반 파일명 + 7일 임계 reaper(unlink 직전 mtime 재확인) + `(-mtime, path)` tie-break.
- **entry_points**: `shared/resource_budget.py` `_worker_role_default()`·`_reap_stale_snapshots()`
- **acceptance**: 재배포 후에도 콘솔이 현행 스냅샷만 표시
- **effort**: 小
- **notes**: PR #1082 머지·`make deploy-all` 완료(2026-07-30).

### ITEM-04 · L0 증거 수집층 (통계 전용, 원시 샘플값 배제)
- **status**: done
- **feature_id**: feature-0031-analysis-grounding
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-01, ITEM-02, ITEM-03]
- **enables**: [ITEM-05, ITEM-07, ITEM-10]
- **why**: RI-1 — 분석 입력(`_build_payload`)에 이름·설명·이웃만 있고 **데이터 실측이 0**이다.
  그래서 프롬프트가 "이름 규칙에서 추론하라"고 지시할 수밖에 없었고, 결과는 추측이 정본이 된다.
  DBAutoDoc(2025) 실측: 통계 기반 결정적 키 탐지가 LLM 단독 대비 FK 판정 F1 +23p.
- **fit_verdict**: adopt-with-guard (guard: 원시 샘플값·문자열 극단값 미저장 · `ds` 예산 위 ·
  전수 스캔 금지 · 쿼리 타임아웃 강제)
- **what**:
  - 신규 테이블 `metadata_table_stats`(scope_key, schema_name, table_name PK + row_count_est,
    column_count, pk_columns, index_columns, fk_out, fk_in, stage, sampled_rows, collected_at, error)
  - 신규 테이블 `metadata_column_stats`(… + column_name PK + data_type, is_nullable, char_max_len,
    distinct_est, null_ratio, num_min/num_max, ts_min/ts_max, len_min/len_max/len_avg,
    **value_pattern**(digits|hex|uuid|email_like|mixed — 패턴 클래스이지 값이 아님), stage,
    sampled_rows, collected_at). alembic **additive**, downgrade 가역.
  - **문자열 min/max 값은 저장하지 않는다** — 극단값은 실질적 원시 샘플이고 이름·이메일 컬럼에서
    곧 PII 다. 숫자·시각 타입만 min/max 를 남기고, 문자열은 길이 분포 + 패턴 클래스로 대체한다.
  - 수집 단계: Stage0 카탈로그만 → Stage1 표본 100 → Stage2 표본 1,000 → Stage3 정밀.
    승격은 **하루 최대 1단계 + 시간창 상한 + 운영자 승인**(AIMD 미채택 — `RESEARCH.md` §4.9).
- **entry_points**: 신규 `unit/feature-0002-agent-core/src/modules/metadata_stats.py` ·
  `node_analysis.py:605 _introspect_table_columns`(ds 게이트 선례) ·
  `unit/feature-0002-agent-core/alembic/versions/`
- **acceptance**: (a) 원시 샘플값·문자열 극단값이 저장·주입되지 않음을 **구조 테스트로 단정**,
  (b) `ds` 예산 거절 시 다음 주기 이월(fail-soft), (c) Stage 승격이 하루 1단계·운영자 승인 없이는
  일어나지 않음을 테스트로 단정, (d) 배포 후 운영 DB 부하 신호 무변화
- **guards**: kill-switch(`AGENT_BACKGROUND_ANALYSIS_ENABLED`) 하위 · 실패는 fail-soft
- **effort**: 大
- **notes**: risk_grade Major 사유 = 운영 DB 에 신규 read 부하. 사용자 승인 있음(2026-07-30
  "모든 트랙 완주까지 진행"). 배포 scope: 워커.

### ITEM-05 · L1 payload 증거 주입 + 프롬프트 완화
- **status**: done
- **feature_id**: feature-0031-analysis-grounding
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-04]
- **enables**: [ITEM-06, ITEM-07, ITEM-10]
- **why**: 증거를 모아도 프롬프트에 닿지 않으면 접지가 아니다. 현행 프롬프트는 "이름 규칙에서
  가장 그럴듯한 의미를 추론하고 단정하라"고 지시한다 — 증거가 생긴 뒤에는 이 지시가 해롭다.
- **fit_verdict**: adopt-with-guard (guard: 증거를 `semantic_cluster` 시그니처에 넣지 않는다)
- **what**: `_build_payload` 에 `evidence` 블록(테이블 통계 + 컬럼 통계 상위 N) 추가.
  `NODE_ANALYSIS_PROMPT` 를 "증거 우선, 증거가 없을 때만 이름 규칙"으로 개정 +
  `evidence` 를 untrusted-data 규칙 대상에 명시. caveats 는 자기-불평 금지(ADR-034)를 유지하되
  증거 기반 위험(고카디널리티 개인정보 의심 컬럼 · null 비율 이상 · 미검증 FK)을 쓸 근거가 생긴다.
- **entry_points**: `node_analysis.py:755 _build_payload` · `llm.py:930 NODE_ANALYSIS_PROMPT`
- **acceptance**: LLM 콜 수 불변(주입만) · 표본 노드 재분석 전/후 summary 밀도·caveats 실질성
  실측 대조 · 증거 필드가 `semantic_cluster` 시그니처에 유입되지 않음을 테스트로 단정
- **guards**: 증거 변경은 L2 요약 캐시 키로만 전파(ITEM-07) — 시그니처 유입 시 전량 재임베딩 폭주
- **effort**: 中
- **notes**: 프롬프트 계약 변경이므로 `docs/` LLM 계약 문서 동반 갱신.

### ITEM-06 · thin 판정 재정의 (길이 → 항목 충족도)
- **status**: done
- **feature_id**: feature-0031-analysis-grounding
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-05]
- **enables**: []
- **why**: `_analysis_is_thin` 은 summary 120자 미만을 thin 으로 보는데, 프롬프트 계약이 "한국어
  1~2문장"(≈50~100자)이라 **정상 분석 대부분이 thin 판정**된다. 지금은 `REFINE_MAX=30`/run 캡이
  폭주를 막고 있을 뿐이며, 캡을 올리면 대량 재분석이 터진다.
- **fit_verdict**: adopt
- **what**: 길이 임계 → 항목 충족도(역할·관계·용도가 실질 내용인지 + 증거 뒷받침 여부)로 전환.
  `AGENT_NODE_ANALYSIS_THIN_CHARS` 는 하위호환 fallback 으로만 남긴다.
- **entry_points**: `node_analysis.py:2157 _analysis_is_thin` · `:2216 _backrefine_neighbors`
- **acceptance**: 라이브 done 분석문 표본에 대해 전/후 thin 비율 분포 대조 — 신 판정이 실제 빈약
  분석에만 수렴(정상 1~2문장 분석이 thin 으로 잡히지 않음)
- **effort**: 小
- **notes**: 판정 변경은 back-refine 물량에 직결 — 캡 유지한 채 배포 후 실측.

### ITEM-07 · L2 클러스터 요약 (신규 저장 계약)
- **status**: done
- **feature_id**: feature-0032-analysis-synthesis
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-05]
- **enables**: [ITEM-08, ITEM-09]
- **why**: RI-2 — 727개 컨텐츠 클러스터에 32자 라벨만 있고 요약이 없다. GraphRAG 계열의 핵심 이득
  (전역 질의 토큰 97%↓)은 계층 요약에서 나온다.
- **fit_verdict**: adopt-with-guard (guard: 아래 4개 불변식)
- **what**: 클러스터 단위 요약 생성·저장. **`_llm_content_labels` 확장이 아니다** — 그것은 32자
  라벨 계약이라 요약기가 아니다(codex 리뷰 P1). 신규 저장 계약:
  1. 저장 키 = `member_set_hash + evidence_version + l1_version`(2중 버전)
  2. **시그니처 미유입 불변식** — 요약이 클러스터링 입력으로 되먹임되면 순환한다
  3. **클러스터 버전 스냅샷** 위에서만 커밋(집계 중 재클러스터링과의 일관성 경계)
  4. payload **결정적 정렬**(현행 `_llm_content_labels` 는 ORDER BY 가 없어 캐시가 오적중한다)
  요약에 "멤버 N개 중 M개 상세분석 근거" 명시(커버리지 14.6% 하에서의 정직성).
- **entry_points**: `semantic_cluster.py` `_llm_content_labels` 주변 · 신규 테이블
- **acceptance**: 727콜 이내 1회 전량 생성 · 동일 입력 재실행 시 캐시 적중률 ≥95%(결정적 정렬 효과)
  · 요약이 시그니처에 유입되지 않음을 테스트로 단정
- **guards**: 일일 토큰 cap 또는 circuit-breaker 선행(§4)
- **effort**: 大
- **notes**: 배치는 5~8개(라벨용 40 배치는 요약엔 과다).

### ITEM-08 · L3 도메인 합성 (lazy)
- **status**: done
- **feature_id**: feature-0032-analysis-synthesis
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: [ITEM-07]
- **enables**: [ITEM-09]
- **why**: 스키마(effective schema 기준, MSSQL=DB) ~370 + 제품 ~17 층의 도메인 서술이 없다.
- **fit_verdict**: adopt-with-guard (guard: 사전 전량 생성 금지)
- **what**: 요청·질의가 유발할 때 합성하고 캐시(LazyGraphRAG 교훈 — 사전요약 0으로도 전역질의
  품질 동등, 비용 700배↓). 사전 배치 생성은 하지 않는다.
- **entry_points**: ITEM-07 저장 계약 재사용
- **acceptance**: 미요청 스키마에 대해 LLM 콜 0 · 요청 시 캐시 미스 1회만 합성
- **effort**: 中

### ITEM-09 · 분석 산출물 → 대화 grounding 배선
- **status**: done
- **feature_id**: feature-0032-analysis-synthesis
- **dimension**: functional
- **risk_grade**: Major
- **depends_on**: [ITEM-07]
- **enables**: []
- **why**: RI-5 — 1만 건을 분석해 놓고 **대화 답변 경로가 그것을 읽지 않는다**(`kb_retrieval`·
  `knowledge` 에서 `node_analysis` 참조 0). 분석의 가치가 콘솔 열람에만 갇혀 있다.
- **fit_verdict**: adopt-with-guard (guard: 런타임 합성 금지 — 사전 계산분만 주입)
- **what**: 질의 관련 클러스터/도메인 요약 1~2건을 답변 컨텍스트에 주입.
- **entry_points**: `kb_retrieval` / `agent_core` grounding 조립 지점
- **acceptance**: 주입 전/후 답변 정확도 표본 대조 · 체감 지연 증가 0(feature-0027 이 확보한
  -25~35s 를 잠식하지 않음)
- **guards**: 지연 예산 초과 시 주입 생략(fail-soft)
- **effort**: 中
- **notes**: risk_grade Major 사유 = 사용자 대면 답변 경로 변경.

### ITEM-10 · 분석 검증층
- **status**: done
- **feature_id**: feature-0033-analysis-trust
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: [ITEM-05]
- **enables**: []
- **why**: RI-3 — 생성된 분석의 사실성을 아무도 확인하지 않는다. LLM-as-judge 로 소형 판정자를
  쓰면 비용 97%↓로 검증층을 붙일 수 있다(2025~2026 표준 패턴).
- **fit_verdict**: adopt-with-guard (guard: red-team 재사용 금지 · `pass_no` 재사용 금지)
- **what**: 분석문 ↔ 증거(ITEM-04) 대조 판정. feature-0021 red-team 은 **답변 전용 프롬프트**
  (question+draft+evidence)라 재사용 불가(codex 실측) — 신규 인프라다. 상태는 별도
  verification state/version 으로 두고 `pass_no`(back-refine 의미)와 섞지 않는다.
- **entry_points**: 신규 · `node_analysis_jobs` 인접 테이블
- **acceptance**: 판정 실패가 "미검증"으로 정직하게 표기(fail-open 이 "검증됨"으로 표시하지 않음)
  · 독립 비용 상한 준수
- **effort**: 大

### ITEM-11 · 결정적 플래너 (분석 대상 선정)
- **status**: done
- **feature_id**: feature-0033-analysis-trust
- **dimension**: performance
- **risk_grade**: Minor
- **depends_on**: [ITEM-05]
- **enables**: []
- **why**: RI-4 — 분석 대상이 "사용자가 클릭한 노드 + 이웃"으로만 정해져 커버리지가 중요도와
  무관하게 편향된다(현행 14.6%).
- **fit_verdict**: adopt-with-guard (guard: AGE 실시간 중심성 계산 금지)
- **what**: degree + 대화 JOIN 학습(`table_relationships`) 사용빈도 기반 우선순위. 중심성은 AGE
  multi-hop 이 최악 82초라 **materialized metric** 으로만 쓴다.
- **entry_points**: `node_analysis.py:2054 _relevance` 주변 · 신규 우선순위 뷰
- **acceptance**: 상위 우선순위 노드가 실제 대화에서 참조되는 테이블과 상관 ≥ 현행
- **effort**: 中

### ITEM-12 · 백그라운드 LLM 토큰 예산
- **status**: done
- **feature_id**: feature-0032-llm-token-budget
- **dimension**: operational
- **risk_grade**: Major
- **depends_on**: []
- **enables**: [ITEM-07, ITEM-08]
- **why**: §4 의 "T2 진입 전 필수" 항목을 실측으로 확정했다. `TODOS.md` P3 의 종결 근거
  ("100% edge → 과금 없음")가 반전됐다 — 7일 Anthropic 8,654콜/55,567,176 토큰 vs edge 25콜
  (과금 lane 99.7%). 그중 사람 confirm 없는 백그라운드가 약 2,600만 토큰/7일인데 상한이 없었다.
  T2 는 여기에 L2 요약을 더 얹는 트랙이라 상한 없는 자동 지출을 늘리는 방향이다.
- **fit_verdict**: adopt-with-guard (guard: 사용자 요청 경로 완전 제외 · fail-open 3중)
- **what**: `shared/llm_budget.py` — `agent_runtime.llm_usage` 기반 rolling 24h 백그라운드 토큰
  집계 + 백그라운드 진입점 3곳 게이트 + 콘솔 현황·attention. circuit-breaker 는 신규 구현하지
  않는다(`llm_provider_health` 가 429/401 축을 이미 담당).
- **entry_points**: `shared/llm_budget.py` · `node_analysis._process_pending_inner`(claim 전) ·
  `semantic_cluster.run_cluster_maintenance` · `product_classify.run_classify_pass` ·
  `routers/ai_ops.py` · `static/admin.js`
- **acceptance**: (a) 사용자 요청 경로가 집계·차단 양쪽에서 제외됨을 **집계 SQL 파라미터 검사**로
  단정, (b) fail-open 3중(상한 0·조회 실패·모듈 부재), (c) 소진 시 본체 미실행 + 정직한 skip 사유,
  (d) 콘솔이 실제로 렌더(응답 필드 존재 ≠ 노출), (e) 라이브에서 상한을 낮춰 게이트 실동작 관측
  하되 같은 창에서 대화 답변이 정상일 것
- **guards**: 기본 상한 2,000만 = 24h 실측(685만)의 약 3배 → 배포 시 정상 운영 무영향
- **effort**: 中
- **notes**: PR #1089 머지·배포(eee1f4fb)·PB-0008 PASS. 게이트 커버리지 96%(진입점 3곳) — 나머지는 계량되지만 차단되지 않음(ADR-0032-05). 라이브 실증: 상한을 낮춘 별도 프로세스에서 3개 게이트 모두 `claimed=0` 으로 차단, 사용자 경로 365만 토큰(24h)은 예산에서 제외 확인.

## 4. 보류·기각 (재논의 방지)

| finding | verdict | 사유 |
|---|---|---|
| LLM 오케스트레이터(lead agent)로 파견·집계 | **기각** | fan-out 은 이미 결정적 큐로 존재 → 얻는 것 없이 토큰 15배·비결정성 증가. 2026 프로덕션 70%가 결정적 orchestrator-worker. 탐색 모드 한정 옵션으로만 여지 |
| AIMD 적응형 부하 제어 | **기각** | 전제 불성립(우리가 지배적 부하원이 아니고 신호 지연이 크다) → 발진 위험. 시간창 상한 + 하루 1단계 승격 + 운영자 승인으로 대체 |
| `AGENT_WORKER_PG_BUDGET` | **기각** | 커넥션 수명과 예산 수명 결합에 광범위 리팩터 필요 → `task`(작업 단위)로 근사. 게이트 없는 이름을 노출하지 않는다(ADR-0025-06) |
| 워커 자원 PG 테이블 | **보류** | 공유 볼륨 파일로 충분(마이그레이션·라우트 0). 워커·web 이 분리 배치되면 재검토 |
| L2 를 `_llm_content_labels` 확장으로 | **기각** | 32자 라벨 계약이라 요약기가 아니다 — 신규 저장 계약 필요(codex P1) |
| L1 전량 확대(+15,000콜) | **보류** | 중요도 상위 + lazy 로 두고 전역 이해는 L2/L3 가 담당(LazyGraphRAG 교훈) |
| **일일 토큰 cap 재평가** | **완료 → ITEM-12 신설** | 실측으로 전제 반전 확정(7일 Anthropic 8,654콜/55,567,176 토큰 vs edge 25콜 = 과금 lane 99.7%). cap 은 ITEM-12 로 구현, circuit-breaker 는 `llm_provider_health` 가 이미 담당하므로 신규 구현 안 함 |
| 원시 샘플값 수집 | **기각** | 사용자 확정(2026-07-30) — PII 표면 제거. 문자열 극단값(min/max)도 실질 원시값이라 함께 배제, 길이 분포 + 패턴 클래스로 대체 |

## 5. 진행 현황 (improve_cycle 갱신)

- 총 12 · **done 12** · in-progress 0 · pending 0 · blocked 0
- 다음 ready: (없음 — 로드맵 완주 2026-07-31)

### 완주 시점 라이브 실측

| 층 | 산출물 | 규모 |
|---|---|---|
| L0 증거 | `metadata_table_stats` | 수집 진행 중(플래너가 커버리지를 채우는 중) |
| L1 분석 | `node_analysis_jobs` done | 10,576 |
| L2 요약 | `cluster_summaries` | 1,006 (120 스키마) |
| L3 도메인 | `domain_summaries` | lazy — 요청분만 |
| 검증 | `node_analysis_verdicts` | 판정 동작 확인(모순 1건 적발) |
| 소비 | 답변 grounding 주입 | 지연 99.4ms |
| 비용 | 백그라운드 토큰 예산 | 24h 상한 2,000만(실측 소비 685만) |


## 6. 이 initiative 에서 확립된 운영 규약

- **ADR-0025-05** 예산은 자원 종류 단위로 두고, 게이트는 호출측에서 명시적으로 건다
  (커넥션 헬퍼에 넣으면 web 요청 경로가 함께 걸린다)
- **ADR-0025-06** 게이트가 없는 상한 knob 을 노출하지 않는다(거짓 컨트롤 금지)
- **ADR-0025-07** 진입 게이트는 래퍼/`_*_inner` 분리로 감싼다(반납 누수는 조용한 전역 고장)
- **ADR-0025-08** 워커 자원 콘솔 노출은 공유 볼륨 파일 경유(PG 테이블 신설하지 않음)
