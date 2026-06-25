---
doc_type: FUNCTION
feature_id: feature-xxxx-template
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
이 기능이 무엇을 하는지 한 문단으로 설명한다.

## 2. Goal
- REQ-001:
- REQ-002:

## 3. In Scope
- 포함되는 동작
- 포함되는 인터페이스
- 포함되는 데이터 처리

## 4. Out of Scope
- 이번 기능에서 다루지 않는 항목
- 후속 기능으로 미루는 항목

## 5. Inputs
- 입력값
- 이벤트
- 외부 호출
- 설정값

## 6. Outputs
- 반환값
- 상태 변경
- 로그/알림/저장 결과

## 7. Main Flow
1. 입력 수신
2. 검증
3. 처리
4. 결과 반환 또는 상태 반영

## 8. Edge Cases
- 누락 입력
- 잘못된 상태
- 중복 요청
- 외부 시스템 장애

## 9. Error Handling
- 사용자에게 보일 오류
- 재시도 가능 여부
- 롤백 필요 여부

## 10. Dependencies
### 내부 기능 의존성
<!-- 이 기능이 의존하는 다른 기능을 feature-id로 참조한다 -->
- 없음

### 외부 의존성
- 외부 API
- 저장소/큐/캐시 등

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
<!-- spec 앵커 ID 형식: timestamp+slug `<PREFIX>-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (REQ/AC/ADR/TEST 공통).
     AC 는 부모 REQ 의 timestamp+slug 를 공유하고, 한 REQ 가 다수 AC 면 `-<n>`(1-based) 으로 구분한다
     (정본 AGENTS.md §6·§13.1, ADR-20260625T023049-spec-anchor-timestamp-id). 병렬 cycle 머지 시
     순번 충돌을 제거한다. 예: REQ `REQ-20260625-login` → `AC-20260625T185057-login-1`, `-2`.
     기존 순번 `AC-0001` 도 유효(fallback·소급 재번호 없음). -->
- AC-<YYYYMMDDTHHMMSS>-<slug>-1:
- AC-<YYYYMMDDTHHMMSS>-<slug>-2:
- AC-<YYYYMMDDTHHMMSS>-<slug>-3:

## 12. Observability
- 어떤 로그를 남기는지
- 어떤 메트릭을 확인하는지
- 어떤 경보가 필요한지

## 13. Pre-approved Changes
<!-- 사람이 이 기능에서 사전 승인하는 변경 범위를 기입한다 (AGENTS.md §11.2 참조) -->
- 없음
