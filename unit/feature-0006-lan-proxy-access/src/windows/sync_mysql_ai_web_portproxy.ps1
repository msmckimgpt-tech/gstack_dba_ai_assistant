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

$legacyPortsToRemove = @($LegacyListenPorts | Where-Object { $_ -notin @($HttpListenPort, $HttpsListenPort) })
foreach ($legacyPort in $legacyPortsToRemove) {
    Invoke-Netsh -Arguments @(
        "interface", "portproxy", "delete", "v4tov4",
        "listenaddress=$ListenAddress",
        "listenport=$legacyPort",
        "protocol=tcp"
    ) -IgnoreExitCode | Out-Null
}

foreach ($mapping in $portMappings) {
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
    removed_legacy_firewall_rules = if ($SkipFirewall) { @() } else { @($LegacyFirewallRuleNames) }
    portproxy = $portProxyText.Trim()
} | ConvertTo-Json -Depth 6
