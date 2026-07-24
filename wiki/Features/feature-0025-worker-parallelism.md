---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: active
ai_generated: true
feature_id: feature-0025-worker-parallelism
linked_unit: unit/feature-0025-worker-parallelism
sources:
  - ../../unit/feature-0025-worker-parallelism/docs/FUNCTION.md
---

# Feature — 워커 성능·병렬 처리 설정

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0025-worker-parallelism/docs/FUNCTION|unit/feature-0025-worker-parallelism/docs/FUNCTION.md]].

## 1. 한 줄 요약

백그라운드 워커(그래프 노드 분석·cluster_label)와 사용자 답변 처리의 **병렬도·처리 주기·배치 크기**를
관리 콘솔 `시스템 > 설정 > 성능·병렬 처리`에서 조절한다(신규 동시성 기본 1=현행 직렬 byte-동치, opt-in).

## 2. 상태

- **active** (2026-07-24 구현·단위/회귀 검증·§18.8 리뷰 완료, 배포 후 PB-0008 잔여).
- 코드 거주: feature-0002(워커 루프·runtime_settings 소비)·feature-0003(admin UI)·shared(레지스트리)·docker-compose(인프라).

## 3. 책임 경계

- **함:** runtime_settings `performance` 그룹(10 knob) 등록·전파, 워커 3워크로드 LLM-병렬/DB-직렬 배선,
  페이싱/배치 live 소비 전환, pgbouncer/PG 커넥션 여력 상향, admin '성능·병렬' 서브탭.
- **안 함(이연):** docker replicas 자동스케일, run_agent 내부 tool 병렬, 전역 LLM 세마포어 (FUNCTION.md 비목표).

## 4. 관련 정본

- 기능 계약: [[../../unit/feature-0025-worker-parallelism/docs/FUNCTION|FUNCTION.md]] (knob 매핑 표·설계 원칙)
- 결정: [[../../unit/feature-0025-worker-parallelism/docs/DECISIONS|DECISIONS.md]] (ADR-0025-01~04)
- 방향 앵커: [[../../unit/feature-0025-worker-parallelism/docs/ANCHOR|ANCHOR.md]]
- 리뷰: [[../../unit/feature-0025-worker-parallelism/docs/REVIEW|REVIEW.md]] (§18.8 2-렌즈 패널)

## 5. 관련 노트

- feature-0018 runtime-settings(재사용한 레지스트리·스냅샷 인프라).
- feature-0016 metadata-graph(노드 분석·cluster_label 워크로드), feature-0002 agent-core(ask/insight 워커).
- 2026-07-14 §82 flock 사건(pgbouncer 풀 소진 — 병렬도 안전 설계의 근거).

## 6. Open questions / 미해결

- 병렬 활성 시 pgbouncer 풀·Bedrock 429 부하 라이브 실증(배포 후 PB-0008 + 운영 현황 관측).
- run_agent run_id 전역→인자 전환(정밀 토큰 귀속), docker replicas 자동스케일.

## 7. 변경 이력 (이 카드)

- 2026-07-24: 신규 생성 (feature-0025 구현 동반).
