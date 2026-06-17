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
- REQ-0283 (TASK-0296, **Major** §12.3 — 사내 테스터 제한 배포): 브라우저 "안전하지
  않은 연결" 경고의 근본 원인(self-signed 인증서, issuer==subject, CA 체인 없음)을
  제거한다. 사내 자체 Root CA 로 leaf 인증서를 서명하고, Root CA(`rootCA.pem`)를
  테스터 PC 신뢰 저장소에 1회 설치하면 경고 없이 신뢰된 HTTPS 가 표시된다.
  `.company.local` 내부 도메인이라 공인 CA(Let's Encrypt) 발급이 불가능한 제약에
  대한 표준 해법. Root CA 는 멱등 재사용(테스터 재설치 불필요), leaf 만 갱신된다.

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
- AC-0004 (REQ-20260520-0002 / TASK-0006 = TASK-0087 in feature-0003, **Major** §12.3): `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `https://{$WEB_PUBLIC_HOST}, :443` 블록 안의 `reverse_proxy web:8000` 가 `header_up X-Forwarded-For {client_ip}` directive 를 포함한다. Caddy 가 클라이언트로부터 받은 임의 `X-Forwarded-For` 헤더 값을 무시하고 본인이 본 TCP peer IP (Caddy v2 `{client_ip}` placeholder) 로 덮어써서 web upstream 에 전달. 이로써 web 의 `_get_client_ip()` 가 보는 `X-Forwarded-For` 는 항상 단일 hop 정규화 값 — multi-hop chain 또는 클라이언트 spoof 가 audit 표면 (`WebAuditEvents.IpAddr`, `WebAuthSessions.RemoteAddr`) 에 도달하지 않는다. feature-0003 의 [`_get_client_ip()` 조건부 trust](../../feature-0003-agent-web-ui/docs/FUNCTION.md) (AC-0205~0207) 와 dual ownership 으로 정합.

- AC-0549 (REQ-0283 / TASK-0296): `bin/tls-internal-ca.sh` 가 사내 Root CA(`artifacts/certs/rootCA.pem` + `rootCA-key.pem` 0600)를 생성하고, 그것으로 서명한 leaf 인증서(`artifacts/certs/<host>/fullchain.pem` = leaf + Root CA, `privkey.pem` 0600)를 발급한다. 출력 경로는 `.env` 의 `WEB_TLS_CERT_FILE` / `WEB_TLS_KEY_FILE` 와 정합한다.
- AC-0550 (REQ-0283): leaf 인증서는 self-signed 가 아니다 — `issuer (CN=mysql-ai Internal Root CA) != subject (CN=<host>)`. `openssl verify -CAfile rootCA.pem fullchain.pem` 가 `OK`.
- AC-0551 (REQ-0283): leaf SAN 은 `.env` 의 `WEB_PUBLIC_HOST` + `WEB_ALLOWED_HOSTS` 의 DNS/IP(docker 내부 서비스명 `web` 제외)를 포함하고, `extendedKeyUsage=serverAuth`(Apple/macOS 요건) + `basicConstraints=critical,CA:FALSE` 를 갖는다.
- AC-0552 (REQ-0283): Root CA 는 멱등 — 재실행 시 기존 Root CA 를 재사용하고 leaf 만 재발급한다(`--force-ca` 명시 시에만 Root CA 재생성). leaf 기본 유효기간 825일(Apple 상한), Root CA 10년. 따라서 leaf 갱신은 테스터 재설치 없이 transparent.
- AC-0553 (REQ-0283): 라이브 web TLS 엔드포인트(`https://<host>:18080`)가 Root CA 로 서명된 leaf 를 서빙하고, Root CA 를 신뢰하는 클라이언트의 체인 검증이 통과한다(`Verify return code: 0`). 테스터 신뢰 설치 절차는 `src/TESTER_TLS_TRUST.md`.

## 12. Observability
- Caddy 로그: `docker compose logs caddy`
- 인증서 위치: `../../../../artifacts/certs`
- 인증서 발급/갱신: `bash bin/tls-internal-ca.sh` (서버) → `sudo docker compose up -d --no-deps web` (반영)
- 라이브 체인 검증: `openssl s_client -connect 127.0.0.1:18080 -CAfile artifacts/certs/rootCA.pem` → `Verify return code: 0`

## 13. Pre-approved Changes
- 비파괴적 운영 자산 재배치와 경로 수정
