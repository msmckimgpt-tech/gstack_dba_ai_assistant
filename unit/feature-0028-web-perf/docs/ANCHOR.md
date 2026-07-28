---
doc_type: ANCHOR
feature_id: feature-0028-web-perf
created_at: 2026-07-28T04:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0028-web-perf

## §1. 외부 관점 요약
- "long-poll 을 왜 그대로 두고 스레드로만 옮겼나?" — SSE/NOTIFY 전환은 프런트·인증·프록시
  계약을 함께 바꾸는 별도 initiative다. 이번엔 **같은 프로토콜에서 이벤트 루프를 막지 않게**
  만드는 것이 목표 — 위험 대비 효과가 가장 큰 지점.
- "캐시가 권한을 낡게 만들지 않나?" — 최초안은 "카탈로그는 집행과 무관" 이라 주장했으나
  **코드로 반증**됐다(§18.8 B-3/qa B3): 카탈로그 codes 는 `_decorate_account_rows` →
  `_apply_permission_overrides` 의 **키 우주**라 stale 이면 신규 코드가 effective 맵에서
  탈락한다(fail-closed 지만 replica 별 비결정적 403). 그래서 **집행 경로는 캐시를 쓰지
  않도록**(use_cache=False) 바꿨다 — 인가 정확성은 종전과 동일. 캐시는 admin 조회 경로에만.
- "LastSeenAt 을 늦게 쓰면 감사에 구멍인가?" — 감사 이벤트(§9)는 별 테이블이고, LastSeenAt 은
  세션 활동 표시용이다. IP 변경 기록이 최대 throttle 간격만큼 늦어질 뿐 누락되지 않는다.

## §2. 대안 분기
- **SSE/LISTEN-NOTIFY 전환** (아키텍트 페르소나): 폴링 자체를 없애 가장 근본적이나 프런트
  재작성·프록시 버퍼링·재접속 시맨틱까지 동반 — 본 slice 범위 초과, 후속 initiative 로.
- **전역 MySQL 풀 기본 ON** (성능 우선 페르소나): 효과는 크지만 web 전 요청 blast radius —
  opt-in 토글로 두고 라이브 관측(db_per_req) 후 단계 활성이 안전.
- **집행 경로 제외 + 관리 경로만 캐시** (보안 페르소나, §18.8 후 **채택**): 캐시 이득은
  줄지만 인가 정확성을 신선도와 거래하지 않는다. B 의 핫패스 이득은 세션 UPDATE 제거로 한정.

## §3. 가정된 사용 시나리오
답변 대기 중인 사용자가 있어도 다른 사용자의 화면 전환·목록 로딩이 멈추지 않는다(이벤트
루프 무정지). 운영자는 `/api/admin/perf/http` 의 `db_per_req` 로 `/api/ask_result`·
`/api/progress` 의 요청당 연결 수가 줄어든 것을 배포 전후로 직접 확인한다.

## §4. 외부 검증 로그
<!-- append-only. source: human:<name> 만 허용. -->
