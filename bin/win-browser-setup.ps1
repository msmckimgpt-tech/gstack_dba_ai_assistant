<#
.SYNOPSIS
  feature-0008 WSL → 실제 Windows 브라우저 CDP 브리지 1회 setup (NAT + portproxy 모드).

.DESCRIPTION
  Chrome 의 remote-debugging 포트는 항상 127.0.0.1 에만 바인딩되므로, NAT 모드 WSL2
  에서 Windows Chrome 의 CDP 에 접속하려면 Windows 측 portproxy relay 가 필요하다.
  본 스크립트는:
    1. netsh portproxy 추가: 0.0.0.0:<RelayPort>  →  127.0.0.1:<CdpPort>
    2. 방화벽 인바운드 규칙 추가 (RelayPort, TCP)
  를 수행한다. **관리자 권한 PowerShell 에서 1회만** 실행하면 된다.

  대안: mirrored networking 모드 (관리자 불요) — bin/WIN-BROWSER-SETUP.md 의 옵션 B 참조.

.PARAMETER CdpPort
  Chrome remote-debugging 포트 (기본 9222 — win-browser.py 의 WIN_BROWSER_CDP_PORT 와 일치).

.PARAMETER RelayPort
  WSL 이 접속할 relay listen 포트 (기본 9223 — win-browser.py 의 WIN_BROWSER_RELAY_PORT 와 일치).

.PARAMETER Remove
  추가 대신 portproxy + 방화벽 규칙을 제거한다 (teardown).

.EXAMPLE
  # 관리자 PowerShell 에서 (WSL 경로 직접 실행):
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\<distro>\...\bin\win-browser-setup.ps1

.EXAMPLE
  # teardown:
  powershell -ExecutionPolicy Bypass -File ...\win-browser-setup.ps1 -Remove
#>
param(
  [int]$CdpPort = 9222,
  [int]$RelayPort = 9223,
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$ruleName = "WSL win-browser CDP relay ($RelayPort)"

function Assert-Admin {
  $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object System.Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "관리자 권한이 필요합니다. PowerShell 을 '관리자 권한으로 실행' 후 다시 시도하세요."
    exit 1
  }
}

Assert-Admin

# vEthernet (WSL) 어댑터의 Windows 측 IP 를 해석 — relay 를 LAN(0.0.0.0)이 아닌
# 이 인터페이스에만 바인딩하여 노출면을 WSL 서브넷으로 한정한다 (security review F1).
function Resolve-WslHostIP {
  $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -like 'vEthernet (WSL*' } |
        Select-Object -First 1
  if ($null -eq $ip) {
    Write-Error "vEthernet (WSL) 어댑터를 찾지 못했습니다. WSL 이 실행 중인지 확인하세요."
    exit 1
  }
  return $ip
}

$wslIp = Resolve-WslHostIP
$listenAddr = $wslIp.IPAddress
# WSL 서브넷 (방화벽 RemoteAddress scope). vEthernet IP 의 prefix 사용.
$wslSubnet = "$($listenAddr -replace '\.\d+$', '.0')/$($wslIp.PrefixLength)"

if ($Remove) {
  Write-Host "[win-browser-setup] teardown: portproxy + 방화벽 규칙 제거" -ForegroundColor Yellow
  netsh interface portproxy delete v4tov4 listenport=$RelayPort listenaddress=$listenAddr 2>$null
  netsh interface portproxy delete v4tov4 listenport=$RelayPort listenaddress=0.0.0.0 2>$null  # 구버전 잔여 정리
  if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
    Remove-NetFirewallRule -DisplayName $ruleName
  }
  Write-Host "[win-browser-setup] 제거 완료." -ForegroundColor Green
  netsh interface portproxy show v4tov4
  exit 0
}

Write-Host "[win-browser-setup] portproxy 추가: ${listenAddr}:$RelayPort -> 127.0.0.1:$CdpPort (vEthernet WSL 전용)" -ForegroundColor Cyan
# 중복 방지를 위해 기존 동일 listenport 항목 제거 후 추가 (idempotent). 구버전 0.0.0.0 바인딩도 정리.
netsh interface portproxy delete v4tov4 listenport=$RelayPort listenaddress=$listenAddr 2>$null | Out-Null
netsh interface portproxy delete v4tov4 listenport=$RelayPort listenaddress=0.0.0.0 2>$null | Out-Null
netsh interface portproxy add v4tov4 listenport=$RelayPort listenaddress=$listenAddr connectport=$CdpPort connectaddress=127.0.0.1

Write-Host "[win-browser-setup] 방화벽 인바운드 규칙: '$ruleName' (TCP $RelayPort, Private, WSL 서브넷 $wslSubnet 한정)" -ForegroundColor Cyan
if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
  Remove-NetFirewallRule -DisplayName $ruleName   # 재실행 시 갱신
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
  -LocalPort $RelayPort -LocalAddress $listenAddr -RemoteAddress $wslSubnet `
  -Action Allow -Profile Private | Out-Null

Write-Host ""
Write-Host "[win-browser-setup] 현재 portproxy 테이블:" -ForegroundColor Green
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "완료. WSL 에서 검증:" -ForegroundColor Green
Write-Host "  python3 bin/win-browser.py launch   # Windows Chrome 기동" -ForegroundColor White
Write-Host "  python3 bin/win-browser.py doctor   # 브리지 'relay' 감지 확인" -ForegroundColor White
