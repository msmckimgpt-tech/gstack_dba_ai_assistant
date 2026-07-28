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
feature_id: feature-0027-perf-latency-p0
linked_unit: unit/feature-0027-perf-latency-p0
sources:
  - ../../unit/feature-0027-perf-latency-p0/docs/FUNCTION.md
---

# Feature — P0 성능 개선 1차 (답변 지연·자원 미스매치)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0027-perf-latency-p0/docs/FUNCTION|unit/feature-0027-perf-latency-p0/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0026 병목 지도 기반 P0 개선 — post-answer 큐레이션(topic/용어/ENUM LLM 3건)을 KV
terminal **이후**로 이동(답변 체감 -25~35s, 결과물·scope 귀속 불변), grounding RO 연결 3→1,
MySQL 버퍼풀 128MB→1G, Caddy gzip+immutable static. 품질 영향 축(레드팀·thinking)은 불변.

## 2. 상태

- **active** (2026-07-28 구현 — 검증·배포 진행). 코드 거주: feature-0002(agent_core·ask)·
  feature-0001(mysql cnf)·feature-0006(Caddyfile)·bin(perf-snapshot 캡션).

## 3. 책임 경계

- **함:** 큐레이션 시점 이동(터미널 후·datasource ContextVar 명시 캡처/해제)·grounding 공유
  RO 연결·버퍼풀 상향·엣지 압축/캐시.
- **안 함(사용자 결정/후속):** red-team 게이팅·thinking 예산(품질 트레이드오프), web 풀링·
  ask_result to_thread·권한 캐시(web-perf slice), sync churn 감쇠.

## 4. 관련 정본

- [[../../unit/feature-0027-perf-latency-p0/docs/FUNCTION|FUNCTION.md]] ·
  [[../../unit/feature-0027-perf-latency-p0/docs/ANCHOR|ANCHOR.md]] ·
  [[../../unit/feature-0027-perf-latency-p0/docs/REVIEW|REVIEW.md]]

## 5. 관련 노트

- [[feature-0026-perf-observability]] — 측정 근거(S9 격차 ~34s·버퍼풀 히트율·전송량)와
  before/after 수단(perf-snapshot).

## 7. 변경 이력 (이 카드)

- 2026-07-28: 신규 생성.
