# mysql-ai 브리지 설치·기동 스크립트 (Windows PowerShell).
#
# ⚠ **이 파일은 UTF-8 BOM 을 반드시 유지한다.** (사용자 제보 2026-08-31)
#
# Windows PowerShell 5.1(윈도우 기본)은 BOM 없는 `.ps1` 을 UTF-8 이 아니라 **시스템 ANSI
# 코드페이지**(한국어 윈도우면 CP949)로 읽는다. 그러면 이 파일의 한글 주석·메시지가 깨지고,
# 깨진 바이트가 인접한 `'`·`)` 를 삼켜 **파서가 죽는다** — 사용자가 본 것이 그것이다:
#
#     식에 닫는 ')'가 없습니다.
#     ... "BRIDGE_PROBED_HANDLER='$ProbedHandler' ??auto|none 以??섎굹?ъ빞 ?⑸땲??
#
# 실측: BOM 없음 → ParseFile 오류 6건 / BOM 있음 → PARSE OK. (PowerShell 7 은 BOM 없이도
# UTF-8 로 읽으므로 **7 로만 검사하면 이 결함을 못 본다** — 회귀 테스트는 BOM 바이트를 직접 본다.)
#
# 편집기 설정 주의: "UTF-8(BOM 없음)" 으로 저장하면 이 결함이 그대로 되돌아온다.
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

function Drop([string]$m) {
  # POSIX 판과 같은 이유로 **stderr** 로 쓴다 — 파이프·치환에 먹혀 경고만 사라지는 형태를
  # 실측에서 겪었다(sh 판 `drop`). 거른 사실이 도달하는 것도 계약의 일부다.
  [Console]::Error.WriteLine("[bridge-setup] ⚠ $m — 이 값은 버리고 기본 동작으로 진행합니다.")
}

$Base  = $env:BRIDGE_BASE
$Token = $env:BRIDGE_TOKEN
$CaSha = $env:BRIDGE_CA_SHA256
$AgSha = $env:BRIDGE_AGENT_SHA256
$Home_ = if ($env:BRIDGE_HOME) { $env:BRIDGE_HOME } else { Join-Path $HOME '.mysql-ai-bridge' }
# 사람이 직접 주는 칸 — 무검증(기존 호환).
$ExtraArgs = if ($env:BRIDGE_ARGS) { $env:BRIDGE_ARGS } else { '' }

# ── LLM 이 채우는 칸 (P0-AD — POSIX 판과 같은 계약) ──────────────────────────
#
# `PROBED_` 접두 = **신뢰하지 않고 검증한다.** 값이 이상하면 버리고 기본 동작으로 간다
# (막지 않는다 — 판단이 틀렸다고 연결까지 못 하게 만들면 그 사용자는 아무 경로도 없다).
$ProbedPy      = $env:BRIDGE_PROBED_PY
$ProbedAi      = $env:BRIDGE_PROBED_AI
$ProbedArgsRaw = $env:BRIDGE_PROBED_ARGS
$ProbedHandler = if ($env:BRIDGE_PROBED_HANDLER) { $env:BRIDGE_PROBED_HANDLER } else { 'auto' }

if (-not $Base)  { Die 'BRIDGE_BASE 가 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요.' }
if (-not $Token) { Die 'BRIDGE_TOKEN 이 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요.' }

#: 후보를 실제로 **실행해** 3.8+ 인지 본다. 이름만 보면 `python` 이 2.7 인 머신에서 러너가
#: 문법 오류로 죽고, 그 죽음은 "AI 가 답을 안 한다" 로만 보인다.
function Test-PyOk([string]$cand) {
  if (-not $cand) { return $false }
  $cmd = Get-Command $cand -ErrorAction SilentlyContinue
  if (-not $cmd) { return $false }

  # ⚠ **Microsoft Store 앱 실행 별칭 스텁을 먼저 걸러낸다** (사용자 제보 2026-08-31).
  #   파이썬을 설치하지 않은 윈도우에도 `…\AppData\Local\Microsoft\WindowsApps\python3.exe`
  #   가 **2바이트 스텁**으로 존재한다. 실행하면 Store 를 열려고 stderr 에 `Python` 을 뱉는데,
  #   `$ErrorActionPreference='Stop'` 에서 그 stderr 는 **NativeCommandError 로 던져진다**
  #   (`2>$null` 로도 못 막는다 — 리다이렉션 이전에 오류 레코드가 된다). 그래서 설치가 거기서
  #   죽고, **바로 다음 후보인 진짜 파이썬까지 가보지도 못했다**(실측: 같은 머신에
  #   `Python314\python.exe` 가 멀쩡히 있었다).
  $src = $cmd.Source
  if ($src -and $src -like '*\WindowsApps\*') { return $false }

  # ⚠ 아래는 **네이티브 명령**이다. 함수 스코프에서만 Stop 을 풀고 try 로 감싼다 — 전역을
  #   바꾸지 않으므로 이 절 밖의 fail-fast 계약은 그대로다.
  $ErrorActionPreference = 'SilentlyContinue'
  $global:LASTEXITCODE = 0
  try {
    & $cand -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>&1 | Out-Null
  } catch {
    return $false
  }
  return ($LASTEXITCODE -eq 0)
}

$Py = $null
if ($ProbedPy) {
  # 이 값은 명령의 첫 토큰이 된다 — 옵션으로 해석될 수 있는 것과 메타문자는 받지 않는다.
  if ($ProbedPy -match '^-' -or $ProbedPy -match '[;&|`$<>"'']') {
    Drop 'BRIDGE_PROBED_PY 가 실행 파일 이름·경로 형태가 아닙니다'
  } elseif (Test-PyOk $ProbedPy) {
    $Py = $ProbedPy; Say "파이썬: $Py (조사값)"
  } else {
    Drop "BRIDGE_PROBED_PY='$ProbedPy' 를 쓸 수 없습니다(미실존 또는 3.8 미만)"
  }
}
if (-not $Py) {
  # ⚠ 순서는 POSIX 판·지시문과 **같아야** 한다 — 안내가 `python3 → python` 인데
  #   여기만 `python` 이 먼저면 같은 머신에서 다른 인터프리터가 뽑힌다(codex P2-6).
  foreach ($c in @('python3','python','py')) {
    if (Test-PyOk $c) { $Py = $c; break }
  }
}

# ── 파이썬이 없으면 «설치까지» 도와준다 (사용자 결정 2026-08-31) ───────────────
#
# 개발자가 아닌 사용자에게 "파이썬을 먼저 설치하고 오세요" 는 사실상 막다른 길이다. 그래서
# 없을 때는 여기서 설치 경로를 연다. 단 **말없이 설치하지는 않는다** — 남의 컴퓨터에 소프트웨어를
# 얹는 일이므로 무엇을 왜 설치하는지 말하고 동의를 받는다(비대화형이면 명령만 알려 주고 멈춘다).
#
# 수단은 **winget**(App Installer)이다. 윈도우 10 1809+ 에 기본 포함이고, 패키지가 서명·해시
# 검증된 공식 경로라 **우리가 설치 프로그램 해시를 관리하지 않아도 된다** — 이 스크립트의
# 「받은 것은 대조한다」 계약을 우리가 직접 구현하는 대신 winget 이 이미 지키는 축이다.
# (임의 URL 에서 installer.exe 를 받아 실행하는 방식은 대조 없이 실행하는 형태가 되어 채택 안 함.)

#: winget 이 **실제로 쓸 수 있는가**. `WindowsApps\winget.exe` 는 App Installer 가 없으면
#: python3 와 같은 빈 스텁일 수 있으므로, 존재가 아니라 **`--version` 이 도는지**로 본다.
function Test-WingetOk {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
  $ErrorActionPreference = 'SilentlyContinue'
  $global:LASTEXITCODE = 0
  try { & winget --version 2>&1 | Out-Null } catch { return $false }
  return ($LASTEXITCODE -eq 0)
}

#: 설치 직후 이 프로세스의 PATH 에는 새 파이썬이 없다(부모가 물려준 값이라 갱신되지 않는다).
#: 레지스트리에서 다시 읽어 합친다 — 새 셸을 열라고 안내하면 그 자체가 또 다른 막다른 길이다.
function Update-PathFromRegistry {
  try {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:PATH = (@($m, $u) | Where-Object { $_ }) -join ';'
  } catch { }
}

if (-not $Py) {
  $canWinget = Test-WingetOk
  $autoOk = $false
  if ($canWinget) {
    if ($env:BRIDGE_AUTO_INSTALL_PYTHON -eq '1') {
      $autoOk = $true                      # 스크립트·무인 실행용 사전 동의
    } elseif ([Environment]::UserInteractive) {
      Say '이 브리지는 파이썬 3.8 이상이 필요한데 이 컴퓨터에서 찾지 못했습니다.'
      Say '  winget(마이크로소프트 공식 앱 설치 도구)으로 Python 3.12 를 설치할 수 있습니다.'
      Say '  설치 범위는 현재 사용자이며 관리자 권한이 필요하지 않습니다.'
      $ans = Read-Host '  지금 설치할까요? (y/N)'
      $autoOk = ($ans -eq 'y' -or $ans -eq 'Y')
    }
  }

  if ($autoOk) {
    Say 'Python 3.12 를 설치하는 중… (수 분 걸릴 수 있습니다)'
    $ErrorActionPreference = 'SilentlyContinue'
    $global:LASTEXITCODE = 0
    try {
      & winget install --id Python.Python.3.12 --exact --scope user --silent `
        --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | Out-Null
    } catch { }
    if ($LASTEXITCODE -ne 0) {
      # `--scope user` 를 받지 않는 패키지·환경이 있다. 범위를 빼고 한 번 더 — 그래도 안 되면
      # 아래 안내로 떨어진다(조용히 실패하지 않는다).
      $global:LASTEXITCODE = 0
      try {
        & winget install --id Python.Python.3.12 --exact --silent `
          --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | Out-Null
      } catch { }
    }
    $ErrorActionPreference = 'Stop'
    Update-PathFromRegistry
    foreach ($c in @('python3','python','py')) {
      if (Test-PyOk $c) { $Py = $c; break }
    }
    if (-not $Py) {
      # PATH 가 아직 안 잡혔을 수 있다 — 표준 설치 위치를 직접 본다.
      foreach ($p in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                       "$env:ProgramFiles\Python312\python.exe")) {
        if ((Test-Path $p) -and (Test-PyOk $p)) { $Py = $p; break }
      }
    }
    if ($Py) { Say "파이썬을 설치했습니다: $Py" }
  }
}

if (-not $Py) {
  $hint = if ($canWinget) {
    '  · 설치(권장): winget install --id Python.Python.3.12 --exact --scope user'
  } else {
    '  · 설치: https://www.python.org/downloads/windows/ (설치 중 "Add python.exe to PATH" 체크)'
  }
  Die "python 3.8 이상을 찾지 못했습니다.

$hint
  · 설치 후 이 명령을 다시 실행하세요.
  · 이미 설치했는데 이 메시지가 나오면, 경로를 직접 지정하세요:
        `$env:BRIDGE_PROBED_PY='C:\path\to\python.exe'
  · 참고: 시작 메뉴의 `"앱 실행 별칭`" 에 있는 python3 는 Microsoft Store 로 가는 **빈 스텁**이라
    파이썬이 아닙니다 — 이 스크립트는 그것을 건너뜁니다."
}

#: 러너에 넘길 `--ai <name>`. **PATH 에 실재할 때만** 넘긴다 — 없는 이름을 주면 러너가
#: "쓸 수 있는 AI 를 찾지 못했습니다" 로 죽는다(실측 2026-08-28: Windows 에 claude 부재).
#: LLM 칸이 지목할 수 있는 AI CLI — **알려진 이름만** (POSIX 판과 같은 목록).
#: 실존 검사만 두면 `BRIDGE_PROBED_AI=rm` 이 통과해 러너가 그것을 AI 로 실행한다(codex 실측).
#: 표 밖 CLI 는 사람 칸(`$env:BRIDGE_ARGS='--ai mycli'`)으로.
#: ⚠ **정본은 러너의 `_RUNTIME_SPECS`(`src/agent/runtimes.py`) 다** — POSIX 판과 같은 이유.
#:   넓으면 설치는 통과하고 런타임에서 실패한다. `test_ai_cli_allowlist_sync.py` 가 잠근다.
$KnownAiClis = @('claude', 'codex', 'gemini')

#: AI CLI 가 이 컴퓨터에 있는가. **PATH 밖 표준 설치 위치까지** 본다 — 러너의 `_which_ai`
#: 와 같은 계약이다. 두 곳이 갈리면 설치기는 「없다」 하고 러너는 「있다」 하는(또는 그 반대)
#: 상태가 되고, 사용자는 어느 쪽을 믿어야 할지 알 수 없다.
#:
#: ⚠ 실측 2026-09-01: Claude Code 의 Windows native installer 는
#:   `%USERPROFILE%\.local\bin\claude.exe` 에 넣는데 **그 폴더가 사용자 PATH 에 없었다**.
#:   `Get-Command claude` 도 못 찾았고, 그래서 설치기·러너 양쪽이 「AI 없음」이라 봤다 —
#:   정작 그 파일을 직접 실행하면 `2.1.70 (Claude Code)` 를 멀쩡히 답했다.
function Get-AiDirs {
  $dirs = @()
  if ($HOME)                { $dirs += (Join-Path $HOME '.local\bin') }           # Claude Code · Codex 설치기
  if ($env:APPDATA)         { $dirs += (Join-Path $env:APPDATA 'npm') }           # npm -g
  # ⚠ `%LOCALAPPDATA%\Programs\Ollama` 는 여기 있었다 — 러너는 P0-Z6.1 에서 이 경로를 함께
  #   지웠는데(`agent/discovery.py` 의 같은 자리 주석) 설치 스크립트에만 남아 있었다.
  #   런타임을 걷어낸 뒤에도 설치 경로만 남으면 「없앴다는데 아직 찾아다닌다」가 된다.
  return $dirs
}

#: ⚠ **`.cmd`·`.bat` 는 목록에 없다** — 러너와 같은 이유다(codex 적대 리뷰 P1). 배치 파일은
#: `cmd.exe` 파싱을 한 번 더 거쳐 질문 본문의 `&`·`|` 가 메타문자가 되므로, 러너가 직접
#: 실행하지 않는다. 여기서 「있다」고 하면 설치기는 통과시키고 러너가 exit 4 를 내는
#: 비대칭이 생긴다 — 두 곳이 다른 답을 내면 사용자는 어느 쪽도 믿을 수 없다.
$AiExecExts = @('.exe', '.com')

function Test-AiPresent([string]$name) {
  if (-not $name) { return $false }
  # `Get-Command` 는 PATHEXT 를 보므로 이름만으로도 `.exe` 를 찾는다. 단 그 결과가
  # 배치·스크립트면 러너는 실행하지 않으므로 여기서도 인정하지 않는다.
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) {
    $src = $cmd.Source
    if (-not $src) { return $true }                     # 함수·별칭 — 판정 대상 아님
    if ([System.IO.Path]::GetExtension($src).ToLower() -in $AiExecExts) { return $true }
  }
  foreach ($d in (Get-AiDirs)) {
    foreach ($ext in $AiExecExts) {
      # `-PathType Leaf` — 같은 이름의 **디렉터리**를 실행 파일로 읽지 않는다.
      if (Test-Path -LiteralPath (Join-Path $d ($name + $ext)) -PathType Leaf) { return $true }
    }
  }
  return $false
}

$AiArgs = @()
if ($ProbedAi) {
  if ($ProbedAi -notin $KnownAiClis) {
    Drop "BRIDGE_PROBED_AI='$ProbedAi' 는 알려진 AI CLI 가 아닙니다($($KnownAiClis -join ' '))"
  } elseif (Test-AiPresent $ProbedAi) {
    $AiArgs = @('--ai', $ProbedAi); Say "AI 런타임: $ProbedAi (조사값)"
  } else {
    Drop "BRIDGE_PROBED_AI='$ProbedAi' 를 이 컴퓨터에서 찾지 못했습니다"
  }
}

#: 러너 추가 인자 — **allowlist**. 통과시키는 축은 「이 머신의 사양·속도에 맞추는 수치」뿐이다.
#: 러너에는 `--cmd`(임의 명령을 AI 호출로 실행)·`--base`/`--token`/`--ca`(다른 서버·다른
#: 자격증명으로 돌리기)·`--once`/`--check`(상주하지 않고 끝나기)가 있고, 그중 하나라도 이 칸으로
#: 들어오면 이 스크립트가 보장한다는 것이 전부 무너진다.
function Get-FilteredProbedArgs([string]$raw) {
  if (-not $raw) { return @() }
  $out = @(); $expect = $null
  foreach ($tok in ($raw -split '\s+' | Where-Object { $_ })) {
    if ($expect) {
      # 축마다 실제 타입으로 본다 — 러너의 `--workers` 는 int 다. 하나의 정규식으로 뭉뚱그리면
      # 설치기는 통과시키고 러너가 argparse 에서 죽는다(codex P2-6).
      if ($expect -in @('--workers', '--max-workers')) {
        if ($tok -notmatch '^[0-9]+$') {
          Drop "BRIDGE_PROBED_ARGS: $expect 의 값 '$tok' 이 정수가 아닙니다"; return @()
        }
        if ([int]$tok -lt 1 -or [int]$tok -gt 64) {
          Drop "BRIDGE_PROBED_ARGS: $expect 의 값 '$tok' 이 범위(1~64) 밖입니다"; return @()
        }
      } else {
        if ($tok -notmatch '^[0-9]+(\.[0-9]+)?$') {
          Drop "BRIDGE_PROBED_ARGS: $expect 의 값 '$tok' 이 숫자가 아닙니다"; return @()
        }
        if ([double]$tok -lt 1 -or [double]$tok -gt 86400) {
          Drop "BRIDGE_PROBED_ARGS: $expect 의 값 '$tok' 이 범위(1~86400초) 밖입니다"; return @()
        }
      }
      $out += @($expect, $tok); $expect = $null; continue
    }
    switch -Regex ($tok) {
      '^--(workers|max-workers|worker-idle-sec|ai-timeout)$' { $expect = $tok }
      '^--refresh-caps$' { $out += $tok }
      default { Drop "BRIDGE_PROBED_ARGS: '$tok' 은 허용 목록에 없습니다"; return @() }
    }
  }
  if ($expect) { Drop "BRIDGE_PROBED_ARGS: $expect 에 값이 없습니다"; return @() }
  return $out
}
$ProbedArgs = Get-FilteredProbedArgs $ProbedArgsRaw
if ($ProbedArgs.Count -gt 0) { Say "러너 인자: $($ProbedArgs -join ' ') (조사값)" }

if ($ProbedHandler -notin @('auto', 'none')) {
  Drop "BRIDGE_PROBED_HANDLER='$ProbedHandler' 는 auto|none 중 하나여야 합니다"
  $ProbedHandler = 'auto'
}

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
$AgentUrl  = "$Base/static/agent/bridge_agent.py"
# Windows 는 CA 를 시스템 저장소에 넣지 않고도 요청별로 신뢰시키기 어려워, curl.exe 가 있으면
# --cacert 로 프로세스 한정 신뢰를 쓴다(POSIX 판과 같은 계약).
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue

#: 네이티브 명령을 **종료코드와 stderr 원문까지 회수**해서 부른다.
#:
#: `$ErrorActionPreference` 를 함수 스코프에서만 **'Continue'** 로 둔다 — 전역을 바꾸지 않으므로
#: 이 절 밖의 fail-fast 계약은 그대로다. 세 값의 차이가 여기서 전부 문제가 된다(실측 2026-08-31,
#: 실 Windows PowerShell 5.1):
#:   · 'Stop'             → 네이티브 stderr 가 NativeCommandError 로 **던져진다** (`2>$null` 로도
#:                          못 막는다 — Test-PyOk 이 같은 함정을 이미 겪었다).
#:   · 'SilentlyContinue' → 그 ErrorRecord 가 **조용히 버려진다**. curl 이 exit 60 으로 죽었는데
#:                          회수된 메시지 길이가 **0** 이었다. 그러면 실패 보고가 "사유: (없음)"
#:                          이 되어, 사유를 모으려고 만든 이 구조가 무의미해진다.
#:   · 'Continue'         → 던지지도 버리지도 않는다. 유일하게 맞는 값이다.
function Invoke-NativeCapture([string]$exe, [string[]]$argv) {
  $ErrorActionPreference = 'Continue'
  # ⚠ 실행 **자체가** 실패하면($exe 부재·권한 거부) $LASTEXITCODE 는 건드려지지 않는다. 0 으로
  #   초기화해 두면 그것이 «성공» 으로 읽힌다 — 실측: 없는 파이썬 경로로 불렀는데 Get-RemoteFile
  #   이 via=python 을 **성공 반환**했다(받은 파일은 없었다). 그래서 초기값을 실패값으로 둔다.
  $global:LASTEXITCODE = 127
  $lines = @()
  try {
    foreach ($item in (& $exe @argv 2>&1)) {
      # 네이티브 stderr 는 ErrorRecord 로 온다. PowerShell 의 장식(위치·CategoryInfo·틸데 밑줄)이
      # 아니라 **원문만** 꺼낸다 — 그 장식은 로케일 의존이라 문자열 패턴으로 걸러낼 수도 없다.
      if ($item -is [System.Management.Automation.ErrorRecord]) { $lines += $item.Exception.Message }
      else { $lines += [string]$item }
    }
  } catch {
    $lines += $_.Exception.Message
  }
  $code = $LASTEXITCODE
  $out  = (($lines | Where-Object { $_ }) -join ' / ').Trim()
  # 사용자에게 보일 한 줄이라 길이를 자른다. 단 **양끝을 남긴다** — curl 의 핵심 토큰
  # (CERT_TRUST_*)은 첫 줄에 오고, 파이썬 트레이스백의 핵심(SSLCertVerificationError 등)은
  # **마지막 줄**에 온다. 앞만 남기면 파이썬 실패에서 정작 원인이 잘려 나간다(실측).
  if ($out.Length -gt 480) {
    $out = $out.Substring(0, 240) + ' … ' + $out.Substring($out.Length - 240)
  }
  return [pscustomobject]@{ Code = $code; Out = $out }
}

#: 종료코드 0 은 «파일이 왔다» 를 뜻하지 않는다. 실행 실패·부분 수신·0바이트를 성공으로 읽지
#: 않도록 **실물**을 본다 — 아래 체크섬 대조는 서버가 값을 주지 않으면 건너뛰므로(그 경로에서는
#: 이것이 유일한 확인이다) 이 검사가 그 구멍을 메운다.
function Test-Downloaded([string]$p) {
  if (-not (Test-Path -LiteralPath $p)) { return $false }
  try { return ((Get-Item -LiteralPath $p).Length -gt 0) } catch { return $false }
}

#: 윈도우 동봉 curl 의 **폐기검사 하드 실패**를 푸는 옵션 하나를 고른다 (사용자 제보 2026-08-31).
#:
#: 윈도우 기본 curl.exe 의 TLS 백엔드는 **Schannel** 이다(실측: curl 8.13.0 (Windows)
#: libcurl/8.13.0 Schannel). Schannel 의 CertGetCertificateChain 은 체인을 세운 **뒤** 폐기
#: 상태를 조회하는데, 우리 사내 CA 에는 조회할 곳이 없다 — CRL 배포점도 OCSP(AIA)도 없다
#: (실측: root·leaf 양쪽 모두 그 확장이 부재). 그래서 결과가 «알 수 없음» 이고 curl 은 그것을
#: **실패로 본다**:
#:
#:     curl: (60) schannel: CertGetCertificateChain trust error CERT_TRUST_REVOCATION_STATUS_UNKNOWN
#:
#: 이것은 CA 신뢰 실패도 네트워크 실패도 아니다 — --cacert 는 이미 먹었고 체인도 섰다. 그런데
#: 종전 안내문이 "CA 신뢰 또는 네트워크를 확인하세요" 라, 사용자는 멀쩡한 두 곳을 뒤지게 됐다.
#: POSIX 판은 OpenSSL curl 이라 폐기검사를 기본으로 하지 않아 이 결함이 없다 — **Windows 전용
#: divergence** 이고, 그래서 이 옵션은 이쪽에만 둔다(bridge_setup.sh 에 같은 것을 넣지 않는다).
#:
#: 순서에 의미가 있다. --ssl-revoke-best-effort 는 «조회할 곳이 없거나 못 닿을 때만» 넘어가고,
#: CRL 에 닿았는데 revoked 라고 하면 **여전히 멈춘다**. --ssl-no-revoke 는 폐기검사를 통째로
#: 끈다. 그래서 잃을 것이 없는 쪽을 먼저 쓰고, 그 옵션을 모르는 구형 curl(7.70 미만)에서만
#: 내려간다. 완화하는 것은 폐기검사뿐이고, CA 지문 pin 과 러너 체크섬 대조는 그대로다.
function Get-CurlRevokeArgs([string]$exe) {
  # 모르는 옵션이면 curl 이 **파싱 단계에서** exit 2 로 죽는다 — 네트워크를 타지 않는 감지다.
  foreach ($f in @('--ssl-revoke-best-effort', '--ssl-no-revoke')) {
    if ((Invoke-NativeCapture $exe @($f, '--version')).Code -eq 0) { return @($f) }
  }
  return @()
}
$CurlRevokeArgs = if ($curl) { Get-CurlRevokeArgs $curl.Source } else { @() }
if ($curl -and $CurlRevokeArgs.Count -eq 0) {
  Drop 'curl 이 폐기검사 완화 옵션(--ssl-revoke-best-effort / --ssl-no-revoke)을 모릅니다. Schannel 이면 여기서 막힐 수 있어 파이썬 경로로 넘어갑니다'
}

#: 파일 하나를 받는 **단일 경로**. 최초 수신과 체크섬 재시도가 각자 구현하던 것을 모은다 —
#: 갈라져 있던 동안 재시도 쪽에는 $LASTEXITCODE 검사가 **아예 없어서**, 실패한 재시도가 조용히
#: 통과하고 바로 다음 대조가 "러너 체크섬이 다릅니다" 로 **오진**했다(실제 원인은 수신 실패).
#:
#: 순서: curl(--cacert, 프로세스 한정 신뢰) → 파이썬(--ca 와 **같은 신뢰 경로**). 둘 다 실패면 멈춘다.
#: 파이썬이 «폴백 하나 더» 가 아닌 이유: 러너는 아래에서 --ca $CaPath 로 **파이썬 TLS** 를 쓴다.
#: 다운로드만 다른 평가기(Schannel)로 하면 신뢰 경로가 둘로 갈리고, 이번 결함이 정확히 그
#: 갈라짐이었다 — 한쪽만 죽었다. 파이썬으로도 못 받으면 러너도 못 뜨므로 실패가 정직해진다.
#:
#: ⚠ **Invoke-WebRequest 를 폴백으로 두지 않는다.** IWR 은 $CaPath 를 보지 않고 **OS 신뢰
#:   저장소**로 검증한다 — 즉 우리가 pin 한 CA 와 무관하게 통과할 수 있다. 실측(2026-08-31,
#:   실 Windows): 사내 CA 가 이미 CurrentUser\Root·LocalMachine\Root 에 있는 머신에서,
#:   **무관한 CA 를 pin 해도 IWR 이 다운로드를 성공**시켰다. 그것을 «curl·파이썬 실패 시의
#:   폴백» 으로 두면 신뢰 실패가 조용한 성공으로 바뀐다 — 이 스크립트가 지킨다고 말하는 것이
#:   바로 그 pin 이다. 종전 코드는 IWR 을 «curl 부재 시» 에만 썼고, 그 자리는 지금 파이썬이
#:   대신한다(파이썬은 pin 을 지키고, 위에서 이미 3.8+ 를 확보했으므로 반드시 존재한다).
#:
#: 실패 시 각 경로의 사유를 **모아서** throw 한다. 하나만 말하면 다음 사람이 또 헤맨다.
function Get-RemoteFile([string]$url, [string]$dest) {
  $why = @()

  if ($curl) {
    $r = Invoke-NativeCapture $curl.Source (@('-fsS') + $CurlRevokeArgs + @('--cacert', $CaPath, '-o', $dest, $url))
    if ($r.Code -eq 0 -and (Test-Downloaded $dest)) { return 'curl' }
    $msg = if ($r.Out) { $r.Out } else { '(메시지 없음 — 받은 파일도 없습니다)' }
    $why += "  · curl (exit $($r.Code)): $msg"
  }

  # 파이썬 — 러너가 쓰는 것과 **같은** 신뢰 앵커. 코드는 파일로 떨어뜨려 argv 로 넘긴다
  # (-c 로 넘기면 PowerShell 5.1 의 네이티브 인자 따옴표 처리에서 깨지는 조합이 있다).
  $dlPy = Join-Path $Home_ '_download.py'
  try {
    # ASCII — 본문이 전부 ASCII 이고, BOM 없는 순수 바이트가 파이썬에 가장 안전하다.
    Set-Content -Encoding ASCII -Path $dlPy -Value @(
      'import ssl, sys, urllib.request',
      'url, dest, ca = sys.argv[1], sys.argv[2], sys.argv[3]',
      'ctx = ssl.create_default_context(cafile=ca)',
      'req = urllib.request.Request(url, headers={"User-Agent": "mysql-ai-bridge-setup"})',
      'with urllib.request.urlopen(req, context=ctx, timeout=60) as r:',
      '    body = r.read()',
      'with open(dest, "wb") as f:',
      '    f.write(body)'
    )
    $r = Invoke-NativeCapture $Py @($dlPy, $url, $dest, $CaPath)
    if ($r.Code -eq 0 -and (Test-Downloaded $dest)) { return 'python' }
    $msg = if ($r.Out) { $r.Out } else { '(메시지 없음 — 받은 파일도 없습니다)' }
    $why += "  · python (exit $($r.Code)): $msg"
  } finally {
    Remove-Item -Force -Path $dlPy -ErrorAction SilentlyContinue
  }

  throw ($why -join "`n")
}

Say '러너를 받는 중…'
try {
  $via = Get-RemoteFile $AgentUrl $AgentTmp
} catch {
  $why = "$_"
  Die @"
러너를 받지 못했습니다. 시도한 경로와 사유:
$why

  · CERT_TRUST_REVOCATION_STATUS_UNKNOWN 이면 CA·네트워크가 아니라 윈도우 폐기검사(Schannel)
    문제입니다. curl 이 구형이면 갱신하거나, 파이썬 경로가 열리도록 파이썬을 확인하세요.
  · 그 밖의 사유면 사내망 연결과 CA 지문을 확인하세요.
"@
}
# 정상 경로는 조용히 지난다. 폴백이 걸렸다는 사실만 말한다 — 지원 문의 때 이 한 줄이 원인 구간을
# 바로 가른다(curl 이 막혔는가, 아니면 서버·네트워크인가).
if ($via -ne 'curl') { Say "  (curl 경로가 막혀 $via 로 받았습니다)" }

if ($AgSha) {
  $got = Sha256File $AgentTmp
  if ($got -ne $AgSha.ToLower()) {
    # 롤링 배포 교대 중일 수 있다 — 1회 재시도 후에도 다르면 멈춘다.
    Say '체크섬 불일치 — 배포 교대 중일 수 있어 1회 재시도합니다.'
    Start-Sleep -Seconds 20
    try {
      Get-RemoteFile $AgentUrl $AgentTmp | Out-Null
    } catch {
      # 종전에는 재시도 실패를 **검사하지 않아** 낡은 파일이 그대로 남고, 그 다음 대조가
      # "체크섬이 다릅니다" 로 오진했다. 수신 실패는 수신 실패라고 말한다.
      $why = "$_"
      Die "러너를 다시 받지 못했습니다. 시도한 경로와 사유:`n$why"
    }
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
# 핸들러가 띄우는 러너도 **같은 인자**를 받아야 한다 — 여기만 빠지면 브라우저 버튼으로 뜬
# 러너와 이 스크립트가 띄운 러너가 다르게 동작하고, 그 차이는 화면에서 구분되지 않는다
# (sh 판의 «RUNNER_ARGS» 와 같은 자리). 검증을 통과한 값만 들어온다.
$BakedArgs = @()
if ($AiArgs.Count -gt 0)     { $BakedArgs += $AiArgs }
if ($ProbedArgs.Count -gt 0) { $BakedArgs += $ProbedArgs }
if ($ExtraArgs) { $BakedArgs += ($ExtraArgs -split '\s+' | Where-Object { $_ }) }
# 리터럴 배열로 굽는다. 각 토큰을 작은따옴표로 감싸고 내부 «'» 는 이중화한다(PowerShell 규칙).
$BakedArgsLiteral =
  if ($BakedArgs.Count -gt 0) {
    '@(' + (($BakedArgs | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ', ') + ')'
  } else { '@()' }
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
# ── 러너 최신화 (TASK-20260902T100000 · 신뢰 앵커 수정 TASK-20260902T170000) ───
# 종전 이 스크립트는 디스크에 있는 파일을 그대로 다시 띄워, 「업데이트 필요」에서 눌러도 같은
# 낡은 러너가 떴다. 그래서 여기서 배포본을 받아 갈아 끼운다.
#
# ⚠ **받는 수단은 파이썬이다 — «Invoke-WebRequest» 가 아니다.** IWR 은 «rootCA.crt» 를 보지
#   않고 **OS 신뢰 저장소**로 검증하는데, 이 설치기는 CA 를 그 저장소에 넣지 않는다(위
#   «Get-RemoteFile» 이 curl --cacert·파이썬으로만 받는 것과 같은 이유). 그래서 IWR 판은
#   사내 CA 머신에서 **TLS 에서 실패**했고 그 실패를 «catch { }» 가 삼켰다 — 갱신이 조용히
#   일어나지 않는 상태로 굳는다. 사용자 화면의 「다시 실행했지만 러너 파일이 그대로입니다」가
#   정확히 이것이었다(재설치해도 같은 자리로 돌아오므로 막다른 길이 된다, 사용자 제보
#   2026-09-02). POSIX 판(«launch.sh»)과 «agent/selfupdate.py» 는 처음부터 pin 을 지켰고,
#   **이 축 하나만 예외**였다.
#
#   파이썬을 쓰는 것은 «폴백 하나 더» 가 아니다 — 러너가 바로 아래에서 «--ca» 로 쓰는 것과
#   **같은 신뢰 평가기**다. 다운로드만 다른 평가기(Schannel)로 하면 신뢰 경로가 둘로 갈린다.
#
# ⚠ 실패는 **종전 동작**으로 떨어진다: 못 받았거나·너무 작거나·문법이 깨졌으면 있던 파일을
#   그대로 쓴다(갱신하려다 멀쩡한 러너를 못 띄우게 만드는 것이 가장 나쁜 결말이다). 다만
#   **조용히** 떨어지지는 않는다 — 이 창은 숨겨져 있어 사유를 남기지 않으면 증거가 하나도
#   없고, 그 침묵이 이번 결함을 여러 cycle 동안 살려 뒀다.
#
# ⚠ 전체를 «try { } catch { }» 로 감싼다 — «$ErrorActionPreference = 'SilentlyContinue'» 는
#   non-terminating error 만 억제한다. 경로·권한·디스크에서 나오는 **terminating** 예외는
#   그대로 스크립트를 끝내고, 그러면 아래 기동에 닿지 못해 **갱신하려다 러너를 못 띄운다**.
#   기존 계약(«test_autolaunch_runner»)이 잠근 것이 정확히 이것이고, 이 cycle 이 한 번 그
#   방어를 걷어냈다가 그 테스트에 잡혔다. 진단은 «catch» 가 아니라 **«else» 분기**에서
#   남긴다 — 흔한 실패(수신·검증 실패)는 거기로 오고, «catch» 는 드문 사고의 최후 방어다.
`$new = Join-Path `$home_ ('.bridge_agent.new.' + `$PID)
`$dl  = Join-Path `$home_ ('.selfupdate_dl.' + `$PID + '.py')
try {
  # 크기·문법 검사까지 받는 쪽에서 끝낸다 — «agent/selfupdate.py» 와 같은 바닥(20000B)·같은 검사.
  # ASCII 로 쓴다(BOM 없는 순수 바이트가 파이썬에 가장 안전하다 — 위 «Get-RemoteFile» 과 동일).
  Set-Content -Encoding ASCII -Path `$dl -Value @(
    'import ast, ssl, sys, urllib.request',
    'url, dest, ca = sys.argv[1], sys.argv[2], sys.argv[3]',
    'if not url.lower().startswith("https://"):',
    '    sys.exit("refuse plaintext: " + url)',
    'class NoRedirect(urllib.request.HTTPRedirectHandler):',
    '    def redirect_request(self, *a, **k):',
    '        return None',
    'ctx = ssl.create_default_context(cafile=ca)',
    'op = urllib.request.build_opener(',
    '    urllib.request.HTTPSHandler(context=ctx), NoRedirect)',
    'req = urllib.request.Request(url, headers={"User-Agent": "mysql-ai-bridge-launch"})',
    'with op.open(req, timeout=30) as r:',
    '    if int(getattr(r, "status", 0) or 0) != 200:',
    '        sys.exit("http status")',
    '    body = r.read()',
    'if len(body) < 20000:',
    '    sys.exit("too small: %d bytes" % len(body))',
    'ast.parse(body)',
    'with open(dest, "wb") as f:',
    '    f.write(body)'
  )
  # ⚠ 초기값은 **실패값**이다. ErrorActionPreference 가 SilentlyContinue 인 이 스크립트에서
  #   «파이썬을 실행조차 못 한 경우»(CommandNotFound)는 예외가 삼켜지고 LASTEXITCODE 가
  #   직전 값을 그대로 유지한다 — 그 직전 값은 위 --check 게이트 때문에 **반드시 0**, 즉
  #   정확히 «성공» 이다. 이 파일의 Invoke-NativeCapture 가 같은 함정을 실측하고 같은
  #   처방을 쓴다(«없는 파이썬으로 불렀는데 성공 반환»).
  `$global:LASTEXITCODE = 127
  `$why = & '$Py' `$dl '$Base/static/agent/bridge_agent.py' `$new ``
    (Join-Path `$home_ 'rootCA.crt') 2>&1
  `$dlOk = (`$LASTEXITCODE -eq 0)
  # 받는 쪽의 검사와 **독립적으로** 한 번 더 본다(POSIX 판이 같은 자리에서 그렇게 한다).
  # 여기까지 통과한 것만 다음 기동에서 실행된다.
  if (`$dlOk -and (Test-Path `$new) -and ((Get-Item `$new).Length -ge 20000)) {
    `$global:LASTEXITCODE = 127
    & '$Py' -c 'import ast,sys; ast.parse(open(sys.argv[1],"rb").read())' `$new 2>&1 | Out-Null
    `$dlOk = (`$LASTEXITCODE -eq 0)
  } else { `$dlOk = `$false }
  if (`$dlOk) {
    Move-Item -Force `$new (Join-Path `$home_ 'bridge_agent.py')
  } else {
    Add-Content -Path (Join-Path `$home_ 'launch.log') -Value (
      '[bridge-launch ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') +
      '] 러너 갱신 실패 — 있던 파일로 계속합니다: ' + (`$why -join ' '))
  }
} catch { }
Remove-Item -Force -ErrorAction SilentlyContinue `$new, `$dl
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { `$_.CommandLine -like '*bridge_agent.py*' } |
  ForEach-Object { Stop-Process -Id `$_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process -WindowStyle Hidden -FilePath '$Py' -ArgumentList (@(
  (Join-Path `$home_ 'bridge_agent.py'), '--base', '$Base',
  '--ca', (Join-Path `$home_ 'rootCA.crt'), '--resume') + $BakedArgsLiteral)
"@ | Set-Content -Encoding UTF8 $LaunchPs

if ($ProbedHandler -eq 'none') {
  # 실패가 아니라 **선택**이다. 실측된 조합이 그렇다: 러너가 WSL 안에 있으면 여기(Windows)에
  # 등록해 봐야 그 러너를 띄우지 못한다. 헛된 등록물을 남기는 대신 안 하는 것을 고를 수 있다.
  Say '핸들러 등록을 건너뜁니다 (BRIDGE_PROBED_HANDLER=none — 이 머신에서는 등록해도'
  Say '  러너에 닿지 않는다는 조사 결과). 러너가 꺼지면 이 명령을 다시 실행하세요.'
} else {
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
}

# ── 4. 연결 확인 → 상주 ──────────────────────────────────────────────────────
Say '연결을 확인하는 중…'
$env:BRIDGE_TOKEN = $Token
& $Py $AgentPath --base $Base --ca $CaPath --check
$CheckCode = $LASTEXITCODE
# ⚠ **연결과 AI 는 다른 축이다** (사용자 제보 2026-09-01). 종전에는 러너가 AI 를 못 찾으면
#   연결 확인 앞에서 죽었고, 이 자리가 그것을 통째로 「연결 확인에 실패했습니다. 토큰이
#   만료됐다면…」 으로 옮겼다 — 토큰도 CA 도 네트워크도 멀쩡한 사용자가 그 셋을 뒤졌다.
#   러너는 이제 exit 4 로 「연결은 됐는데 답할 AI 가 없다」를 따로 말한다.
if ($CheckCode -eq 4) {
  Die @"
서버 연결은 정상인데, 이 컴퓨터에서 쓸 수 있는 AI 를 찾지 못했습니다.

  이 브리지는 이 컴퓨터에 설치된 AI 프로그램(Claude Code 등)으로 답합니다.
  · 아직 설치하지 않았다면 설치한 뒤 이 명령을 다시 실행하세요.
  · 이미 설치했다면 설치 폴더가 시스템 PATH 에 등록되지 않은 것입니다 — 설치 프로그램의
    「PATH 에 추가」 를 켜고 다시 설치하거나, 컴퓨터를 다시 로그인한 뒤 실행하세요.
  (위에 러너가 찾아본 위치가 모두 적혀 있습니다.)
"@
}
if ($CheckCode -ne 0) {
  Die '연결 확인에 실패했습니다. 토큰이 만료됐다면 웹에서 [연결 명령 복사] 를 다시 누르세요.'
}

# 이미 떠 있는 러너는 정리한다. 둘이 같은 계정으로 대기하면 같은 질문을 두 번 집으려다 한쪽이
# 409 로 하차하고, 그 왕복이 사용자 계정 토큰을 태운다.
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like '*bridge_agent.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Say '러너를 상주시킵니다…'
# 조사값 → 사람 값 순. 같은 인자가 겹치면 뒤가 이기므로 **사람이 이긴다**(POSIX 판과 동일).
$argv = @($AgentPath, '--base', $Base, '--ca', $CaPath, '--resume')
if ($AiArgs.Count -gt 0)     { $argv += $AiArgs }
if ($ProbedArgs.Count -gt 0) { $argv += $ProbedArgs }
if ($ExtraArgs) { $argv += ($ExtraArgs -split '\s+' | Where-Object { $_ }) }
$proc = Start-Process -PassThru -WindowStyle Hidden -FilePath $Py -ArgumentList $argv
Start-Sleep -Seconds 2
if ($proc -and -not $proc.HasExited) {
  Say "완료. 웹 화면의 표시가 '내 AI 대기 중' 으로 바뀌면 질문을 보낼 수 있습니다."
  # ⚠ 이 창은 숨겨져 있고 stderr 를 아무 데도 잇지 않는다 — 종전에는 그래서 **Windows 러너의
  #   사고에 증거가 하나도 없었다**. 이제 러너가 자기 로그 파일을 직접 쓴다(POSIX 는 셸이
  #   stderr 를 이어 주고, 러너가 같은 파일인지 확인해 이중 기록을 피한다).
  Say "  로그   : $Home_\bridge.log          (사람이 읽는 줄)"
  Say "  감사    : $Home_\bridge.events.jsonl (한 줄 = 한 사건. 문제 보고 시 이 파일을 보내"
  Say "            주세요 — 토큰은 기록 전에 지워집니다)"
  Say "  종료   : Stop-Process -Id $($proc.Id)"
  Say "  해제   : Remove-Item -Recurse '$Home_'  +  Remove-Item -Recurse 'HKCU:\Software\Classes\mysql-ai-bridge'"
} else {
  Die '러너가 바로 종료됐습니다. 토큰·CA·파이썬 버전을 확인하세요.'
}
