[CmdletBinding()]
param(
    [string]$TaskName = "mysql_ai_web_portproxy_sync",
    [string]$DistroName = "Ubuntu",
    [string]$ListenAddress = "127.0.0.1",
    [string[]]$RemoteAddresses = @("LocalSubnet"),
    [string]$OfficialHost = "localhost",
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    throw "Administrator privileges are required."
}

$syncScript = Join-Path $PSScriptRoot "sync_mysql_ai_web_portproxy.ps1"
if (-not (Test-Path $syncScript)) {
    throw "Sync script not found: $syncScript"
}

$remoteCsv = ($RemoteAddresses | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ","
if ([string]::IsNullOrWhiteSpace($remoteCsv)) {
    throw "At least one remote address range is required."
}

$quotedScript = '"' + $syncScript + '"'
$quotedDistro = '"' + $DistroName + '"'
$quotedListenAddress = '"' + $ListenAddress + '"'
$quotedRemoteCsv = '"' + $remoteCsv + '"'

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $quotedScript,
    "-DistroName", $quotedDistro,
    "-ListenAddress", $quotedListenAddress,
    "-RemoteAddresses", $quotedRemoteCsv
) -join " "

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments

$now = Get-Date
$startBoundary = $now.AddMinutes(1)
$startBoundary = Get-Date `
    -Year $startBoundary.Year `
    -Month $startBoundary.Month `
    -Day $startBoundary.Day `
    -Hour $startBoundary.Hour `
    -Minute $startBoundary.Minute `
    -Second 0

$repeatSeed = New-ScheduledTaskTrigger `
    -Once `
    -At $startBoundary `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)

$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $startBoundary
$dailyTrigger.Repetition = $repeatSeed.Repetition

$triggers = @(
    $startupTrigger,
    $logonTrigger,
    $dailyTrigger
)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal | Out-Null

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
}

$task = Get-ScheduledTask -TaskName $TaskName
[pscustomobject]@{
    task_name = $task.TaskName
    task_path = $task.TaskPath
    state = [string]$task.State
    run_as = "SYSTEM"
    listen_address = $ListenAddress
    listen_ports = @(80, 443)
    official_url = "https://$OfficialHost"
    remote_addresses = ($remoteCsv -split ",")
    trigger_types = @("Boot", "Logon", "Daily")
    repetition_interval = [string]$dailyTrigger.Repetition.Interval
    repetition_duration = [string]$dailyTrigger.Repetition.Duration
} | ConvertTo-Json -Depth 4
