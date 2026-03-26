---
doc_type: TEST
feature_id: feature-0002-agent-core
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 코어 소스가 새 위치에서 빌드되는지 확인
- `make ask`가 새 feature Dockerfile을 통해 실행되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 agent 계열 build가 `feature-0002-agent-core/src/Dockerfile`을 사용한다
- TEST-0002: `Makefile`의 `make ask`가 동일 인터페이스를 유지한다
- TEST-0003: 엄격한 질의 정확도 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 질의 시나리오는 후속 작성 예정
