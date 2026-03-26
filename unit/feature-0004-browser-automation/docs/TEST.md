---
doc_type: TEST
feature_id: feature-0004-browser-automation
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 브라우저 서비스가 새 경로에서 빌드되는지 확인
- `make browser-*` 인터페이스가 유지되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 browser build가 `feature-0004-browser-automation/src/Dockerfile`을 사용한다
- TEST-0002: `Makefile`의 `browser-*` 타깃이 기존 이름을 유지한다
- TEST-0003: 엄격한 브라우저 업무 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 브라우저 시나리오는 후속 작성 예정
