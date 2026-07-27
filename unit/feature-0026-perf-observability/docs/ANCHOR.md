---
doc_type: ANCHOR
feature_id: feature-0026-perf-observability
created_at: 2026-07-27T09:10:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0026-perf-observability

## §1. 외부 관점 요약
- "왜 측정 코드가 제품 코드에 섞여 있나?" — 이 서비스는 dev/staging 분리가 없는 라이브
  단일 환경이라, 병목의 실체는 라이브 계측으로만 확정된다. 외부 APM 도입 대신 최소
  침습 in-process 계측을 택했다.
- "미들웨어가 오히려 성능을 해치지 않나?" — 순수 ASGI + fixed bucket + fail-open 으로
  요청당 오버헤드를 마이크로초대에 묶는다. 측정이 병목이 되면 본말전도라는 것이 설계 제1 제약.
- "왜 개선(버퍼풀·풀링·gzip)을 같이 안 하나?" — 측정 없는 개선은 §16.3 proxy≠ground-truth
  위반. 본 feature 는 측정 축만 깔고, 개선은 측정치 기반 후속 cycle 로 분리한다.

## §2. 대안 분기
- **Prometheus + Grafana 스택** (SRE 페르소나): 표준적이나 컨테이너 3+개·저장소·인증 표면이
  늘고 사내 LAN 단일호스트 규모 대비 과설계. → 기각, in-process 집계 + 스냅샷 CLI.
- **OpenTelemetry auto-instrumentation** (플랫폼 엔지니어 페르소나): FastAPI/psycopg 자동
  계측이 넓지만 의존성·오버헤드·버전 결합이 크고 fail-open 보장이 불투명. → 기각.
- **로그 파싱만 (계측 무추가)** (보수 운영자 페르소나): uvicorn access log + Caddy log 만으로
  지연 축은 얻지만 요청당 DB 커넥션 수·파이프라인 단계 분해는 불가. → 부분 채택 (Caddy log 는 M6).

## §3. 가정된 사용 시나리오
운영자(또는 후속 AI cycle)가 "답변이 느리다"는 보고를 받으면: ① `bin/perf-snapshot.sh` 실행
→ ② snapshot.md 에서 답변 E2E p95 · task 별 LLM p95 · redteam_ms · post_answer_ms ·
HTTP route p95 · pgbouncer 풀 사용률 · MySQL buffer pool 히트율을 한 번에 대조 → ③ 어느
축(LLM/리뷰/DB/폴링/edge)이 지배적인지 수치로 확정 → ④ 해당 축의 개선 cycle 을 연다.
개선 배포 후 같은 스냅샷을 다시 떠 before/after 를 비교한다 (회귀 감지).

## §4. 외부 검증 로그
<!-- append-only. source: human:<name> 만 허용. -->
