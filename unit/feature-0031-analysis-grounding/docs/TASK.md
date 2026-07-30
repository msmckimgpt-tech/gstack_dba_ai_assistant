---
doc_type: TASK
feature_id: feature-0031-analysis-grounding
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (T1 접지 슬라이스 구현 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-30

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  `unit/feature-0002-agent-core/src/modules/metadata_stats.py`(신규) ·
  `unit/feature-0002-agent-core/alembic/versions/*_metadata_stats.py`(신규) ·
  `unit/feature-0002-agent-core/src/modules/node_analysis.py`(payload evidence · thin 판정) ·
  `unit/feature-0002-agent-core/src/modules/llm.py`(`NODE_ANALYSIS_PROMPT` 개정) ·
  `shared/runtime_settings.py`(수집 knob) ·
  `unit/feature-0002-agent-core/tests/test_metadata_stats.py`(신규)
- **접근 방법:** 운영 DB 에서 **통계만**(원시 샘플값 배제) 단계적으로 수집해 `agent_kb` 에 적재하고
  (`ds` 자원 예산 게이트 위, fail-soft), 그 통계를 노드 분석 LLM payload 의 `evidence` 블록으로
  주입한다. 프롬프트를 "이름 규칙 추론"에서 "증거 우선"으로 개정하고, 길이 기반 thin 판정을
  항목 충족도 기반으로 바꾼다.
- **위험도:** Major — 운영 DB 에 신규 read 부하가 생긴다(파괴적 작업·스키마 변경 없음, 읽기 전용).
  완화: `ds` 예산 게이트 · 전수 스캔 금지 · 쿼리 타임아웃 · Stage 승격 하루 1단계 + 운영자 승인 ·
  전역 kill-switch(`AGENT_BACKGROUND_ANALYSIS_ENABLED`) 하위.

<!-- PLAN-APPROVED by mckim on 2026-07-30 (AskUserQuestion: "T0 부터 순차" + "샘플값 배제 확정" + "모든 트랙 완주까지 자율 진행") -->

### 2.2 근거
설계·리서치 전문: `docs/improvements/analysis-orchestration/RESEARCH.md`
로드맵(ITEM-04·05·06): `docs/improvements/analysis-orchestration/ROADMAP.md`

## 3. Task Queue

- [ ] TASK-0001 `metadata_table_stats` · `metadata_column_stats` alembic additive 마이그레이션
- [ ] TASK-0002 `metadata_stats.py` — 카탈로그 수집(Stage 0): 컬럼 타입·nullable·길이 상한,
      PK/인덱스/FK 선언, 근사 row count (MySQL `information_schema` / MSSQL `sys.*`)
- [ ] TASK-0003 `metadata_stats.py` — 표본 통계(Stage 1·2): distinct 추정·null 비율·숫자/시각
      min·max·문자열 길이 분포·패턴 클래스. **문자열 원시값 미저장**
- [ ] TASK-0004 Stage 승격 정책 — 하루 1단계 · 시간창 상한 · 운영자 승인 게이트
- [ ] TASK-0005 `ds` 예산 게이트 배선 + fail-soft(거절 시 다음 주기 이월)
- [ ] TASK-0006 `_build_payload` 에 `evidence` 블록 주입 (시그니처 미유입 불변식 유지)
- [ ] TASK-0007 `NODE_ANALYSIS_PROMPT` 개정 — 증거 우선 + evidence 를 untrusted-data 대상에 명시
- [ ] TASK-0008 `_analysis_is_thin` 재정의 — 길이 → 항목 충족도
- [ ] TASK-0009 테스트: 원시값 미저장 구조 단정 · 예산 거절 이월 · 승격 정책 · payload 계약
- [ ] TASK-0010 verify-completion --pre-commit → PR → CI → 머지 → `make deploy-all` → PB-0008

## 9. Requested Scope (요청 범위 자기-열거)

원 요청(2026-07-30): "AI 능동 분석이 단발성 + 유사 노드 재귀의 일차원 구조다. 오케스트레이터 중심
파견·집계로 갈 수 있나, 아니면 더 좋은 구조가 있나. 대규모 관계 데이터 분석의 모범 구조를 웹
리서치로 찾아 이 프로젝트에 녹여라." + 후속 지시(적응형 부하 + 운영 DB 부하 관측 · 저렴한 설계보다
근본 해소 우선 · 샘플값 배제 · 모든 트랙 완주).

- [x] `현행 구조 진단` — 산출물: `docs/improvements/analysis-orchestration/RESEARCH.md` §1 ·
      배선 확인: 라이브 PG 실측(분석 1만 건·월 10,620 콜·summary 평균 94자·클러스터 727·
      분석 입력의 데이터 실측 0·대화 경로 참조 0)
- [x] `웹 리서치(대규모 관계 데이터 분석 모범 구조·최근 AI 트렌드)` — 산출물: RESEARCH.md §3
      (GraphRAG·LazyGraphRAG·RAPTOR·DBAutoDoc·semantic layer·Spider 2.0/CHESS·LLM-as-judge·
      증분 인덱싱·multi-agent 실측) · 배선 확인: 각 패턴을 채택/기각 판정과 함께 ROADMAP §4 에 반영
- [x] `"오케스트레이터 파견·집계" 가부 판정` — 산출물: ADR-0031-02 · 배선 확인: fan-out 이 이미
      결정적 큐(`node_analysis_jobs`)로 존재함을 코드로 확인 → LLM 오케스트레이터 기각, 집계(L2)·
      검증(T3)으로 위치 이동
- [x] `프로젝트 적합 설계로 구성` — 산출물: `ROADMAP.md`(11 ITEM, 종속성·Phase·완료 판정식) ·
      배선 확인: `/_dqa:improve_cycle` 파싱 계약(status·feature_id·depends_on) 준수
- [x] `적응형 부하 + 운영 DB 부하 관측` — 산출물: Stage 0~3 승격 정책(`metadata_stats.plan_stage`·
      `stage_ceiling`) + T0 의 `ds` 예산·워커 자원 스냅샷 · 배선 확인: 승격 정책 테스트 5건,
      부하 관측은 `bin/perf-snapshot.sh` §12 + 콘솔 '워커 공유 자원' 표(T0b 배포 완료)
- [x] `샘플값 배제` — 산출물: 통계 전용 스키마 + `value_pattern` CHECK 제약 ·
      배선 확인: 집계 산출물·upsert 바인딩·evidence 블록 3지점에서 원시값 부재를 테스트로 단정
- [x] `T1 접지 구현` — 산출물: alembic 0050 · `metadata_stats.py` · payload `evidence` ·
      프롬프트 Evidence-first · thin 재정의 · 배선 확인: `COMPOSE_PROJECT_NAME=repo make test`
      FAILED 0 · ruff 통과
- [ ] `T2 합성·소비` — 산출물: `TBD`(ITEM-07·08·09) · 배선 확인: `TBD` — 본 cycle 범위 밖(ROADMAP)
- [ ] `T3 신뢰·계획` — 산출물: `TBD`(ITEM-10·11) · 배선 확인: `TBD` — 본 cycle 범위 밖(ROADMAP)

**주장 affordance 실측 (G3)**: 본 cycle 은 사용자 대면 UI 를 추가하지 않는다. 콘솔에 새로 노출되는
것은 설정 4 knob 뿐이며, 이들은 `_PERF_SPECS` 등록 → `serialize_registry` 노출을 테스트로 단정했고
(`test_worker_parallelism.py` PERF_KEYS), 각 knob 은 실제 게이트를 갖는다(ADR-0025-06 — 게이트 없는
knob 을 노출하지 않는다): ENABLED→`enabled()`, MAX_STAGE·DAY_MAX_STAGE→`stage_ceiling()`,
REFRESH_HOURS→`plan_stage()`. 분석문 품질 개선 주장은 배포 후 전/후 대조로 실측한다(TEST.md §4).

**경계변수 양측 검증 (G4)**:
- `AGENT_NODE_ANALYSIS_THIN_CHARS`(20) → 20자 미만("짧음")=thin / 계약 길이 문장(28자)=비-thin
- `_THIN_MIN_FILLED`(2) → 충족 1개=thin / 2개=비-thin (Table 의 role 포함 경로도 양측 검증)
- `AGENT_METADATA_STATS_REFRESH_HOURS`(24) → 1시간 경과=수집 안 함 / 30시간 경과=1단계 승격
- Stage 상한 → 상한 미만=승격 / 상한 도달=같은 Stage 재수집(초과 없음)
- 시간창 → 주간(14시)=상한 1 / 야간(23시)=상한 3, 그리고 판정이 UTC 가 아닌 로컬 시각을 쓰는지 단정

## 4. Notes
- 이 feature 의 코드는 `feature-0002-agent-core` 에 거주한다(워커 실행 단위). 문서만 본 unit 에
  귀속시킨다 — feature-0025 와 동일한 배치.
- 증거를 `semantic_cluster` RC4 시그니처에 넣지 않는다. 넣으면 전량 재임베딩·재클러스터가 유발된다.
