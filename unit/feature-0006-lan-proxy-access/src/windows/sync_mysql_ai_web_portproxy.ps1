[CmdletBinding()]
param(
    [string]$DistroName = "Ubuntu",
    [string]$ListenAddress = "127.0.0.1",
    [int]$HttpListenPort = 80,
    [int]$HttpsListenPort = 443,
    [int[]]$LegacyListenPorts = @(18080),
    [string]$HttpFirewallRuleName = "mysql_ai_web_http_80",
    [string]$HttpsFirewallRuleName = "mysql_ai_web_https_443",
    [string[]]$LegacyFirewallRuleNames = @("mysql_ai_web_18080"),
    [string[]]$RemoteAddresses = @("LocalSubnet"),
    [string]$ConnectAddress = "",
    [switch]$SkipFirewall,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-Ipv4Address {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Value, [ref]$parsed)) {
        return $false
    }

    return $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
}

function Invoke-WslBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    $raw = & wsl.exe -d $Name -- bash -lc $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        $detail = [string]::Join([Environment]::NewLine, @($raw)).Trim()
        if ([string]::IsNullOrWhiteSpace($detail)) {
            $detail = "WSL command execution failed."
        }
        throw "WSL command failed for distro '$Name': $detail"
    }

    return [string]::Join([Environment]::NewLine, @($raw)).Trim()
}

function Get-FirstNonEmptyLine {
    param(
        [string]$Text
    )

    foreach ($line in @(($Text -split "\r?\n"))) {
        $candidate = ($line | Out-String).Trim()
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            return $candidate
        }
    }

    return ""
}

function Get-WslRouteInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $routeText = Invoke-WslBash -Name $Name -Command "ip route show default"
    $routeLine = Get-FirstNonEmptyLine -Text $routeText
    if ([string]::IsNullOrWhiteSpace($routeLine)) {
        throw "Failed to resolve the default route from distro '$Name'."
    }

    $routeMatch = [regex]::Match($routeLine, "\bdev\s+(?<iface>\S+)\b")
    if (-not $routeMatch.Success) {
        throw "Failed to extract the default route interface from: $routeLine"
    }

    $routeInterface = $routeMatch.Groups["iface"].Value.Trim()
    if ($routeInterface -notmatch "^[A-Za-z0-9_.:-]+$") {
        throw "Default route interface '$routeInterface' contains unsupported characters."
    }

    $addressText = Invoke-WslBash -Name $Name -Command ("ip -o -4 addr show dev '{0}'" -f $routeInterface)
    $addressLine = Get-FirstNonEmptyLine -Text $addressText
    if ([string]::IsNullOrWhiteSpace($addressLine)) {
        throw "No IPv4 address was found on interface '$routeInterface' in distro '$Name'."
    }

    $addressMatch = [regex]::Match($addressLine, "\binet\s+(?<ip>[0-9]{1,3}(?:\.[0-9]{1,3}){3})/")
    if (-not $addressMatch.Success) {
        throw "Failed to extract IPv4 from interface '$routeInterface': $addressLine"
    }

    $ipv4 = $addressMatch.Groups["ip"].Value.Trim()
    if (-not (Test-Ipv4Address -Value $ipv4)) {
        throw "Resolved IPv4 '$ipv4' on interface '$routeInterface' is invalid."
    }

    return [pscustomobject]@{
        route_interface = $routeInterface
        connect_address = $ipv4
    }
}

function Normalize-RemoteAddresses {
    param(
        [string[]]$Values
    )

    $items = New-Object System.Collections.Generic.List[string]
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        foreach ($segment in ($value -split ",")) {
            $candidate = ($segment | Out-String).Trim()
            if (-not [string]::IsNullOrWhiteSpace($candidate)) {
                $items.Add($candidate)
            }
        }
    }

    return @($items.ToArray())
}

function Normalize-PortList {
    param(
        [object[]]$Values
    )

    $items = New-Object System.Collections.Generic.List[int]
    foreach ($value in @($Values)) {
        if ($null -eq $value) {
            continue
        }

        foreach ($segment in (("$value") -split ",")) {
            $candidate = ($segment | Out-String).Trim()
            if ([string]::IsNullOrWhiteSpace($candidate)) {
                continue
            }

            $port = 0
            if (-not [int]::TryParse($candidate, [ref]$port)) {
                throw "Port '$candidate' is not a valid integer."
            }

            if ($port -lt 1 -or $port -gt 65535) {
                throw "Port '$port' must be between 1 and 65535."
            }

            if (-not $items.Contains($port)) {
                $items.Add($port)
            }
        }
    }

    return @($items.ToArray())
}

function Invoke-Netsh {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$IgnoreExitCode
    )

    $output = & netsh.exe @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if (-not $IgnoreExitCode -and $exitCode -ne 0) {
        $text = [string]::Join([Environment]::NewLine, @($output))
        throw "netsh failed ($exitCode): $text"
    }

    return [string]::Join([Environment]::NewLine, @($output))
}

function Get-PortProxyEntries {
    <#
    현재 등록된 v4tov4 portproxy 매핑을 읽어 딕셔너리로 돌려준다.
    키 = "<listen_addr>:<listen_port>", 값 = "<connect_addr>:<connect_port>".

    ⚠ 헤더 문구로 파싱하지 않는다 — `netsh` 출력은 OS 표시 언어를 따라가므로(한국어 Windows 는
      "수신 대기" 등) 헤더에 기대면 로케일이 바뀌는 순간 조용히 빈 결과가 된다. 대신 데이터 행의
      «IPv4 포트 IPv4 포트» 형태만 뽑는다 — 이 형태는 언어와 무관하다.

    읽지 못하면 **$null** 을 돌려준다. 빈 딕셔너리와 구분되어야 하기 때문이다: 빈 딕셔너리는
    "등록된 것이 없다"(→ 추가해야 한다)이고, $null 은 "현재 상태를 모른다"(→ 종전대로 무조건
    재설정한다)이다. 둘을 뭉개면 파싱이 깨진 날 포트포워딩이 조용히 사라진다.
    #>

    # ⚠ 여기서 `-IgnoreExitCode` 를 쓰지 않는다. 쓰면 netsh 가 실패해도 예외가 오르지 않고 오류
    #   **텍스트**가 그대로 넘어오는데, 그 텍스트는 아래 정규식에 하나도 매칭되지 않아 «빈 맵»이
    #   된다 — 즉 "읽지 못했다"가 "등록된 것이 없다"로 둔갑한다. 동작 자체는 재설정 쪽이라 안전
    #   하지만, `portproxy_state_known` 이 `true` 라고 **거짓 보고**하게 되어 위 주석이 약속한
    #   $null 계약이 실제로는 성립하지 않는다. 실패를 실패로 올려야 그 구분이 유지된다.
    try {
        $text = Invoke-Netsh -Arguments @("interface", "portproxy", "show", "v4tov4")
    }
    catch {
        return $null
    }

    if ($null -eq $text) {
        return $null
    }

    $map = @{}
    $rowPattern = "^\s*(?<la>\d{1,3}(?:\.\d{1,3}){3})\s+(?<lp>\d{1,5})\s+(?<ca>\d{1,3}(?:\.\d{1,3}){3})\s+(?<cp>\d{1,5})\s*$"
    foreach ($line in @(($text -split "\r?\n"))) {
        $match = [regex]::Match($line, $rowPattern)
        if (-not $match.Success) {
            continue
        }

        $key = "{0}:{1}" -f $match.Groups["la"].Value, $match.Groups["lp"].Value
        $map[$key] = "{0}:{1}" -f $match.Groups["ca"].Value, $match.Groups["cp"].Value
    }

    return $map
}

if (-not (Test-IsAdministrator)) {
    throw "Administrator privileges are required."
}

if (-not (Test-Ipv4Address -Value $ListenAddress)) {
    throw "ListenAddress '$ListenAddress' is not a valid IPv4 address."
}

$RemoteAddresses = Normalize-RemoteAddresses -Values $RemoteAddresses
if (-not $SkipFirewall -and $RemoteAddresses.Count -eq 0) {
    throw "At least one remote address range is required unless -SkipFirewall is used."
}

$LegacyListenPorts = Normalize-PortList -Values $LegacyListenPorts
$publicPorts = Normalize-PortList -Values @($HttpListenPort, $HttpsListenPort)
if ($publicPorts.Count -ne 2) {
    throw "HttpListenPort and HttpsListenPort must resolve to two distinct ports."
}

$RouteInterface = ""
if ([string]::IsNullOrWhiteSpace($ConnectAddress)) {
    $routeInfo = Get-WslRouteInfo -Name $DistroName
    $ConnectAddress = [string]$routeInfo.connect_address
    $RouteInterface = [string]$routeInfo.route_interface
}

$ConnectAddress = $ConnectAddress.Trim()
if (-not (Test-Ipv4Address -Value $ConnectAddress)) {
    throw "ConnectAddress '$ConnectAddress' is not a valid IPv4 address."
}

$portMappings = @(
    [pscustomobject]@{
        listen_port = $HttpListenPort
        firewall_rule = $HttpFirewallRuleName
        verify_uri = "http://{0}:{1}/" -f $ListenAddress, $HttpListenPort
    },
    [pscustomobject]@{
        listen_port = $HttpsListenPort
        firewall_rule = $HttpsFirewallRuleName
        verify_uri = $null
    }
)

# ── 이미 맞는 매핑은 건드리지 않는다 (2026-09-02) ────────────────────────────────
#
# 이 스크립트는 5분마다 예약 실행된다. 종전에는 매 실행이 조건 없이 `delete` → `add` 였고,
# `netsh interface portproxy delete` 는 그 리스너를 내려 **해당 포트를 지나던 기존 TCP 연결을
# 전부 끊는다**. WSL IP 가 바뀌지 않은 평상시에도 5분마다 한 번씩 모든 연결이 끊긴 것이다.
#
# 실측(2026-09-02): 개인 AI 브리지 러너의 대기 호출(`wait_for_request`, 서버가 55초 보류)이
# 5분 주기로 `RemoteDisconnected` 를 맞았다 — WARN 14건 중 13건이 이 작업 실행 후 3~19초 안에
# 발생했고, 서로 다른 시각에 뜬 러너 프로세스들이 **모두 같은 벽시계 위상**(:04/:09/:14…)에서
# 끊겼다. 브라우저처럼 짧은 요청은 재시도로 가려지지만, 오래 유지되는 연결은 그대로 드러난다.
#
# 그래서 **원하는 매핑이 이미 그대로면 아무것도 하지 않는다.** 이 스크립트의 목적은 WSL 재부팅
# 으로 바뀐 IP 를 따라가는 것이지 매번 리스너를 새로 세우는 것이 아니다 — 목적은 유지하면서
# 부작용만 없앤다.
#
# ⚠ 현재 상태를 **읽지 못했을 때는 종전대로 재설정한다**(`$proxyStateKnown = $false`). 모르는
#   것을 "맞다" 로 낙관하면 파싱이 깨진 날 포트포워딩이 조용히 사라진다 — 안전한 실패 방향은
#   «불필요한 재설정»이지 «필요한 재설정 누락»이 아니다.
#
# ⚠ **알려진 트레이드오프 — TOCTOU** (codex 리뷰 P2, 수용): 상태를 읽은 뒤 판정하기까지의 창에
#   다른 도구가 매핑을 지우면, 이 실행은 조회 당시 값만 보고 `unchanged` 로 건너뛴다 — 다음
#   실행(최대 5분)까지 접근이 끊길 수 있다. 종전의 «무조건 재설정» 에는 없던 창이다.
#   그럼에도 수용한 이유: netsh 에 원자적 비교-교체가 없어 창을 구조적으로 없앨 수 없고,
#   **이 스크립트 외에 portproxy 를 건드리는 주체가 없는 것이 전제**다(있다면 종전 코드에서도
#   두 주체가 서로를 덮어썼다). 반대로 무조건 재설정은 5분마다 **확실히** 연결을 끊었다 —
#   확률적 5분 창과 확정적 5분 절단을 맞바꾼 것이다. 아래 verify 단계의 `Test-NetConnection`
#   결과가 JSON 에 남으므로 그 창에 빠졌는지는 사후에 판별할 수 있다.
$existingProxies = Get-PortProxyEntries
$proxyStateKnown = ($null -ne $existingProxies)

$legacyPortsToRemove = @($LegacyListenPorts | Where-Object { $_ -notin @($HttpListenPort, $HttpsListenPort) })
$legacyPortsDeleted = New-Object System.Collections.Generic.List[int]
foreach ($legacyPort in $legacyPortsToRemove) {
    # legacy 삭제는 **조건 없이 시도한다** — 위 public 포트와 달리 skip 최적화를 두지 않는다.
    #
    # 처음에는 여기도 "이미 없으면 건너뛴다" 를 넣었다가 되돌렸다(codex 리뷰 P2). 이유 둘:
    #   ① 얻는 것이 없다. legacy 포트는 더 이상 쓰지 않는 포트라 거기 걸린 활성 연결이 없고,
    #      없는 매핑에 대한 `delete` 는 **아무 연결도 끊지 않는다**. 이 스크립트가 고치려던
    #      「기존 연결 절단」은 public 포트(80/443)에서만 발생한다.
    #   ② 잃는 것이 있다. 파서가 못 읽는 형태(netsh 는 `connectaddress` 에 hostname 도 허용한다)
    #      로 등록된 legacy 매핑은 `ContainsKey` 에 안 잡혀 **영영 삭제되지 않는다**.
    # 즉 skip 은 위험만 도입하는 최적화였다. 안 하는 편이 낫다.
    #
    # 삭제 **성공한 것만** 기록한다. 없는 매핑을 지우려 하면 netsh 가 비-0 으로 끝나는데,
    # 그것까지 목록에 넣으면 "지웠다" 는 원장이 거짓이 된다(운영자가 정리 완료로 오판).
    # 없는 것을 못 지우는 것은 정상이므로 예외는 삼키되 기록도 하지 않는다.
    try {
        Invoke-Netsh -Arguments @(
            "interface", "portproxy", "delete", "v4tov4",
            "listenaddress=$ListenAddress",
            "listenport=$legacyPort",
            "protocol=tcp"
        ) | Out-Null
        $legacyPortsDeleted.Add($legacyPort) | Out-Null
    }
    catch {
        # 대상이 없었다(정상) 또는 삭제 실패. 어느 쪽이든 "지웠다" 로 기록하지 않는다.
    }
}

$portActions = @{}
foreach ($mapping in $portMappings) {
    $mappingKey = "{0}:{1}" -f $ListenAddress, $mapping.listen_port
    $desiredTarget = "{0}:{1}" -f $ConnectAddress, $mapping.listen_port

    if ($proxyStateKnown -and $existingProxies.ContainsKey($mappingKey) -and
        $existingProxies[$mappingKey] -eq $desiredTarget) {
        # 이미 원하는 그대로다 — 기존 연결을 살려 둔다.
        $portActions[[string]$mapping.listen_port] = "unchanged"
        continue
    }

    $portActions[[string]$mapping.listen_port] =
        if ($proxyStateKnown -and -not $existingProxies.ContainsKey($mappingKey)) { "created" } else { "recreated" }

    # 여기서는 지운다. `add` 는 같은 listen 조합이 이미 있으면 실패하므로, 재설정 경로에서는
    # 선삭제가 필요하다(없으면 `-IgnoreExitCode` 로 무해하게 지나간다).
    Invoke-Netsh -Arguments @(
        "interface", "portproxy", "delete", "v4tov4",
        "listenaddress=$ListenAddress",
        "listenport=$($mapping.listen_port)",
        "protocol=tcp"
    ) -IgnoreExitCode | Out-Null

    Invoke-Netsh -Arguments @(
        "interface", "portproxy", "add", "v4tov4",
        "listenaddress=$ListenAddress",
        "listenport=$($mapping.listen_port)",
        "connectaddress=$ConnectAddress",
        "connectport=$($mapping.listen_port)",
        "protocol=tcp"
    ) | Out-Null
}

if (-not $SkipFirewall) {
    foreach ($ruleName in @($LegacyFirewallRuleNames + @($HttpFirewallRuleName, $HttpsFirewallRuleName)) | Select-Object -Unique) {
        if ([string]::IsNullOrWhiteSpace($ruleName)) {
            continue
        }

        Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule | Out-Null
    }

    foreach ($mapping in $portMappings) {
        New-NetFirewallRule `
            -DisplayName $mapping.firewall_rule `
            -Direction Inbound `
            -Action Allow `
            -Profile Private `
            -Protocol TCP `
            -LocalAddress $ListenAddress `
            -LocalPort $mapping.listen_port `
            -RemoteAddress $RemoteAddresses | Out-Null
    }
}

$portProxyText = Invoke-Netsh -Arguments @("interface", "portproxy", "show", "all")
$portResults = New-Object System.Collections.Generic.List[object]

foreach ($mapping in $portMappings) {
    $listenProbe = $null
    $connectProbe = $null
    $httpStatusCode = $null

    if (-not $SkipVerify) {
        $listenProbe = Test-NetConnection -ComputerName $ListenAddress -Port $mapping.listen_port -WarningAction SilentlyContinue
        $connectProbe = Test-NetConnection -ComputerName $ConnectAddress -Port $mapping.listen_port -WarningAction SilentlyContinue

        if ($mapping.verify_uri) {
            try {
                $httpResponse = Invoke-WebRequest `
                    -Uri $mapping.verify_uri `
                    -UseBasicParsing `
                    -MaximumRedirection 0 `
                    -TimeoutSec 10
                $httpStatusCode = [int]$httpResponse.StatusCode
            }
            catch {
                if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                    $httpStatusCode = [int]$_.Exception.Response.StatusCode.value__
                }
            }
        }
    }

    $portResults.Add(
        [pscustomobject]@{
            listen_port = $mapping.listen_port
            firewall_rule = if ($SkipFirewall) { "" } else { $mapping.firewall_rule }
            # 이번 실행이 이 포트에 무엇을 했는지 — `unchanged` 면 기존 연결이 유지됐다는 뜻이다.
            # 이 필드가 없으면 "조용히 아무것도 안 한 것" 과 "매번 재설정한 것" 이 로그에서 같아 보인다.
            portproxy_action = $portActions[[string]$mapping.listen_port]
            verify_listen = if ($listenProbe) { [bool]$listenProbe.TcpTestSucceeded } else { $null }
            verify_connect = if ($connectProbe) { [bool]$connectProbe.TcpTestSucceeded } else { $null }
            verify_http_status = $httpStatusCode
        }
    ) | Out-Null
}

[pscustomobject]@{
    listen_address = $ListenAddress
    connect_address = $ConnectAddress
    route_interface = $RouteInterface
    remote_addresses = @($RemoteAddresses)
    ports = @($portResults.ToArray())
    removed_legacy_ports = @($legacyPortsToRemove)
    # 실제로 지운 것 — 위 `removed_legacy_ports` 는 «대상» 목록이라 둘이 다를 수 있다.
    legacy_ports_deleted = @($legacyPortsDeleted.ToArray())
    removed_legacy_firewall_rules = if ($SkipFirewall) { @() } else { @($LegacyFirewallRuleNames) }
    # 현재 매핑을 읽어서 판단했는지 여부. `false` 면 안전측으로 전부 재설정했다는 뜻이다.
    portproxy_state_known = $proxyStateKnown
    # 이번 실행이 portproxy 를 건드렸는지. 평상시(IP 불변)에는 `false` 여야 정상이다.
    # ⚠ legacy 삭제도 «건드린 것»에 포함한다 — public 포트만 세면 18080 을 지운 실행이
    #   `legacy_ports_deleted:[18080]` 과 `portproxy_changed:false` 를 동시에 보고해
    #   필드 의미가 자기모순이 된다 (codex 리뷰 P2).
    portproxy_changed = (@($portActions.Values | Where-Object { $_ -ne "unchanged" }).Count -gt 0) -or
                        ($legacyPortsDeleted.Count -gt 0)
    portproxy = $portProxyText.Trim()
} | ConvertTo-Json -Depth 6
