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
- TEST-0004 (TASK-0006 / TASK-0087, **Major** §12.3): Caddyfile 의 `reverse_proxy web:8000` 블록이 `header_up X-Forwarded-For {client_ip}` directive 를 명시한다. 검증:
  - **A1 (syntax)**: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` 가 exit 0 + `{client_ip}` placeholder 인식.
  - **A2 (live header replace)**: Caddy 컨테이너 가동 + 외부 클라이언트가 `curl -H 'X-Forwarded-For: 1.2.3.4' https://<WEB_PUBLIC_HOST>/api/session` → web 측 (`_get_client_ip`) 가 `1.2.3.4` 가 아닌 Caddy container IP (예: 172.18.0.x) 를 반환. live 검증 사용자 위임.

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 네트워크 시나리오는 후속 작성 예정
- 2026-05-21 (TASK-0006 / TASK-0087): Caddyfile static syntax 검증을 사용자 docker 환경에서 진행 권장 — `caddy validate` PASS 후 cycle-finalize.
