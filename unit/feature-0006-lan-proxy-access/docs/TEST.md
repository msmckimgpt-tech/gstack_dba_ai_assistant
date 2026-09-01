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
- 2026-06-17 (TASK-20260617T083954-ai-claude-trust-bundle):
  - Environment: Linux (openssl/curl/one-off caddy). Run: `caddy validate`=Valid; one-off 테스트 caddy(:8080/:8443) → `http://…/trust/`·`install-trust-windows.bat`·`rootCA.crt`=200, bare `/trust`→301 `/trust/`, 그외 HTTP→HTTPS 301, 앱 `:443`=200. 임베드 base64 디코드 지문=실제 Root CA 일치(win .bat·mac .command). placeholder 잔존 0.
  - Environment: Windows-browser (PB-0008). **사유 명시(미수행)**: `/trust/` 는 inline CSS + 단순 OS감지 JS 의 **정적 다운로드 페이지**로 앱 로직/동적 상태 표면 없음. server-side(HTTP 200 + 링크/지문 정확성) 검증으로 충족. 실제 설치(`certutil`/`security`)는 Windows/macOS 클라이언트 권한 동작이라 CI 브리지 불가 — 운영자/테스터 1회 수동 확인 영역. 시각 회귀 우려 낮음(단일 페이지). 후속 운영 검증 시 실제 브라우저 확인 권장.
  - 사후 PB-0008(실 Windows Chrome, win-browser.py): `http://112.185.196.20/trust/`=200 렌더(지문박스·Win/mac/crt 버튼·OS감지 mac카드 숨김), 앱 `https://112.185.196.20/`=200 로그인 렌더. 증거 `artifacts/pb0008-trust/{trust-page-ip,app-login-ip}.png`. (호스트명은 Windows hosts admin 부재로 IP 검증.)
- 2026-06-17 (TASK-20260617T083954-ai-claude-bat-encoding-fix): Environment: Windows cmd.exe (실측). 깨진 .bat 재현(`echo`→`cho`·base64 명령실행) 확인 → ASCII+CRLF+no-chcp 수정본을 neuter(자가상승+certutil 제거) 후 cmd.exe 실행: echo/지문표시/base64 디코드/지문검증 전 구간 정상, `ACTUAL==FP_HEX` 통과(이전 잠복 mismatch 해소), `[OK]` 도달. `file`=ASCII+CRLF 확인. `.command` 는 `base64 -D`(macOS 전용)라 Linux 단위실행 불가 — 지문 로직 openssl 결정적. 실 certutil/security 설치는 관리자 환경 1회 확인 권장.

## Run — TASK-20260901T103000-ai-claude-corp-cert-expiry-monitor (2026-09-01)

Environment: WSL Ubuntu (openssl 3.x) · 라이브 엣지 `112.185.196.20`
> UI 표면 없음(운영 스크립트) — Windows-browser 시각검증 대상 아님.

**동작 실측 — 생성한 cert 로 경계를 넘겨 본다** (텍스트 검사가 아니라 실행 결과):

| 케이스 | 기대 | 실측 |
|---|---|---|
| leaf 100일 | exit 0 (정상) | **0** |
| leaf 20일 | exit 1 (WARN, 30일 임계) | **1** |
| leaf 3일 | exit 2 (CRITICAL, 7일 임계) | **2** |
| leaf 여유 + **rootCA 10일** | exit 2 (CA 축 단독 발동) | **2**, 메시지가 `rootCA` 지목 |
| cert 파일 부재 | 비-0 (fail-open 금지) | **비-0** |
| `--leaf-warn 5` (게이트 14일보다 좁음) | exit 3 거절 | **3**, 사유에 «게이트» 명시 |

**실환경 1회**: `--live 112.185.196.20` → leaf(2028-09-19)·rootCA(2036-06-14)·live 3축 OK, exit 0.

**드리프트 잠금**: `deploy-web.sh` 의 `checkend 1209600`(14일)과 감시의 `DEPLOY_GATE_DAYS=14` 가
어긋나면 FAIL 하는 단언 포함 — 두 파일이 조용히 갈라지는 것을 막는 유일한 연결.

**자가적용 검증**: `unit/feature-0006-lan-proxy-access/tests` 를 Makefile·ci.yml 양쪽에 등재했고,
직전 cycle 의 parity 테스트가 이를 검증했다. **한쪽만 등재한 사본에서 그 테스트가 FAIL 함**도
별도 실증(가드가 실제로 무언가를 잡는다는 근거).

결과: 신규 9건 PASS · `bash -n` 2개 파일 OK · cron 은 `--print` 확인만(**crontab 무변경**).
