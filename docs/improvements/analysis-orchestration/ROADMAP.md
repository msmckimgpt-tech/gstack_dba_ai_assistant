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

T4 (2026-08-14 추가 — 요청당 낭비 제거):
ITEM-13 (형제 dedup, 독립)
ITEM-14 (캐싱 검증 스파이크) ──gates──▶ ITEM-15 (프롬프트 계약 정리)
```

- `ITEM-01/02/03 → ITEM-04`: L0 은 운영 DB 를 읽는다. `ds` 자원 게이트가 없으면 부하 제어가 강제
  수단 없는 선언이 된다.
- `ITEM-04 → ITEM-07/10`: 접지 없는 합성은 추측의 요약이고, 접지 없는 검증은 추측의 검증이다.
- `ITEM-14 → ITEM-15`: 두 항목은 **프롬프트 길이를 반대 방향으로 민다**. ITEM-15 는 프롬프트를
  줄이고, 캐싱은 최소 캐시 prefix(Haiku 4.5 = 4,096 토큰) 이상이어야 발동한다. 스파이크 결과를
  모르는 채 둘을 동시에 진행하면 한쪽이 다른 쪽을 무효화한다.

## 2. Phase 시퀀스

| Phase | 포함 ITEM | 병렬? | 진입 조건 |
|---|---|---|---|
| T0 | ITEM-01·02·03 | 순차 | (없음) |
| T1 | ITEM-04·05·06 | 순차(한 cycle) | T0 done |
| T1.5 | ITEM-12 | — | (없음) — T2 게이트 |
| T2 | ITEM-07·08·09 | 07→08 순차, 09 병렬 | ITEM-05 done + ITEM-12 done |
| T3 | ITEM-10·11 | 병렬 | ITEM-05 done |
| T4 | ITEM-13·14·15 | 13 독립 / 14→15 순차 | (없음) |

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

### ITEM-13 · 노드 분석 형제 dedup (요청 수 자체를 줄인다)
- **status**: rejected (2026-08-14 — 착수 직후 전제 반증)
- **rejected_because**: 등재 근거였던 "중복률 69.3%"는 **이름 중복률**이었고, 착수 후 측정한
  **내용 중복률은 사실상 0** 이다. 라이브 실측(`node_analysis_jobs` done + analysis):
  `AccountId` 261잡 → distinct summary **260**(99.6% 고유) · `regdate` 193 → **193**(100%) ·
  `member_srl` 104 → **104**(100%) · Table `character` 8 → **8**. 육안 확인 결과 이는 LLM
  비결정성이 아니라 **부모 테이블 맥락을 반영한 유의미한 차이**였다 —
  `dbLog.EquipTransform.AccountId`="장비 변환 이벤트를 수행한 플레이어 계정",
  `dbLog.Cheat.AccountId`="부정행위 적발 기록을 특정 플레이어 계정과 연결",
  `dbLog.ClassBuff.AccountId`="어느 게임 계정이 어떤 클래스 버프를 받았는지". 형제에게 대표
  분석을 상속시키면 이 맥락이 통째로 사라진다 — 절감이 아니라 **정보 손실**이다.
- **재논의 조건**: 이름이 아니라 **payload 구조 동일성**(부모 테이블·FK 상대·description 까지 일치)
  으로 판정하는 축을 세우고, 그 축의 실제 히트율이 유의미함을 먼저 측정할 것. 현 데이터에서는
  그 조건을 만족하는 형제가 드물 것으로 보인다(위 실측이 그 방증)
- **feature_id**: feature-0042-analysis-dedup
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: []
- **enables**: []
- **why**: 요청당 낭비를 줄이는 세 후보(dedup·캐싱·프롬프트 축소) 중 유일하게 **입력·출력 양쪽**을
  줄인다 — 나머지 둘은 입력만 건드린다. 라이브 실측(`node_analysis_jobs` 전량, 2026-08-13):
  Column 6,258잡 / distinct name 1,922 = **중복률 69.3%**(`AccountId` 261회 · `regdate` 193회 ·
  `member_srl` 104회), Table 3,355 / 1,796 = 46.5%, Routine 3,069 / 2,100 = 31.6%. 같은 구조의
  형제를 매번 따로 LLM 에 보내고 있다.
- **fit_verdict**: adopt-with-guard (guard: 이름만으로 묶지 않는다 · 대표 유래를 숨기지 않는다)
- **what**: `_enqueue_neighbors` 에 **형제 게이트**를 추가한다 — 구조 동일 형제는 대표 1건만 큐잉하고
  나머지는 대표 분석을 상속한다. 판정 축은 insight 의 검증된 패턴을 이식한다(`_build_table_groups`
  = base_stem + fingerprint **이중 축**). **이름 단독 판정 금지** — 같은 `AccountId` 라도 소속
  테이블이 다르면 참조 대상과 역할이 다르다. 상속분은 대표 유래를 분석문에 명시해 "자기 분석"으로
  위장시키지 않는다(insight 의 `source_meta.table_family` 와 동형).
- **entry_points**: `node_analysis.py:2194 _enqueue_neighbors`(게이트 삽입 — relevance 게이트·예산
  캡·`FOR UPDATE` 원자화가 이미 있는 자리) · `node_analysis.py:_persist`(대표 유래 키) ·
  `insight.py:151 _build_table_groups`(판정 축 재사용)
- **acceptance**: (a) 이름은 같지만 구조가 다른 노드가 **묶이지 않음**을 단위 테스트로 단정,
  (b) 상속 분석문에 대표 유래가 남아 UI 가 구분 가능, (c) 게이트 OFF 시 종전과 byte-동치,
  (d) 라이브에서 enqueue 억제분이 계측되고 분석 품질(`node_analysis_verdicts` supported 비율)이
  게이트 전후로 악화되지 않음
- **guards**: 스키마 변경 0(대표 유래는 `analysis` JSON 키 추가로 표현 — alembic 불필요) ·
  기본 OFF 로 배포해 라이브에서 켠다
- **effort**: 中

### ITEM-14 · 프롬프트 캐싱 검증 스파이크 (ITEM-15 의 방향 게이트)
- **status**: done (2026-08-14)
- **feature_id**: feature-0042-analysis-dedup
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: [ITEM-15]
- **why**: `node_analysis` 입력의 약 80%가 매 호출 재전송되는 고정 시스템 프롬프트다
  (`NODE_ANALYSIS_PROMPT` 9,124자 ≈ 1,780 토큰 = `min(prompt_tokens)` 1,778 과 일치, 입력 p50
  2,177). 고정 prefix + 고빈도 반복은 prompt caching 의 교과서 사례인데, **지금은 발동조차 하지
  않는다** — Haiku 4.5 의 최소 캐시 prefix 는 4,096 토큰이라 미달이면 에러 없이 조용히 무시된다.
- **fit_verdict**: adopt-with-guard (guard: 스파이크 전에 프롬프트를 건드리지 않는다)
- **what**: 코드 변경 전에 **전제 3항을 라이브로 확정**한다 — (1) litellm(OpenAI 규약) 경유로
  `cache_control` 이 Anthropic 까지 passthrough 되는가, (2) 4,096 토큰 미만에서 실제로 무음
  실패하는가(`cache_creation_input_tokens` 관측), (3) 구독형 OAuth 사용량 한도 회계에 캐시 읽기
  0.1× 가 반영되는가. 결과가 양성이면 ITEM-15 는 "프롬프트 축소"가 아니라 "캐시 가능 형태로
  재구성"이 된다.
- **entry_points**: `llm.py:1847 llm_node_analysis`(현재 `chat.completions.create` 직접 호출 —
  `cache_control` 을 실을 채널이 없다) · `litellm_config.yaml`
- **acceptance**: 3항 각각에 대해 **관측된 수치**로 판정(추정 금지). 음성 항목은 음성으로 기록한다
- **effort**: 小
- **notes**: 라이브 프로브 실행(`insight-worker` 컨테이너 → `bedrock-gateway`, `claude-haiku-4-meta`,
  각 조건 2회 호출). **관측 결과**:

  | 조건 | prompt_tokens | cache_creation | cache_read | 판정 |
  |---|---:|---:|---:|---|
  | A. 433 토큰 + `cache_control` | 433 / 433 | 0 | 0 | **무음 실패 확인** — 에러 없이 무시 |
  | B. 4,463 토큰 + `cache_control` | 4,463 / 4,463 | **4,422** → 0 | 0 → **4,422** | **캐시 발동 확인** |
  | C. 4,463 토큰, `cache_control` 없음 | 4,463 / 4,463 | 0 | 0 | 대조군 정상 |

  → (1) **litellm passthrough 동작한다** — OpenAI 규약 `content` 블록에 `cache_control` 을 실으면
  Anthropic 까지 전달된다(별도 전송 경로 불필요). (2) **4,096 미만은 무음 실패한다** — 현
  `NODE_ANALYSIS_PROMPT` 1,780 토큰은 `cache_control` 을 붙여도 영구 미발동. (3) 관측 채널 존재 —
  `usage.cache_creation_input_tokens` / `cache_read_input_tokens` 가 OpenAI 응답에 그대로 실리고
  `prompt_tokens_details.cached_tokens` 로도 매핑된다.
  **미확정으로 남긴 1항**: 구독형 OAuth 사용량 한도 회계에 캐시 읽기 0.1× 가 반영되는지는 usage·헤더
  어디에도 노출되지 않아 이 프로브로 판정 불가 — 장기 관측 과제로 이월(추정하지 않는다).

### ITEM-15 · 프롬프트 계약 정리 → **캐시 가능 형태로 재구성** (ITEM-14 로 방향 확정)
- **status**: pending (방향 확정 — 착수 전 안전망 필요)
- **feature_id**: feature-0042-analysis-dedup
- **dimension**: performance
- **risk_grade**: Major
- **depends_on**: [ITEM-14]
- **enables**: []
- **why**: 요청당 ~1,780 토큰의 고정 오버헤드. 다만 블록 분해 결과 9,124자의 60%가 계약
  4블록이다(Caveats 16% · Evidence-first 16% · Output 스키마 15% · Input 스키마 13%). 그리고 각
  블록은 특정 회귀에 대응해 추가된 흔적이 명확하다 — Caveats rule 은 코드 주석이 스스로
  `IMPORTANT — this is the field operators complained about` 라고 적고 있고, Untrusted-data rule 은
  프롬프트 인젝션 방어, Refine rule 은 §55 refine-not-override 계약이다. **군더더기 제거가 아니라
  계약 축소**라는 뜻이다.
- **fit_verdict**: adopt-with-guard (guard: 안전망 없이 착수 금지)
- **what**: ITEM-14 가 **양성으로 나왔으므로 방향은 "축소"가 아니라 "캐시 가능 형태로 재구성"이다.**
  현 1,780 토큰을 줄이면 캐시는 영영 발동하지 않는다(4,096 하한). 대신 프롬프트를 4,096 토큰 이상으로
  **정당하게** 키운다 — 억지 padding 이 아니라 **few-shot 예시 2~3개**(Table·Column·Routine 각 1개,
  입력 payload → 기대 출력 JSON)를 추가한다. 예시는 (a) 캐시 하한을 자연스럽게 넘기고 (b) 계약 4블록이
  산문으로 설명하던 것을 실물로 보여줘 품질도 올린다. 안정 prefix(계약+예시)를 앞, 가변 payload 를
  뒤로 두고 `cache_control` 은 system 블록 끝에 1개.
  **경제성**: 캐시 write 1.25× 1회 + read 0.1× N회이므로 5분 TTL 창에 2회 이상 호출이면 이득이다.
  워커는 60초 tick 으로 연속 호출하므로 창 안 재호출이 정상 경로다.
- **entry_points**: `llm.py:931 NODE_ANALYSIS_PROMPT`(예시 추가) ·
  `llm.py:1847 llm_node_analysis`(system 을 `content` 블록 리스트로 + `cache_control`) ·
  `_record_llm_usage`(캐시 필드 계측 — 현재 `usage` 의 cache 컬럼을 저장하지 않는다)
- **acceptance**: (a) 라이브에서 `cache_read_input_tokens > 0` 이 실제로 관측될 것(ITEM-14 의 B 조건이
  운영 경로에서 재현), (b) 변경 전후 `node_analysis_verdicts` 의 supported 비율이 악화되지 않음,
  (c) 캐시 미발동(하한 미달·프롬프트 변경 직후)에도 분석이 정상 동작(fail-open)
- **blocked_reason**: ~~ITEM-14 미완~~ **해소(2026-08-14)**. 남은 차단 사유는 **검증 표본 부족** 하나다 —
  `node_analysis_verdicts` 140건(supported 114 · unverifiable 14 · contradicted 12), 증거 커버리지
  `metadata_table_stats` 152행 / done 잡 12,088 = **1.3%**. 프롬프트 회귀 테스트는 **0건**
  (`unit/*/tests/` 전수 grep). 이 상태로 프롬프트를 바꾸면 품질 회귀를 관측할 수단이 없다.
  → 선행: ITEM-11 플래너로 증거 커버리지 확대, 또는 프롬프트 출력 계약(JSON 필드 존재·caveats 빈값
  규칙 등)을 고정하는 최소 회귀 테스트 신설
- **effort**: 小(편집) / 中(검증)

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
| LLM 요청 batch 화 (Message Batches API / 다건 묶기) | **기각** | 2026-08-14 사용자 질문. Batches API = 전송 경로 부재 + 구독형이라 50% 할인 가치 0 + 24h SLA 불일치. 다건 묶기 = 출력이 안 줄어 max_tokens 상한 초과(p95×5 = 13,535 > 13,000) + per-job 상태기계(attempts·backoff·회로차단) 붕괴. 상세는 §5 "T4 추가 경위" |
| **노드 분석 형제 dedup (ITEM-13)** | **기각** | 이름 중복률(69.3%)과 **내용 중복률(≈0)** 을 혼동한 등재였다. `AccountId` 261잡 → distinct summary 260. 형제 분석문의 차이는 비결정성이 아니라 부모 테이블 맥락이라 상속은 정보 손실이다. 상세는 ITEM-13 `rejected_because` |

## 5. 진행 현황 (improve_cycle 갱신)

- 총 15 · **done 13** (ITEM-14 추가) · in-progress 0 · pending 1 (ITEM-15) · rejected 1 (ITEM-13)
- 다음 ready: **없음** — ITEM-15 는 방향이 확정됐으나 검증 표본 부족으로 착수 보류
  (선행: 증거 커버리지 확대 또는 프롬프트 출력 계약 회귀 테스트 신설)
- T1~T3 는 2026-07-31 완주. **T4 는 2026-08-14 추가** — batch 요청 구조 검토(사용자 요청)에서
  batch 자체는 기각되었으나 그 검토가 드러낸 요청당 낭비를 다루는 트랙이다.

### T4 추가 경위 (2026-08-14)

사용자 질문은 "워커의 LLM 요청을 batch 형태로 보내는 구조가 적절한가"였다. 두 해석 모두 기각됐다:

| 해석 | 판정 | 근거 |
|---|---|---|
| Anthropic Message Batches API | **기각** | (1) 앱은 OpenAI 규약으로 litellm 에 보내므로 별도 엔드포인트에 도달 경로가 없다 (2) 50% 할인은 종량제 전제인데 서빙이 **OAuth 구독 토큰**이라 토큰당 과금이 없다 → 할인 가치 0 (3) 최대 24h SLA 가 진행률을 보며 기다리는 준실시간 잡(tick 60초 · lease 900초)과 불일치. Bedrock/Vertex 미지원도 겹친다 |
| 여러 대상을 한 요청에 묶기 | **기각** | 출력은 줄지 않는다 — `node_analysis` 출력 p95 2,707 × 5 = 13,535 > 실질 여유 13,000(max_tokens 18,000 − thinking 5,000), 단건도 cap 히트 이력 있음. 더해 per-job 상태기계(attempts·backoff·회로차단·refine pass_no)가 잡 1건 단위라 부분 실패를 표현할 수 없다. 같은 결론이 이미 코드에 있다 — `analysis_verify` docstring: *"판정은 1건 1콜이다(배치하면 한 건의 오판이 다른 건으로 번진다)"* |

기각의 부산물로 **요청당 낭비의 정량**이 확보됐고(입력 80%가 고정 프롬프트, 형제 중복률 최대
69.3%), 그것을 batch 보다 싼 수단으로 회수하는 것이 T4 다.

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
