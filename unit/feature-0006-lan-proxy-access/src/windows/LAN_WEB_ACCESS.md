# mysql_ai LAN HTTPS Access

## Goal
- Web UI를 HTTPS와 사용자 지정 LAN 주소로 노출하는 운영 절차 템플릿이다.
- 이 문서는 특정 사내 도메인이나 고정 IP를 전제하지 않는다.
- 실제 값은 `<public-host>`, `<listen-address>`, `<remote-ranges>` 자리에 운영 환경 값을 넣어 사용한다.

## Runtime components
- Docker `web`는 `8000`에서 FastAPI를 제공한다.
- Docker `caddy`는 `80/443`에서 TLS를 종료하고 `web:8000`으로 프록시한다.
- Windows `portproxy`는 `<listen-address>:80/443`을 현재 WSL IPv4로 전달한다.
- 인증서 파일은 `../../../artifacts/certs/<public-host>/` 아래에 둔다.

## Why HTTPS is required
- API Vault는 브라우저 Web Crypto API를 사용한다.
- Web Crypto API는 secure context에서만 안정적으로 동작한다.
- 따라서 외부 접근 기본 경로는 `https://<public-host>`를 권장한다.

References:
- MDN Web Crypto API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API
- MDN Secure Contexts: https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts

## Required values
- `<public-host>`: 인증서와 브라우저 접근에 사용할 DNS 이름
- `<listen-address>`: Windows가 바인딩할 LAN IPv4
- `<remote-ranges>`: 방화벽 허용 대역
- `<distro-name>`: WSL 배포판 이름

## Files
- `../caddy/Caddyfile`
- `./sync_mysql_ai_web_portproxy.ps1`
- `./register_mysql_ai_web_portproxy_task.ps1`

## Start the TLS proxy from the execution root
프로젝트 루트에서:

```bash
cd ./_ai_delegated_dev_template/repo
make web-tls-up
```

지속적으로 프록시를 유지하려면 현재 디렉토리의 `.env`에 아래 값을 넣는다.

```text
ENABLE_WEB_TLS_PROXY=1
WEB_PUBLIC_HOST=<public-host>
WEB_TLS_CERT_FILE=/certs/<public-host>/fullchain.pem
WEB_TLS_KEY_FILE=/certs/<public-host>/privkey.pem
```

## Apply Windows LAN exposure
관리자 권한 PowerShell에서 프로젝트 루트 기준으로:

```powershell
Set-Location .\_ai_delegated_dev_template\repo\unit\feature-0006-lan-proxy-access\src\windows

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\sync_mysql_ai_web_portproxy.ps1 `
  -DistroName "<distro-name>" `
  -ListenAddress "<listen-address>" `
  -RemoteAddresses "<remote-ranges>"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\register_mysql_ai_web_portproxy_task.ps1 `
  -DistroName "<distro-name>" `
  -ListenAddress "<listen-address>" `
  -RemoteAddresses "<remote-ranges>" `
  -OfficialHost "<public-host>" `
  -StartNow
```

## Verify
### 1. Docker side

```bash
cd ./_ai_delegated_dev_template/repo
make web-tls-status
```

### 2. Windows portproxy and firewall

```powershell
netsh interface portproxy show all
Get-NetFirewallRule -DisplayName mysql_ai_web_http_80 | Format-List
Get-NetFirewallRule -DisplayName mysql_ai_web_https_443 | Format-List
Test-NetConnection <listen-address> -Port 80
Test-NetConnection <listen-address> -Port 443
```

### 3. Scheduled task

```powershell
Get-ScheduledTask -TaskName mysql_ai_web_portproxy_sync | Format-List TaskName,State,Triggers
Get-ScheduledTaskInfo -TaskName mysql_ai_web_portproxy_sync | Format-List *
```

### 4. Browser path

기대 결과:
- `http://<public-host>`는 `https://<public-host>`로 리다이렉트된다.
- `https://<public-host>/api/session`이 응답한다.
- `window.isSecureContext === true`
- `window.crypto?.subtle` 사용 가능

## Notes
- 이 문서의 값은 예시가 아니라 placeholder다. 그대로 복사하지 말고 운영 환경 값으로 치환한다.
- 컨테이너 내부 경로(`/certs`, `/shared`)는 런타임 계약이므로 절대경로를 유지한다.
