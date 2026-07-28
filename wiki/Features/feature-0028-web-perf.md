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
feature_id: feature-0028-web-perf
linked_unit: unit/feature-0028-web-perf
sources:
  - ../../unit/feature-0028-web-perf/docs/FUNCTION.md
---

# Feature — web 계층 성능 (long-poll·연결·인증 오버헤드)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0028-web-perf/docs/FUNCTION|unit/feature-0028-web-perf/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0026 이 지목한 web 병목 제거 — `/api/ask_result` long-poll 을 워커 스레드로 옮겨
**이벤트 루프 정지 제거**, 스냅샷 PG 연결 **4~5→1**(단일 왕복 번들), 권한 카탈로그 TTL 캐시 +
세션 LastSeenAt throttle 로 인증 왕복 완화, web MySQL 연결 풀 opt-in. 응답·인가 불변.

## 2. 상태

- **active** (2026-07-28). 코드 거주: feature-0003(conversations·_conv_store·web_context·
  admin_products·app rebind).

## 3. 책임 경계

- **함:** 폴 루프 스레드 위임·스냅샷 번들·카탈로그 캐시/무효화·세션 touch throttle·풀 토글.
- **안 함:** 폴링→SSE 전환, 사이드바 배지 엔드포인트, /api/progress 접근검사 병합,
  uvicorn --workers (후속).

## 4. 관련 정본

- [[../../unit/feature-0028-web-perf/docs/FUNCTION|FUNCTION.md]] ·
  [[../../unit/feature-0028-web-perf/docs/ANCHOR|ANCHOR.md]] ·
  [[../../unit/feature-0028-web-perf/docs/REVIEW|REVIEW.md]]

## 5. 관련 노트

- [[feature-0026-perf-observability]] (측정 근거·`db_per_req` 전후 수단) ·
  [[feature-0027-perf-latency-p0]] (같은 병목 지도의 답변·자원 축).

## 7. 변경 이력 (이 카드)

- 2026-07-28: 신규 생성.
