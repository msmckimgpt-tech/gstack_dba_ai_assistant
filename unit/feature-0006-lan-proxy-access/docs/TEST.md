---
doc_type: TEST
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- Caddy 설정이 새 feature 경로에서 마운트되는지 확인
- 인증서와 Caddy 상태 파일이 `../../../../artifacts`에 생성되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 caddy 서비스가 `feature-0006-lan-proxy-access/src/caddy/Caddyfile`을 사용한다
- TEST-0002: `Makefile`의 TLS 인증서 생성 경로가 `../../../../artifacts/certs`를 사용한다
- TEST-0003: 엄격한 네트워크 운영 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 네트워크 시나리오는 후속 작성 예정
