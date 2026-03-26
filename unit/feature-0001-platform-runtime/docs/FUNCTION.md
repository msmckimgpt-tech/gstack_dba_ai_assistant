---
doc_type: FUNCTION
feature_id: feature-0001-platform-runtime
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
템플릿 사본에서 MySQL/DAB 운영 자산과 버전관리 대상 SQL 유틸리티를 관리한다.

## 2. Goal
- REQ-0001: 루트 중심 운영 자산을 기능 단위 구조로 이관한다.
- REQ-0002: 런타임 산출물과 버전관리 자산의 경계를 분리한다.

## 3. In Scope
- MySQL `conf.d` 설정 파일
- DAB 설정 파일
- 버전관리 대상 SQL 유틸리티 스크립트
- `../../../../artifacts` 경계에 맞는 운영 문서화

## 4. Out of Scope
- 실제 MySQL 데이터 파일
- 세션, 로그, 인증서 파일 내용
- 도메인 검증 시나리오 작성

## 5. Inputs
- `../../../.env`
- `docker-compose.yml`
- `Makefile`

## 6. Outputs
- MySQL 컨테이너에 마운트되는 설정 파일
- 운영자가 재사용할 SQL 점검 스크립트
- `../../../../artifacts` 기준 경로 계약

## 7. Main Flow
1. 루트 실행 파일이 feature 경로의 설정 자산을 참조한다.
2. `make start`가 `../../../../artifacts` 디렉토리를 준비한다.
3. MySQL이 새 경로 기준으로 기동한다.

## 8. Edge Cases
- `../../../../artifacts/mysql-data`가 없으면 Makefile이 먼저 생성한다.
- 인증서 디렉토리가 없으면 `make web-tls-cert`가 생성한다.

## 9. Error Handling
- 경로 누락 시 Makefile이 생성 후 재시도한다.
- MySQL 기동 실패는 compose 상태와 로그로 확인한다.

## 10. Dependencies
### 내부 기능 의존성
- 없음

### 외부 의존성
- Docker Compose
- MySQL 8.0 이미지

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: 설정 파일이 `src/mysql/conf.d`와 `src/dab` 아래로 이관되어 있다.
- AC-0002: SQL 유틸리티가 `src/sql` 아래로 이관되어 있다.
- AC-0003: 루트 실행 파일이 이 기능 경로만 참조한다.

## 12. Observability
- 로그는 `../../../../artifacts/shared/logs`
- 백업은 `../../../../artifacts/mysql-backup`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 설정 파일 이관
