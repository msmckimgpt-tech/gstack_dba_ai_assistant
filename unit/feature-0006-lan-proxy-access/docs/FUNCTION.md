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
- REQ-0284 (TASK-0297, **Major** §12.3 — caddy :443 정식 front door): caddy(`:443`)가
  반환하던 502 를 해소하고 포트 없는 `https://{$WEB_PUBLIC_HOST}` 를 정식 진입점으로 만든다.
  근본 원인 = `ENABLE_WEB_TLS=1` 이라 web 이 8000 에서 HTTPS 를 서빙하는데 caddy 가 평문
  `reverse_proxy web:8000` 로 붙어 프로토콜 불일치(502). caddy 를 HTTPS-upstream(사내 Root
  CA 검증)으로 전환하고, web 이 caddy 의 `X-Forwarded-For` 를 신뢰하도록 trusted proxy 를
  설정해 audit IP 정확도(SECURITY.md §9.7)를 보존한다. web 직접 TLS `:18080` 경로는 유지.
- REQ-0285 (TASK-20260617T083954-ai-claude-trust-bundle, **Major** §12.3 — 테스터 Root CA 원클릭 설치 번들): 테스터가 PC 마다
  인증서를 수동으로 옮기는 번거로움을 없앤다. web 서버가 `http://{$WEB_PUBLIC_HOST}/trust/`
  에서 OS별 단일 자가완결 설치 스크립트(인증서 임베드) + 다운로드 페이지를 제공해, 테스터는
  URL 접속 → 스크립트 실행(승인 1회) 로 끝낸다. (브라우저 방문만으로 신뢰 저장소에 자동 설치하는
  것은 OS/브라우저 보안 경계상 불가능 — 사용자 승인 필수.) Root CA 배포의 신뢰 부트스트랩 한계는
  SHA-256 지문 노출 + 스크립트 지문 재검증 + 운영자 out-of-band 지문 공유로 완화한다.
- REQ-0286 (TASK-20260617T083954-ai-claude-bat-encoding-fix, **Minor** §12.3 — 설치 스크립트 실행 버그 2종 수정): 라이브에서 Windows
  `.bat` 실행 시 `echo`→`cho`·base64 가 명령으로 실행되는 파싱 붕괴 + 지문 항상 불일치가 발생했다.
  ① **인코딩/줄바꿈**: `.bat` 가 LF + UTF-8 + `chcp 65001` → cmd.exe 가 코드페이지 전환 후 파일
  바이트 오프셋을 잃어 라인 파싱 붕괴. → ASCII 전용 + CRLF + `chcp` 제거(코드페이지 무관). ②
  **지문 비교 오류**: 스크립트가 PEM **파일** 해시(`Get-FileHash`/`shasum`)를 인증서 **DER** 지문
  (`openssl -fingerprint`)과 비교 → 항상 불일치. → 인증서 DER SHA-256(Windows X509Certificate2
  RawData, macOS `openssl x509 -fingerprint`)으로 통일.

- REQ-20260902-portproxy-idempotent-sync (TASK-20260902T113500-ai-claude-feature-0006-lan-proxy-access,
  **Major** §12.3 — 5분 주기 포트프록시 재설정이 라이브 연결을 끊는 문제 해소): Windows 예약작업
  `mysql_ai_web_portproxy_sync` 가 매 실행마다 조건 없이 `netsh interface portproxy delete` → `add`
  를 수행해, WSL IP 가 바뀌지 않은 평상시에도 **5분마다 80/443 의 기존 TCP 연결을 전부 끊었다**.
  짧은 요청(브라우저)은 재시도로 가려지지만 오래 유지되는 연결은 그대로 드러난다 — 개인 AI 브리지
  러너의 대기 호출(`wait_for_request`, 서버가 55초 보류)이 5분 주기로 `RemoteDisconnected` 를 맞고
  `conn.retry` WARN 을 남겼다. 스크립트를 **현재 매핑이 이미 원하는 값이면 아무것도 하지 않도록**
  (idempotent) 바꿔, 목적(WSL 재부팅 후 바뀐 IP 추종)은 유지하고 부작용만 제거한다.

## 3. In Scope
- `src/caddy/Caddyfile`
- `src/windows/*`
- `src/trust-bundle/*` (테스터 설치 번들 템플릿)
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
- AC-0554 (REQ-0284 / TASK-0297): `src/caddy/Caddyfile` 의 `:443` 블록 `reverse_proxy web:8000` 가 `transport http { tls; tls_trust_pool file /certs/rootCA.pem; tls_server_name {$WEB_PUBLIC_HOST} }` 를 포함한다. caddy 가 web(8000, HTTPS) 에 HTTPS 로 연결하고 사내 Root CA 로 leaf 를 검증한다. `caddy validate` = `Valid configuration`, 런타임 프록시 = HTTP 200(이전 502 해소). AC-0004 의 `header_up X-Forwarded-For {client_ip}` 등 XFF directive 는 보존된다.
- AC-0555 (REQ-0284): `.env` `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES=172.18.0.0/16`(caddy dbnet 서브넷). web 의 `_get_client_ip()` 가 caddy 의 `X-Forwarded-For` 를 신뢰해 `WebAuditEvents.IpAddr` / `WebAuthSessions.RemoteAddr` 가 caddy 컨테이너 IP 가 아닌 실 클라이언트 IP 를 기록한다(SECURITY.md §9.7 PIPA 품질). 외부/미신뢰 LAN 노출 시 서브넷 협소화 + web port 비공개 별 cycle.
- AC-0556 (REQ-0284): 라이브 `:443`(caddy) 과 `:18080`(web 직접) 양쪽이 Root CA 로 신뢰된 체인으로 HTTP 200 을 반환한다. 테스터는 포트 없는 `https://{$WEB_PUBLIC_HOST}` 또는 `:18080` 어느 쪽이든 경고 없이 접속한다.
- AC-0557 (REQ-0285 / TASK-20260617T083954-ai-claude-trust-bundle): `bin/trust-bundle.sh` 가 `artifacts/certs/rootCA.pem` 를 읽어 `src/trust-bundle/*.tmpl` placeholder(`__PUBLIC_HOST__`/`__ROOTCA_SHA256__`/`__ROOTCA_SHA256_HEX__`/`__ROOTCA_B64__`)를 주입, `artifacts/trust-bundle/{index.html, install-trust-windows.bat, install-trust-macos.command, rootCA.crt}` 를 조립한다. 임베드 base64 디코드 지문이 실제 Root CA 와 일치함을 자가검증(불일치 시 die). `tls-internal-ca.sh` 가 끝에서 자동 호출(인증서 갱신 시 번들 동반 갱신).
- AC-0558 (REQ-0285): `src/caddy/Caddyfile` 가 `/trust` → `/trust/` 리다이렉트 + `handle_path /trust/*`(`root /srv/trust`, `file_server`) 를 **HTTP `:80`** 블록(나머지는 HTTPS 리다이렉트) **및 HTTPS `:443`** 블록(나머지는 reverse_proxy) 양쪽에 둔다. compose 가 `../artifacts/trust-bundle:/srv/trust:ro` 를 마운트. HTTP 서빙 이유 = 테스터가 아직 Root CA 미설치(HTTPS 경고) 상태에서 경고 없이 번들을 받게 하기 위함.
- AC-0559 (REQ-0285): 설치 스크립트는 단일 자가완결 파일(Root CA PEM base64 임베드). Windows `.bat` = 자가-상승 + 지문 표시/재검증 + `certutil -addstore -f Root`. macOS `.command` = 지문 표시/재검증 + `sudo security add-trusted-cert -d -r trustRoot -k System.keychain`. 설치 전 임베드 인증서의 SHA-256 이 기대값과 불일치하면 중단.
- AC-0560 (REQ-0285): `http://{$WEB_PUBLIC_HOST}/trust/` 다운로드 페이지가 SHA-256 지문(out-of-band 대조 안내) + OS 감지 다운로드 + Firefox 자체 저장소 + hosts 안내를 제공한다.
- AC-0561 (REQ-0285): 라이브 `http://<host>/trust/`(평문, index/스크립트/`rootCA.crt`) = HTTP 200, bare `/trust` → 301 `/trust/`, 그 외 HTTP 경로 → HTTPS 301, 앱 `:443` reverse_proxy = 200 (번들 추가가 앱 라우팅 무회귀).
- AC-20260617T083954-ai-claude-bat-encoding-fix-01 (REQ-0286 / TASK-20260617T083954-ai-claude-bat-encoding-fix): `install-trust-windows.bat` 는 **ASCII 전용 + CRLF 줄바꿈 + `chcp` 없음**. `bin/trust-bundle.sh` 가 .bat 를 CRLF 로 출력하고 비-ASCII 바이트 검출 시 die. cmd.exe 가 라인 파싱 붕괴(`echo`→`cho`, base64 가 명령 실행) 없이 실행한다(실측: cmd.exe 로 echo/지문표시/base64 디코드/지문검증 전 구간 정상). `.command`/​`index.html` 은 LF 유지.
- AC-20260617T083954-ai-claude-bat-encoding-fix-02 (REQ-0286): 설치 스크립트의 지문 재검증은 인증서 **DER SHA-256**(= `openssl x509 -fingerprint -sha256`, 브라우저 표시 지문)을 비교한다 — PEM **파일** 해시가 아님. Windows = `X509Certificate2.RawData` 의 SHA-256, macOS = `openssl x509 -noout -fingerprint -sha256`. 정상 인증서에서 `ACTUAL == FP_HEX` 로 통과(이전엔 항상 불일치로 중단되던 잠복 버그 수정).

- AC-20260902T113500-portproxy-idempotent-1 (REQ-20260902-portproxy-idempotent-sync):
  `src/windows/sync_mysql_ai_web_portproxy.ps1` 는 실행 전에 `netsh interface portproxy show v4tov4`
  로 현재 매핑을 읽고, `listenaddress:listenport` → `connectaddress:connectport` 가 **이미 원하는
  값과 같으면 `delete`/`add` 를 호출하지 않는다**. 출력 JSON 의 `ports[].portproxy_action` 이
  `unchanged` 이고 `portproxy_changed` 가 `false` 다. 값이 다르거나 없으면 종전대로 재설정한다
  (`recreated` / `created`).
- AC-20260902T113500-portproxy-idempotent-2 (REQ-20260902-portproxy-idempotent-sync): 현재 매핑을
  **읽지 못하면 종전 동작(무조건 재설정)으로 폴백**한다 — `Get-PortProxyEntries` 가 `$null` 을
  돌려주고 `portproxy_state_known` 이 `false` 다. 빈 딕셔너리("등록된 것이 없다")와 `$null`("상태를
  모른다")을 구분한다. 안전한 실패 방향은 «불필요한 재설정»이지 «필요한 재설정 누락»이 아니다.
- AC-20260902T113500-portproxy-idempotent-3 (REQ-20260902-portproxy-idempotent-sync): 매핑 파싱은
  **로케일 무관**이다 — `netsh` 출력 헤더 문구(한국어 Windows 는 "수신 대기" 등)가 아니라 데이터
  행의 «IPv4 포트 IPv4 포트» 패턴만 정규식으로 뽑는다. 한국어 로케일 실호스트에서 4개 매핑
  (`112.185.196.20:443 → 172.26.154.233:443` 포함)이 정확히 파싱된다. 파일은 한글 주석을 담으므로
  **UTF-8 BOM** 을 갖는다 (`bridge_setup.ps1` 선례) — BOM 없이 PS 5.1 이 읽으면 한글 839자 중
  324자가 손실된다(실측).

- AC-20260902T124500-portproxy-idempotent-4 (REQ-20260902-portproxy-idempotent-sync, codex P2 반영):
  **legacy 포트 삭제에는 멱등 skip 을 적용하지 않는다** — 조건 없이 `delete` 를 시도하고, 성공한
  것만 `legacy_ports_deleted` 에 기록한다. 근거: legacy 포트에는 활성 연결이 없어 skip 의 이득이
  없고, netsh 가 허용하는 hostname 형태 매핑(`127.0.0.1 18080 localhost 18080`)은 IPv4 정규식에
  잡히지 않아 skip 하면 **영영 삭제되지 않는다**. 삭제 실패(대상 없음 포함)는 기록하지 않는다.
- AC-20260902T124500-portproxy-idempotent-5 (REQ-20260902-portproxy-idempotent-sync, codex P2 반영):
  `portproxy_changed` 는 public 포트 재설정 **또는** legacy 삭제 중 하나라도 있으면 `true` 다.
  둘 중 하나만 세면 `legacy_ports_deleted: [18080]` 과 `portproxy_changed: false` 가 동시에
  보고되어 필드 의미가 자기모순이 된다.
- **알려진 한계 (수용, codex P2-5)**: 상태 조회와 판정 사이에 다른 주체가 매핑을 바꾸면 이 실행은
  조회 시점 값으로 `unchanged` 를 판정한다(TOCTOU). netsh 에 원자적 비교-교체가 없어 창을 없앨 수
  없고, 이 스크립트 외에 portproxy 를 건드리는 주체가 없는 것이 전제다. **확률적 5분 창**과
  종전의 **확정적 5분 절단**을 맞바꾼 것이며, verify 단계 `Test-NetConnection` 결과가 JSON 에
  남아 사후 판별이 가능하다.

## 12. Observability
- Caddy 로그: `docker compose logs caddy`
- 인증서 위치: `../../../../artifacts/certs`
- 인증서 발급/갱신: `bash bin/tls-internal-ca.sh` (서버) → `sudo docker compose up -d --no-deps web` (반영)
- 라이브 체인 검증: `openssl s_client -connect 127.0.0.1:18080 -CAfile artifacts/certs/rootCA.pem` → `Verify return code: 0`
- caddy :443 검증: `caddy validate` + `curl --cacert rootCA.pem https://<host>/healthz` → 200
- caddy 설정 검증: `docker run --rm -v <Caddyfile>:/etc/caddy/Caddyfile:ro -v <certs>:/certs:ro caddy:2 caddy validate --config /etc/caddy/Caddyfile`
- 테스터 설치 번들 갱신: `bash bin/trust-bundle.sh` → `artifacts/trust-bundle/`. 서빙: `http://<host>/trust/`
- 번들 라이브 검증: `curl http://<host>/trust/install-trust-windows.bat` → 200

### 포트프록시 동기화가 «무엇을 했는지» 보는 법 (2026-09-02)

- 실행 heartbeat: `C:\Users\Public\mysqlai_sync.log` (예약작업이 뜰 때마다 1줄, UTF-16).
- 이번 실행이 포트프록시를 건드렸는지: 스크립트 표준출력 JSON 의 `portproxy_changed`
  (평상시 `false` 여야 정상) · `ports[].portproxy_action` (`unchanged` / `recreated` / `created`) ·
  `portproxy_state_known` (`false` = 현재 상태를 못 읽어 안전측으로 전부 재설정했다는 뜻).
- 절단이 실제로 멈췄는지: 브리지 러너 원장 `~/.mysql-ai-bridge/bridge.events.jsonl` 에서
  `ev=conn.retry` / `ev=api.fail` 의 시각이 sync 실행 시각 직후(3~19초)에 몰리는지 대조한다.
  수정 전에는 **5분마다 1건**이 규칙적으로 찍혔다.

```bash
# 러너 원장에서 5분 주기 절단 여부 확인 (수정 후에는 0건이어야 한다)
python3 - <<'PY'
import json, collections
c = collections.Counter()
for line in open('/home/claude-corp/.mysql-ai-bridge/bridge.events.jsonl', errors='replace'):
    if not line.strip(): continue
    d = json.loads(line)
    if d.get('ev') in ('conn.retry', 'api.fail'):
        c[d['ts'][:13]] += 1
print(sorted(c.items())[-6:])
PY
```

### 만료 감시 — 게이트와 감시는 다른 축이다 (2026-09-01)

`bin/deploy-web.sh` 의 `preflight_tls()` 가 leaf 만료를 보지만 그것은 **배포할 때만** 돈다.
배포가 없으면 신호도 없고, 그 사이 만료되면 **첫 신호가 전면 outage** 다. 그리고 그 preflight 는
**Root CA 를 아예 보지 않는다** — CA 만료는 테스터 전원 재설치라 회복 비용이 훨씬 크다.

| 축 | 실행 시점 | 대상 | 임계 | 실패 시 |
|---|---|---|---|---|
| `deploy-web.sh preflight_tls` (게이트) | 배포 직전 | leaf | 14일 | WARN 후 배포 계속 |
| `bin/cert-expiry-check.sh` (감시) | 주기(cron 주 1회) | **leaf + Root CA** | leaf 30일 / CA 180일 | exit 1(WARN)·2(CRIT) → cron 메일 |

- ⚠ **감시 임계는 게이트보다 넓어야 한다.** 좁으면 게이트가 먼저 울려 감시가 아무것도 더해
  주지 않는다 — 스크립트가 `--leaf-warn < 14` 를 **거절**하고, 두 파일의 상수 관계를 테스트가 잠근다.
- `--live <host>` 로 **실제 서빙본**도 함께 본다. 디스크 cert 를 갱신하고 배포하지 않으면
  사용자가 받는 것은 여전히 옛 cert 다 — 파일만 보면 그 창을 못 본다.
- 설치: `bash bin/install-cert-expiry-cron.sh`(멱등, `--print`/`--remove`). 정상이면 침묵하고
  임계 침범 시에만 stderr → cron 메일.
- 경보 시 갱신: `bash bin/tls-internal-ca.sh`(leaf 재발급 — **CA 유지라 테스터 재설치 불필요**)
  → `make deploy-web-only`.

> **왜 CRL/OCSP 가 아니라 만료 감시인가** (사용자 결정 2026-09-01): 사내 CA 에는 CRL 배포점도
> OCSP 도 없어 Windows Schannel 이 폐기상태를 «알 수 없음» 으로 하드 실패시킨다(feature-0043
> 브리지 결함의 원인). CRL 을 도입하면 폐기가 가능해지지만 **완화 플래그를 없애지는 못한다** —
> CRL 은 `nextUpdate` 가 있어 만료·404 시 같은 오류로 되돌아가므로 안전망이 계속 필요하다.
> 즉 CRL 은 «새 liveness 의존성 + 그 실패 모드가 이번 버그» 인 반면, 막는 위협(leaf 키 유출 +
> MITM)은 저확률이다. 그래서 폐기 인프라 대신 **만료를 놓치지 않는 것**에 투자한다.

## 13. Pre-approved Changes
- 비파괴적 운영 자산 재배치와 경로 수정

## 동기화 예약작업의 실행 계정 — SYSTEM 이 아니라 사용자 계정 + S4U

### 왜 SYSTEM 이면 안 되는가 (실측 2026-09-09)

`sync_mysql_ai_web_portproxy.ps1` 은 `wsl.exe -d <distro> -- bash -lc …` 로 WSL 안의 기본 라우트
IP 를 읽는다. **WSL 은 LOCAL SYSTEM 계정을 지원하지 않는다.**

| 실행 계정 | WSL 조회 | 콘솔 창 |
|---|---|---|
| `SYSTEM` (`ServiceAccount`) | **불가** — `WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED` · `EXIT=-1` | — |
| 사용자 계정 + `Interactive` | 가능 (`EXIT=0`) | **5분마다 뜬다** |
| **사용자 계정 + `S4U`** | **가능** (`EXIT=0`) | **안 뜬다** |

SYSTEM 으로 등록하면 작업은 5분마다 돌면서 매번 **rc=1** 로 죽는다 — 등록은 성공하고 스케줄러
상태도 「사용」이라 **겉보기로는 정상이며**, 실패는 `LastTaskResult` 를 봐야 드러난다. 라이브가
그 상태였다.

### 왜 `run_hidden.vbs` 가 있었나 — 그리고 왜 이제 필요 없는가

사용자 계정 + `Interactive` 로 등록하면 5분마다 PowerShell 콘솔 창이 화면에 뜬다. 그것을 숨기려고
`wscript`+`run_hidden.vbs` 래퍼를 씌우는 우회가 실제로 쓰였고, **그 vbs 가 사라지자 5분마다
「스크립트 파일을 찾을 수 없습니다」 오류창**이 떴다(사용자 제보 2026-09-09).

`S4U`(Service-For-User)는 비밀번호 저장 없이 **로그온 세션 없이** 실행하므로 창이 뜨지 않으면서
WSL 조회도 된다. 그래서 **vbs 래퍼는 이제 불필요하다** — 다만 그것은 「원래 불필요했다」는 뜻이
아니다. SYSTEM 도 Interactive 도 아닌 **제3의 선택지를 쓰기 때문에** 불필요해진 것이다.

### 등록 계약

- `-RunAsUser` 기본값 = **스크립트를 실행하는 사용자**(`$env:USERDOMAIN\$env:USERNAME`). SYSTEM 아님.
- `-RunLevel Highest` 유지 — `netsh interface portproxy` 변경에 승격이 필요하다.
- 트리거는 **부팅 + 5분 반복(3650일)** 뿐이다. `AtLogOn` 은 S4U 와 함께 「일부 트리거만 시작」
  경고를 내고 의미도 없어 제거했다. `RepetitionDuration` 에 `[TimeSpan]::MaxValue` 를 주면
  `Duration:P99999999DT23H59M59S` 로 **등록이 실패**한다(실측) — 유한값을 쓴다.

## 실제 리스너 검증과 복구 (2026-09-10)

정기 동기화는 netsh 매핑 외에 실제 TCP 리스너도 확인한다. 매핑이 맞고 리스너가 없을 때 활성 연결이 남으면 변경 없이 실패한다. 연결이 없을 때 해당 포트만 재등록하고 최대 2초 동안 리스너 복귀를 확인한다. SkipVerify는 이 필수 확인을 생략하지 않는다. 선택적인 TCP 연결 검사 실패도 성공 종료로 보고하지 않는다.

`-RepairOnly -SkipFirewall -LegacyListenPorts @()`는 기존 대상의 리스너만 복구한다. 매핑 조회 실패·불일치 때는 자동 IP 동기화의 재등록 분기로 진행하지 않는다. 방화벽 변경과 legacy 삭제도 거부한다. 설정을 바꾸는 정기 IP 동기화 호출은 기존 옵션을 유지한다.
