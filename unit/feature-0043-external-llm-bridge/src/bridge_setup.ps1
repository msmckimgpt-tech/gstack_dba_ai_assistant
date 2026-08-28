# mysql-ai 브리지 설치·기동 스크립트 (Windows PowerShell).
#
# POSIX 판(`bridge_setup.sh`)과 **같은 계약**이다 — 하는 일·안 하는 일·멈추는 지점이 같다.
# 두 파일이 갈리면 OS 마다 다른 연결 절차가 되고, 그것이 정확히 이 기능이 없애려는 마찰이다.
#
#   1. 사내 사설 CA 수신 + 지문 대조   2. bridge_agent.py 수신 + 체크섬 대조
#   3. mysql-ai-bridge:// 핸들러 등록   4. --check → 상주
#
# 사용:
#   $env:BRIDGE_BASE='https://host'; $env:BRIDGE_TOKEN='mat_...'; .\bridge_setup.ps1
#
# 웹 콘솔의 [연결 명령 복사](Windows) 가 이 값을 채운 한 줄을 만들어 준다.
$ErrorActionPreference = 'Stop'

function Say([string]$m) { Write-Host "[bridge-setup] $m" }
function Die([string]$m) { Write-Host "`n[bridge-setup] 중단: $m" -ForegroundColor Red; exit 1 }

$Base  = $env:BRIDGE_BASE
$Token = $env:BRIDGE_TOKEN
$CaSha = $env:BRIDGE_CA_SHA256
$AgSha = $env:BRIDGE_AGENT_SHA256
$Home_ = if ($env:BRIDGE_HOME) { $env:BRIDGE_HOME } else { Join-Path $HOME '.mysql-ai-bridge' }
$ExtraArgs = if ($env:BRIDGE_ARGS) { $env:BRIDGE_ARGS } else { '' }

if (-not $Base)  { Die 'BRIDGE_BASE 가 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요.' }
if (-not $Token) { Die 'BRIDGE_TOKEN 이 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요.' }

$Py = $null
foreach ($c in @('python','python3','py')) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $Py = $c; break }
}
if (-not $Py) { Die 'python 이 없습니다. 파이썬 3.8 이상을 설치한 뒤 다시 실행하세요.' }

New-Item -ItemType Directory -Force -Path $Home_ | Out-Null
$Host_ = ([Uri]$Base).Host

function Sha256File([string]$p) {
  (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower()
}

# ── 1. CA ────────────────────────────────────────────────────────────────────
#
# 평문 HTTP 로 받는다 — 엣지 인증서를 서명한 것이 이 CA 라, 아직 CA 가 없는 상태의 https 는
# 실패한다(부트스트랩 데드락). 평문의 위험은 아래 지문 대조가 덮는다.
$CaPath = Join-Path $Home_ 'rootCA.crt'
$CaTmp  = "$CaPath.tmp"
Say "사내 CA 를 받는 중… (http://$Host_/trust/rootCA.crt)"
try {
  Invoke-WebRequest -Uri "http://$Host_/trust/rootCA.crt" -OutFile $CaTmp -UseBasicParsing
} catch {
  Die '사내 CA 를 받지 못했습니다. 사내망에 연결돼 있는지 확인하세요.'
}

if ($CaSha) {
  # 인증서 **DER** 기준 — 서버(`_ca_fingerprint`) 및 `openssl x509 -fingerprint -sha256` 과 같은 기준.
  # PEM 텍스트를 그냥 해싱하면 줄바꿈 차이로 값이 갈린다.
  try {
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $CaTmp
    $sha  = [System.Security.Cryptography.SHA256]::Create()
    $got  = ([BitConverter]::ToString($sha.ComputeHash($cert.RawData))).Replace('-','').ToLower()
  } catch {
    Die 'CA 지문을 계산하지 못했습니다(인증서 형식 확인 필요).'
  }
  $want = $CaSha.ToLower().Replace(':','')
  if ($got -ne $want) {
    Die "CA 지문이 다릅니다.`n  기대: $want`n  실제: $got`n  네트워크 중간에서 바뀌었을 수 있습니다. 진행하지 말고 운영자에게 알리세요."
  }
  Say 'CA 지문 일치.'
} else {
  # POSIX 판과 **같은 계약** — 건너뛰지 않고 멈춘다(codex 적대 리뷰 P1-3). 이 CA 는 평문 HTTP 로
  # 받았고 다음 단계에서 신뢰시킨다. "경고 후 진행" 은 경고가 아니라 승인이다.
  if ($env:BRIDGE_ALLOW_UNVERIFIED -eq '1') {
    Say '⚠ BRIDGE_ALLOW_UNVERIFIED=1 — CA 지문 대조를 건너뜁니다. 신뢰할 수 있는 망에서만 쓰세요.'
  } else {
    Die @"
CA 지문을 받지 못해 대조할 수 없습니다.
  이 CA 는 평문 HTTP 로 받았고, 다음 단계에서 이 연결에 신뢰시킵니다 — 대조 없이 진행하면
  중간에서 바꿔치기당해도 알 수 없습니다.

  해결: 운영자에게 CA 지문(SHA-256)을 받아 다시 실행하세요.
        `$env:BRIDGE_CA_SHA256='<지문>'; .\bridge_setup.ps1
  (위험을 인지하고 강행하려면 `$env:BRIDGE_ALLOW_UNVERIFIED='1')
"@
  }
}
Move-Item -Force $CaTmp $CaPath

# ── 2. 러너 ──────────────────────────────────────────────────────────────────
$AgentPath = Join-Path $Home_ 'bridge_agent.py'
$AgentTmp  = "$AgentPath.tmp"
Say '러너를 받는 중…'
# Windows 는 CA 를 시스템 저장소에 넣지 않고도 요청별로 신뢰시키기 어려워, curl.exe 가 있으면
# --cacert 로 프로세스 한정 신뢰를 쓴다(POSIX 판과 같은 계약). 없으면 사용자가 CA 를 신뢰해
# 두었다고 보고 Invoke-WebRequest 로 받는다.
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
try {
  if ($curl) {
    & $curl.Source -fsS --cacert $CaPath -o $AgentTmp "$Base/static/agent/bridge_agent.py"
    if ($LASTEXITCODE -ne 0) { throw 'curl failed' }
  } else {
    Invoke-WebRequest -Uri "$Base/static/agent/bridge_agent.py" -OutFile $AgentTmp -UseBasicParsing
  }
} catch {
  Die '러너를 받지 못했습니다. CA 신뢰 또는 네트워크를 확인하세요.'
}

if ($AgSha) {
  $got = Sha256File $AgentTmp
  if ($got -ne $AgSha.ToLower()) {
    # 롤링 배포 교대 중일 수 있다 — 1회 재시도 후에도 다르면 멈춘다.
    Say '체크섬 불일치 — 배포 교대 중일 수 있어 1회 재시도합니다.'
    Start-Sleep -Seconds 20
    if ($curl) { & $curl.Source -fsS --cacert $CaPath -o $AgentTmp "$Base/static/agent/bridge_agent.py" }
    else { Invoke-WebRequest -Uri "$Base/static/agent/bridge_agent.py" -OutFile $AgentTmp -UseBasicParsing }
    $got = Sha256File $AgentTmp
    if ($got -ne $AgSha.ToLower()) {
      Die "러너 체크섬이 다릅니다.`n  기대: $($AgSha.ToLower())`n  실제: $got`n  진행하지 말고 운영자에게 알리세요."
    }
  }
  Say '러너 체크섬 일치.'
} else {
  Say '⚠ 서버가 러너 체크섬을 제공하지 않아 대조를 건너뜁니다.'
}
Move-Item -Force $AgentTmp $AgentPath

# ── 3. 프로토콜 핸들러 ────────────────────────────────────────────────────────
#
# 브라우저는 로컬 프로세스를 직접 띄우지 못한다. 웹의 [내 AI 실행] 버튼은 스킴 URL 을 열 뿐이고,
# 그것을 프로세스로 바꾸는 것이 이 등록이다. HKCU 만 쓴다 — 관리자 권한이 필요 없고, 이 사용자
# 계정 밖으로 영향이 나가지 않는다.
$LaunchPs = Join-Path $Home_ 'launch.ps1'
@"
# mysql-ai 브리지 러너 기동 (프로토콜 핸들러가 부른다).
# 토큰은 여기 없다 — 웹이 스킴 인자로 그때그때 넘긴다.
param([string]`$Url)
`$ErrorActionPreference = 'SilentlyContinue'
`$home_ = '$Home_'
if (`$Url -match '[?&]token=([^&]+)') { `$tok = `$Matches[1] } else { exit 2 }
# ⚠ 이 스킴은 아무 웹페이지나 열 수 있다 — 토큰을 확인하기 전에는 아무것도 죽이지 않는다.
# 먼저 검증, 그다음 교체(POSIX 판과 같은 계약, codex 적대 리뷰 P2).
if (`$tok -notlike 'mat_*') { exit 2 }
`$env:BRIDGE_TOKEN = `$tok
& '$Py' (Join-Path `$home_ 'bridge_agent.py') --base '$Base' ``
  --ca (Join-Path `$home_ 'rootCA.crt') --check | Out-Null
if (`$LASTEXITCODE -ne 0) { exit 3 }
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { `$_.CommandLine -like '*bridge_agent.py*' } |
  ForEach-Object { Stop-Process -Id `$_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process -WindowStyle Hidden -FilePath '$Py' -ArgumentList @(
  (Join-Path `$home_ 'bridge_agent.py'), '--base', '$Base',
  '--ca', (Join-Path `$home_ 'rootCA.crt'), '--resume')
"@ | Set-Content -Encoding UTF8 $LaunchPs

try {
  $key = 'HKCU:\Software\Classes\mysql-ai-bridge'
  New-Item -Path $key -Force | Out-Null
  Set-ItemProperty -Path $key -Name '(Default)' -Value 'URL:mysql-ai bridge'
  Set-ItemProperty -Path $key -Name 'URL Protocol' -Value ''
  New-Item -Path "$key\shell\open\command" -Force | Out-Null
  Set-ItemProperty -Path "$key\shell\open\command" -Name '(Default)' `
    -Value "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$LaunchPs`" `"%1`""
  Say '웹 [내 AI 실행] 버튼용 핸들러를 등록했습니다 (mysql-ai-bridge://).'
} catch {
  # 등록 실패는 연결을 막지 않는다 — 러너는 아래에서 그대로 뜬다. 다만 버튼이 안 되는 사실은
  # 말해야 한다(조용히 실패하면 사용자가 버튼을 눌러 보고 고장으로 읽는다).
  Say '⚠ 프로토콜 핸들러를 등록하지 못했습니다 — 웹의 [내 AI 실행] 버튼은 이 머신에서 동작하지'
  Say '  않습니다. 러너가 꺼지면 이 명령을 다시 실행하세요. (연결 자체에는 영향 없음)'
}

# ── 4. 연결 확인 → 상주 ──────────────────────────────────────────────────────
Say '연결을 확인하는 중…'
$env:BRIDGE_TOKEN = $Token
& $Py $AgentPath --base $Base --ca $CaPath --check
if ($LASTEXITCODE -ne 0) {
  Die '연결 확인에 실패했습니다. 토큰이 만료됐다면 웹에서 [연결 명령 복사] 를 다시 누르세요.'
}

# 이미 떠 있는 러너는 정리한다. 둘이 같은 계정으로 대기하면 같은 질문을 두 번 집으려다 한쪽이
# 409 로 하차하고, 그 왕복이 사용자 계정 토큰을 태운다.
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like '*bridge_agent.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Say '러너를 상주시킵니다…'
$argv = @($AgentPath, '--base', $Base, '--ca', $CaPath, '--resume')
if ($ExtraArgs) { $argv += $ExtraArgs.Split(' ') }
$proc = Start-Process -PassThru -WindowStyle Hidden -FilePath $Py -ArgumentList $argv
Start-Sleep -Seconds 2
if ($proc -and -not $proc.HasExited) {
  Say "완료. 웹 화면의 표시가 '내 AI 대기 중' 으로 바뀌면 질문을 보낼 수 있습니다."
  Say "  종료   : Stop-Process -Id $($proc.Id)"
  Say "  해제   : Remove-Item -Recurse '$Home_'  +  Remove-Item -Recurse 'HKCU:\Software\Classes\mysql-ai-bridge'"
} else {
  Die '러너가 바로 종료됐습니다. 토큰·CA·파이썬 버전을 확인하세요.'
}
