---
doc_type: FUNCTION
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
Caddy TLS 프록시 설정과 Windows 포트 프록시 스크립트를 관리한다.

## 2. Goal
- REQ-0001: LAN/TLS 관련 운영 자산을 기능 단위 구조로 이관한다.
- REQ-0002: 인증서와 상태 파일을 버전관리 밖으로 분리한다.

## 3. In Scope
- `src/caddy/Caddyfile`
- `src/windows/*`
- LAN/TLS 운영 문서

## 4. Out of Scope
- 인증서 실제 파일
- Web UI 앱 자체
- 엄격한 네트워크 운영 시나리오

## 5. Inputs
- `WEB_*` 환경값
- `ENABLE_WEB_TLS_PROXY`
- Windows 포트 프록시 운영 절차

## 6. Outputs
- Caddy 프록시 설정
- Windows 운영 스크립트
- TLS 관련 문서

## 7. Main Flow
1. 루트 compose가 feature 경로의 Caddyfile을 마운트한다.
2. 루트 Makefile이 인증서 디렉토리를 `../../../../artifacts/certs` 아래 준비한다.
3. 운영자는 Windows 스크립트로 LAN 포트프록시를 설정한다.

## 8. Edge Cases
- 인증서 부재
- `WEB_PUBLIC_HOST` 미설정
- Windows 방화벽/포트프록시 실패

## 9. Error Handling
- 인증서 부재는 `make web-tls-cert`로 보완한다.
- 프록시 실패는 운영 스크립트와 Caddy 로그로 점검한다.

## 10. Dependencies
### 내부 기능 의존성
- feature-0001-platform-runtime

### 외부 의존성
- Caddy
- Windows `netsh` / Scheduled Task

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: Caddy와 Windows 스크립트가 feature 경로로 이관되어 있다.
- AC-0002: 루트 compose가 새 Caddy 경로를 사용한다.
- AC-0003: 인증서와 Caddy 상태 파일은 `../../../../artifacts`에만 저장된다.

## 12. Observability
- Caddy 로그: `docker compose logs caddy`
- 인증서 위치: `../../../../artifacts/certs`

## 13. Pre-approved Changes
- 비파괴적 운영 자산 재배치와 경로 수정
