[CmdletBinding()]
param(
    [string]$TaskName = "mysql_ai_web_portproxy_sync",
    [string]$DistroName = "Ubuntu",
    [string]$ListenAddress = "127.0.0.1",
    [string[]]$RemoteAddresses = @("LocalSubnet"),
    [string]$OfficialHost = "localhost",
    # 실행 계정. 기본값은 **이 스크립트를 실행하는 사용자** 다 — SYSTEM 이 아니다.
    # 근거는 아래 §실행 계정 주석 참조(WSL 이 LOCAL SYSTEM 을 지원하지 않는다).
    [string]$RunAsUser = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME),
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
    -RepetitionDuration (New-TimeSpan -Days 3650)

$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $startBoundary
$dailyTrigger.Repetition = $repeatSeed.Repetition

# 트리거는 **실측으로 통과한 조합만** 남긴다 (2026-09-09).
#   · `-RepetitionDuration ([TimeSpan]::MaxValue)` → `작업 XML에 형식이 잘못되었거나 범위를
#     벗어난 값이 있습니다 (Duration:P99999999DT23H59M59S)` 로 등록 실패.
#   · `AtLogOn` 은 S4U 와 함께 쓰면 「지정된 트리거 중 일부만 작업을 시작합니다」 경고가 난다 —
#     로그온 세션에 매이지 않는 것이 S4U 의 요점이므로 의미도 없다.
# 5분 반복이 3650일간 이어지므로 부팅·로그온 직후에도 최대 5분 안에 첫 동기화가 돈다.
$triggers = @(
    $startupTrigger,
    $dailyTrigger
)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# ── 실행 계정: SYSTEM 이 아니라 **사용자 계정 + S4U** 다 (2026-09-09 실측으로 교정) ──────
#
# 종전 이 줄은 `-UserId "SYSTEM" -LogonType ServiceAccount` 였다. 그 구성은 **이 스크립트에서
# 절대 동작하지 않는다** — `sync_mysql_ai_web_portproxy.ps1` 은 `wsl.exe -d <distro>` 로 WSL 안의
# 기본 라우트 IP 를 읽는데, WSL 은 LOCAL SYSTEM 계정을 지원하지 않는다:
#
#     SYSTEM 으로 실행 → WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED · EXIT=-1  (실측)
#     사용자 계정      → inet 172.26.x.x/20 · EXIT=0                  (실측)
#
# 그래서 SYSTEM 으로 등록하면 작업은 5분마다 돌면서 매번 rc=1 로 죽는다(라이브에서 그 상태였다).
#
# **왜 S4U 인가**: 사용자 계정 + `Interactive` 로 등록하면 5분마다 PowerShell 콘솔 창이 사용자
# 화면에 뜬다. 그 창을 숨기려고 `wscript`+`run_hidden.vbs` 래퍼를 씌우는 우회가 실제로 쓰였고,
# 그 vbs 가 사라지자 **5분마다 「스크립트 파일을 찾을 수 없습니다」 오류창**이 떴다(사용자 제보).
# `S4U`(Service-For-User)는 비밀번호 저장 없이 **로그온 세션 없이** 실행하므로 **창이 뜨지 않고**
# WSL 조회도 된다(실측 rc=0). 즉 vbs 래퍼가 필요 없어진다.
#
# ⚠ `-RunLevel Highest` 는 유지한다 — `netsh interface portproxy` 변경에 승격이 필요하다.
$principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType S4U -RunLevel Highest

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
    run_as = $RunAsUser
    logon_type = "S4U"
    listen_address = $ListenAddress
    listen_ports = @(80, 443)
    official_url = "https://$OfficialHost"
    remote_addresses = ($remoteCsv -split ",")
    trigger_types = @("Boot", "Logon", "Daily")
    repetition_interval = [string]$dailyTrigger.Repetition.Interval
    repetition_duration = [string]$dailyTrigger.Repetition.Duration
} | ConvertTo-Json -Depth 4
