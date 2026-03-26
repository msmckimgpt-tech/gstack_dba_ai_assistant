---
doc_type: TEST
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- Web UI 앱이 새 feature 경로에서 이미지에 포함되는지 확인
- `make web`가 동일 인터페이스로 동작하는지 확인

## 2. Test Cases
- TEST-0001: agent Dockerfile이 `feature-0003-agent-web-ui/src`를 `/app/web`로 복사한다
- TEST-0002: `docker-compose.yml`의 `web` 서비스가 새 이미지 경로를 사용한다
- TEST-0003: 엄격한 사용자 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 Web UI 시나리오는 후속 작성 예정
