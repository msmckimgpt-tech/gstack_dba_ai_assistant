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
- 2026-06-17 (TASK-0296): leaf 체인 `openssl verify` OK + 라이브 web `:18080` `Verify return code: 0` + HTTP 200.
- 2026-06-17 (TASK-0297): `caddy validate`=Valid + one-off 테스트 caddy(dbnet, :8443) 런타임 `/healthz`·`/`=200(502 해소). 라이브 caddy `:443`=200·`Verify 0`, web `:18080`=200, HTTP→HTTPS 301.
- 2026-06-17 (TASK-0298):
  - Environment: Linux (openssl/curl/one-off caddy). Run: `caddy validate`=Valid; one-off 테스트 caddy(:8080/:8443) → `http://…/trust/`·`install-trust-windows.bat`·`rootCA.crt`=200, bare `/trust`→301 `/trust/`, 그외 HTTP→HTTPS 301, 앱 `:443`=200. 임베드 base64 디코드 지문=실제 Root CA 일치(win .bat·mac .command). placeholder 잔존 0.
  - Environment: Windows-browser (PB-0008). **사유 명시(미수행)**: `/trust/` 는 inline CSS + 단순 OS감지 JS 의 **정적 다운로드 페이지**로 앱 로직/동적 상태 표면 없음. server-side(HTTP 200 + 링크/지문 정확성) 검증으로 충족. 실제 설치(`certutil`/`security`)는 Windows/macOS 클라이언트 권한 동작이라 CI 브리지 불가 — 운영자/테스터 1회 수동 확인 영역. 시각 회귀 우려 낮음(단일 페이지). 후속 운영 검증 시 실제 브라우저 확인 권장.
