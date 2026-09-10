[CmdletBinding()]
param(
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
if (-not $Source) { $Source = Join-Path $PSScriptRoot "../src/windows/sync_mysql_ai_web_portproxy.ps1" }
$sourceText = [IO.File]::ReadAllText((Resolve-Path $Source))
$tokens = $null
$parseErrors = $null
$tree = [Management.Automation.Language.Parser]::ParseInput($sourceText, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
if (Get-Variable DqaPortproxyMockState -Scope Global -ErrorAction SilentlyContinue) {
    throw "Fixture state already exists; refusing to replace it."
}

# Replace complete function definitions before executing any source code.
$replacements = @{
    "Test-IsAdministrator" = 'function Test-IsAdministrator { return $true }'
    "Invoke-WslBash" = 'function Invoke-WslBash { throw "Unexpected WSL access" }'
    "Invoke-Netsh" = @'
function Invoke-Netsh {
    param([string[]]$Arguments, [switch]$IgnoreExitCode)
    $state = $global:DqaPortproxyMockState
    $state.calls.Add(($Arguments -join " ")) | Out-Null
    if ($Arguments[0] -ne "interface" -or $Arguments[1] -ne "portproxy") {
        throw "Unexpected netsh command"
    }
    if ($Arguments[2] -eq "show") {
        if ($state.lookupFails) { throw "Fixture mapping lookup failed" }
        if ($state.targetChanged) {
            return "192.0.2.10 80 198.51.100.20 80`n192.0.2.10 443 198.51.100.21 443"
        }
        return "192.0.2.10 80 198.51.100.20 80`n192.0.2.10 443 198.51.100.20 443"
    }
    if ($Arguments[2] -notin @("delete", "add") -or
        $Arguments -notcontains "listenaddress=192.0.2.10" -or
        $Arguments -notcontains "listenport=443") {
        throw "Mutation escaped the sole drifted fixture port"
    }
    $state.mutations.Add(($Arguments -join " ")) | Out-Null
    if ($Arguments[2] -eq "add" -and $state.recoveryWorks) { $state.listening443 = $true }
    return ""
}
'@
    "Get-PortListenerState" = @'
function Get-PortListenerState {
    param([string]$Address, [int]$Port)
    $state = $global:DqaPortproxyMockState
    if ($Address -ne "192.0.2.10" -or $Port -notin @(80, 443)) {
        throw "Listener query escaped fixture endpoints"
    }
    $state.probes.Add($Port) | Out-Null
    if ($Port -eq 80) { return @{ listening = $true; active_connections = 1 } }
    return @{ listening = $state.listening443; active_connections = $state.active443 }
}
'@
}
$edits = @()
foreach ($name in $replacements.Keys) {
    $found = @($tree.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    if ($found.Count -ne 1) { throw "Expected exactly one source function: $name" }
    $edits += [pscustomobject]@{ start = $found[0].Extent.StartOffset; end = $found[0].Extent.EndOffset; text = $replacements[$name] }
}
foreach ($edit in ($edits | Sort-Object start -Descending)) {
    $sourceText = $sourceText.Remove($edit.start, $edit.end - $edit.start).Insert($edit.start, $edit.text)
}
$subject = [scriptblock]::Create($sourceText)

# Fail closed if future source changes unexpectedly enter a real side-effect path.
function netsh.exe { throw "Real netsh access is prohibited" }
function wsl.exe { throw "Real WSL access is prohibited" }
function Get-NetFirewallRule { throw "Firewall access is prohibited" }
function Remove-NetFirewallRule { throw "Firewall mutation is prohibited" }
function New-NetFirewallRule { throw "Firewall mutation is prohibited" }
function Test-NetConnection { throw "Real connection probes are prohibited" }
function Invoke-WebRequest { throw "Real HTTP probes are prohibited" }
function Start-Sleep { param($Milliseconds) }

$cases = @(
    @{ name = "healthy mappings retain both listeners"; listening = $true; active = 0; recovery = $true; fails = $false; mutations = 0 },
    @{ name = "only missing 443 listener is recovered"; listening = $false; active = 0; recovery = $true; fails = $false; mutations = 2 },
    @{ name = "active connections prevent listener replacement"; listening = $false; active = 1; recovery = $true; fails = $true; mutations = 0 },
    @{ name = "failed listener recovery cannot report success"; listening = $false; active = 0; recovery = $false; fails = $true; mutations = 2 },
    @{ name = "RepairOnly rejects unknown mappings without mutation"; listening = $false; active = 0; recovery = $true; fails = $true; mutations = 0; lookupFails = $true },
    @{ name = "RepairOnly rejects a changed target without mutation"; listening = $false; active = 0; recovery = $true; fails = $true; mutations = 0; targetChanged = $true }
)
$results = @()
try {
    foreach ($case in $cases) {
        $global:DqaPortproxyMockState = @{
            listening443 = $case.listening; active443 = $case.active; recoveryWorks = $case.recovery
            lookupFails = [bool]$case.lookupFails; targetChanged = [bool]$case.targetChanged
            calls = [Collections.Generic.List[string]]::new()
            mutations = [Collections.Generic.List[string]]::new()
            probes = [Collections.Generic.List[int]]::new()
        }
        $failure = $null
        $output = $null
        try {
            $output = & $subject -ListenAddress "192.0.2.10" -ConnectAddress "198.51.100.20" `
                -RepairOnly -SkipFirewall -SkipVerify -LegacyListenPorts @()
        }
        catch { $failure = $_.Exception.Message }
        $state = $global:DqaPortproxyMockState
        if (($null -ne $failure) -ne $case.fails) { throw "$($case.name): unexpected result: $failure" }
        if ($state.mutations.Count -ne $case.mutations) { throw "$($case.name): wrong mutation count: $($state.mutations.Count)" }
        if (-not $case.lookupFails -and -not $case.targetChanged -and $state.probes.Count -lt 2) {
            throw "$($case.name): mandatory listener checks were skipped"
        }
        if (-not $case.fails) {
            $report = ($output -join "`n") | ConvertFrom-Json
            $http = @($report.ports | Where-Object listen_port -eq 80)[0]
            $https = @($report.ports | Where-Object listen_port -eq 443)[0]
            if ($http.portproxy_action -ne "unchanged") { throw "Healthy HTTP listener was changed" }
            $expected = if ($case.mutations) { "recovered" } else { "unchanged" }
            if ($https.portproxy_action -ne $expected) { throw "Incorrect HTTPS recovery result" }
        }
        elseif ($case.active -gt 0 -and $failure -notmatch "(?i)active|connection") {
            throw "Active-connection case failed for an unrelated reason: $failure"
        }
        elseif (-not $case.recovery -and $failure -notmatch "(?i)listen") {
            throw "Missing-listener case failed for an unrelated reason: $failure"
        }
        elseif (($case.lookupFails -or $case.targetChanged) -and $failure -notmatch "RepairOnly") {
            throw "RepairOnly case failed for an unrelated reason: $failure"
        }
        $results += [pscustomobject]@{ case = $case.name; result = "PASS"; mutations = @($state.mutations); listener_checks = $state.probes.Count; expected_error = $failure }
    }
}
finally { Remove-Variable DqaPortproxyMockState -Scope Global -ErrorAction SilentlyContinue }
[pscustomobject]@{ result = "PASS"; cases = $results; live_mutations = 0 } | ConvertTo-Json -Depth 6
