---
doc_type: TEST
feature_id: feature-0001-platform-runtime
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 설정 파일 경로가 새 feature 구조를 가리키는지 확인
- 런타임 산출물이 `../../../../artifacts`에 생성되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`이 `src/mysql/conf.d`를 참조한다
- TEST-0002: `Makefile`이 `../../../../artifacts/mysql-data`와 `../../../../artifacts/mysql-backup`를 사용한다
- TEST-0003: 엄격한 운영 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 운영 시나리오는 후속 작성 예정
