$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$resultPath = Join-Path $PSScriptRoot 'apply-result.json'
$result = @{ result='FAIL'; changed_ports=@(); service_restart=$false; firewall_change=$false }
try {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator privileges are required.'}
    $source=Join-Path $PSScriptRoot 'sync_mysql_ai_web_portproxy.ps1'
    $target='C:\ProgramData\mysql_ai_web_portproxy\sync_mysql_ai_web_portproxy.ps1'
    $sourceBytes=[IO.File]::ReadAllBytes($source)
    $hash=[Security.Cryptography.SHA256]::Create()
    try { $sourceHash=([BitConverter]::ToString($hash.ComputeHash($sourceBytes))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
    if($sourceHash -ne '7b629d37f3f221f6f6864ff69be212295e4d785af48ec60add2cbafb6f945f86'){throw 'Reviewed source changed; refusing to apply.'}
    if((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant() -ne 'f639c48fc85d3335b4ca2805fecad961fa61c603f10381a80197b183a9140ce1'){throw 'Installed script changed since review; refusing to overwrite.'}
    $listen='112.185.196.20'; $connect='172.26.154.233'
    $entries=@(& netsh.exe interface portproxy show v4tov4)
    if($LASTEXITCODE -ne 0){throw 'Cannot read current portproxy mappings.'}
    $otherBefore=@($entries | Where-Object {$_ -match '^\s*\d+\.\d+\.\d+\.\d+\s+\d+' -and $_ -notmatch '^\s*112\.185\.196\.20\s+(80|443)\s+'})
    foreach($port in @(80,443)) {
        $pattern='^\s*112\.185\.196\.20\s+'+$port+'\s+172\.26\.154\.233\s+'+$port+'\s*$'
        if(-not @($entries | Where-Object {$_ -match $pattern}).Count){throw "Mapping changed on port $port; refusing to alter another target."}
        $tcp=New-Object Net.Sockets.TcpClient
        try { $pending=$tcp.ConnectAsync($connect,$port); if(-not $pending.Wait(2000) -or -not $tcp.Connected){throw "WSL destination is not reachable on $port."} } finally {$tcp.Dispose()}
    }
    $network=[Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    $protectedBefore=@($network.GetActiveTcpListeners() | Where-Object {$_.Port -in @(6379,28080)} | ForEach-Object {$_.ToString()} | Sort-Object)
    $backup=$target+'.backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $target -Destination $backup
    [IO.File]::WriteAllBytes($target,$sourceBytes)
    $result.backup=$backup
    $output=& $target -ListenAddress $listen -ConnectAddress $connect -HttpListenPort 80 -HttpsListenPort 443 -LegacyListenPorts @() -RepairOnly -SkipFirewall -SkipVerify
    $report=($output -join "`n") | ConvertFrom-Json
    $otherAfter=@((& netsh.exe interface portproxy show v4tov4) | Where-Object {$_ -match '^\s*\d+\.\d+\.\d+\.\d+\s+\d+' -and $_ -notmatch '^\s*112\.185\.196\.20\s+(80|443)\s+'})
    if(($otherBefore -join "`n") -ne ($otherAfter -join "`n")){throw 'Other portproxy mappings changed during verification.'}
    $protectedAfter=@($network.GetActiveTcpListeners() | Where-Object {$_.Port -in @(6379,28080)} | ForEach-Object {$_.ToString()} | Sort-Object)
    if(($protectedBefore -join ',') -ne ($protectedAfter -join ',')){throw 'Protected service listeners changed during verification.'}
    $result.result='PASS'; $result.sync=$report; $result.source_sha256=$sourceHash
    $result.changed_ports=@($report.ports | Where-Object {$_.portproxy_action -ne 'unchanged'} | ForEach-Object {$_.listen_port})
    $result.other_mappings_unchanged=$true; $result.protected_listeners_unchanged=$true
} catch { $result.error=$_.Exception.Message }
$result | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $resultPath
if($result.result -ne 'PASS'){exit 1}
