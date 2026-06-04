# Windows 브라우저 테스트 브리지 — 1회 setup

> feature-0008-windows-browser-testing. AI 작업자가 WSL 안에서 **실제 Windows
> 브라우저**를 자동 구동(CDP)하여 웹/UI 를 검증하기 위한 브리지 설정. 환경당
> **1회만** 하면 된다. 이후는 `python3 bin/win-browser.py ...` 로 동작.

## 왜 필요한가

WSL2 의 Chrome remote-debugging 포트(CDP)는 보안상 **항상 `127.0.0.1` 에만
바인딩**된다. NAT 모드 WSL2 에서는 WSL → Windows loopback 직결이 불가하므로
브리지가 필요하다. 아래 3가지 중 하나.

| 모드 | 관리자 | WSL 재시작 | 보안 노출면 | 비고 |
|---|---|---|---|---|
| **0. 무권한 auto-relay (권장)** | 불필요 | 불필요 | vEthernet(WSL) IP 한정 | `launch` 가 자동 기동. Windows python 필요. 별도 setup 0 단계 |
| **A. NAT + portproxy relay** | 필요(1회) | 불필요 | vEthernet(WSL) 서브넷 한정 | 영속 relay 가 필요할 때. 관리자 netsh |
| **B. mirrored networking** | 불필요 | 필요(1회) | 인바운드 규칙 없음 (loopback 공유) | loopback 공유. WSL 전역 네트워킹 영향 |

**기본은 옵션 0** — `python3 bin/win-browser.py launch` 한 번으로 Chrome 기동 +
무권한 userspace relay 자동 기동(Windows python 으로 vEthernet IP:9223 → 127.0.0.1:9222
forward)까지 끝난다. **관리자도 WSL 재시작도 불필요.** Windows python 이 없거나
영속 relay 를 원하면 옵션 A/B.

`python3 bin/win-browser.py doctor` 가 현재 브리지 상태 + Windows python 가용성을 진단한다.

> **보안 (필독)** — CDP 는 **인증이 없는 브라우저 원격제어 채널**이다. 노출되면 열린
> 페이지·쿠키·세션 탈취, 임의 JS 실행이 가능하다. 따라서:
> - 가능하면 **옵션 B (mirrored)** 를 쓴다 — 인바운드 방화벽 hole 이 전혀 없다.
> - 옵션 A 를 쓰면 `win-browser-setup.ps1` 이 relay 를 `0.0.0.0`(LAN) 이 아닌
>   **vEthernet(WSL) IP 에만** 바인딩하고 방화벽을 `Private` 프로파일 + WSL 서브넷으로
>   한정한다. **수동 `netsh ... listenaddress=0.0.0.0` 로 열지 말 것.**
> - 드라이버는 **전용 프로필**(`%LOCALAPPDATA%\win-browser-cdp`)을 쓴다 — 사용자 실제
>   Chrome 쿠키/세션과 격리된다. **이 테스트 프로필로 민감 계정에 로그인하지 말 것.**
> - 검증 종료 후 relay 를 닫으려면 `win-browser-setup.ps1 -Remove` (옵션 A). 상시 유지가
>   부담되면 세션 시작 시 setup, 종료 시 `-Remove` 패턴 권장.

## 사전 준비 (공통)

```bash
# host 에 playwright (python) — connect_over_cdp 만 쓰므로 브라우저 다운로드 불요
pip install playwright          # 이미 설치돼 있으면 skip
# (PEP 668 externally-managed 환경이면: pip install --user playwright 또는 venv)
```

Windows 측에 Chrome 또는 Edge 가 설치돼 있어야 한다 (표준 경로 자동 탐색;
비표준 경로면 `WIN_BROWSER_CHROME` 환경변수로 `.exe` 지정).

**옵션 0(권장)을 쓰려면 Windows 측 python 이 필요하다** (무권한 relay 구동용 — Microsoft
Store stub 이 아닌 실제 설치본). `python3 bin/win-browser.py doctor` 의 `win_python`
필드로 탐지 결과 확인. 비표준 경로면 `WIN_BROWSER_WIN_PYTHON` 으로 지정.

## 옵션 0 — 무권한 auto-relay (권장, 별도 setup 불요)

```bash
python3 bin/win-browser.py launch --url https://localhost:18080/
# → Chrome 기동 + 무권한 relay 자동 기동 + 해당 URL navigate. 끝.
python3 bin/win-browser.py down          # chrome + relay 함께 정리
```

`launch` 출력의 `"bridge_mode": "relay"` + `"relay": "relay started (... no-admin)"` 가
무권한 relay 가동을 의미. relay 만 따로 제어하려면 `relay-start` / `relay-stop`.
relay 는 vEthernet(WSL) IP 에만 바인딩되어 LAN 에 노출되지 않는다.

## 옵션 A — NAT + portproxy relay (권장)

**관리자 권한 PowerShell** 에서 1회 실행:

```powershell
# WSL 경로의 스크립트를 직접 실행 (<distro> = 배포판 이름)
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\<distro>\<...>\bin\win-browser-setup.ps1
```

스크립트가 하는 일:
1. `netsh portproxy` 추가: `0.0.0.0:9223 → 127.0.0.1:9222`
2. 방화벽 인바운드 규칙 추가 (TCP 9223)

teardown: `... win-browser-setup.ps1 -Remove`

## 옵션 B — mirrored networking (관리자 불요)

`%USERPROFILE%\.wslconfig` 에 추가:

```ini
[wsl2]
networkingMode=mirrored
```

그 후 (관리자 PowerShell/cmd 불요):

```powershell
wsl --shutdown
```

WSL 재시작 후 Windows `127.0.0.1:9222` 가 WSL 에서 `localhost:9222` 로 직결된다.
> 주의: mirrored 는 모든 WSL 배포판의 네트워킹에 영향을 준다. 기존 NAT 기반
> 설정(예: 다른 portproxy)이 있으면 옵션 A 를 권장.

## 검증

```bash
python3 bin/win-browser.py launch          # 실제 Windows Chrome 기동 (전용 프로필)
python3 bin/win-browser.py doctor          # "ok": true, bridge_mode: relay|mirrored 확인
python3 bin/win-browser.py goto --url http://localhost:18080/
python3 bin/win-browser.py screenshot --path /tmp/win-browser-shots/check.png
```

`doctor` 가 `"ok": true` 면 AI 자동 구동 준비 완료.

## AI 자동 구동 사용법

```bash
# 단발 조작
python3 bin/win-browser.py goto --url http://localhost:18080/login
python3 bin/win-browser.py type --selector "#email" --text "a@b.c"
python3 bin/win-browser.py click --selector "button[type=submit]"
python3 bin/win-browser.py screenshot --path /tmp/win-browser-shots/after_login.png

# 시나리오 일괄 실행 (권장 — 검증 증거 일괄 생성)
python3 bin/win-browser.py run --scenario unit/feature-0008-windows-browser-testing/src/scenario.example.json

# 본 드라이버가 띄운 인스턴스만 종료 (사용자 일반 브라우저 보존)
python3 bin/win-browser.py down
```

검증 흐름·완료 게이트는 **PB-0008** (`playbooks/PB-0008-windows-browser-verification.md`)
참조. 환경 분류(CLI / WSL-headless / **Windows-browser**)와 게이트 규칙은 AGENTS.md
§15.4 + 각 feature `docs/TEST.md` §3.

## Playwright MCP (대화형 in-loop, 선택)

같은 브리지/Chrome 위에서 **Claude Code(VSCode/CLI)에 native 브라우저 도구**(browser_snapshot
a11y 트리 · browser_click/type/navigate 등)를 제공하려면 Playwright MCP(`@playwright/mcp`)를
attach 한다. `bin/playwright-mcp.sh` 가 relay endpoint 를 자동 해석해 `--cdp-endpoint` 로 띄운다.

```bash
# 0) 브리지 먼저 성립 (Chrome + 무권한 relay)
python3 bin/win-browser.py launch
# 1) Claude Code 에 등록 (project scope) — 첫 사용 시 승인 필요
claude mcp add --scope project playwright -- bash "$PWD/bin/playwright-mcp.sh"
#    (또는 repo/.mcp.json 커밋본 사용. VSCode 확장은 같은 config 를 읽고 /mcp 로 활성화)
```

**역할 분담**: MCP = 대화형 탐색·조작(모델 루프에서 직접, a11y 스냅샷 토큰 효율). win-browser.py
= 브리지 성립 + 반복 가능한 시나리오/완료 게이트 증거(TEST.md §3)/CI. 둘 다 같은 실제 Windows
브라우저에 attach. MCP 도 CDP 로 붙으므로 로컬 브라우저 바이너리 불요.

> **Claude for Chrome 는 미채택** — Anthropic 의 Chrome 확장(2025-12 GA)은 사용자의 실제
> Chrome 을 수동 UI 로 조작하는 소비자용 에이전트이며 **MCP/프로그래매틱 API 가 없어** 본
> delegated-dev/CDP 워크플로에 부적합(헤드리스·스크립트 불가). 대화형 보조가 필요하면 사용자가
> 별도로 쓸 수 있으나 본 프로젝트 자동화에는 통합하지 않는다.

## Troubleshooting

| 증상 | 원인 / 조치 |
|---|---|
| `doctor` → `playwright: missing` | `pip install playwright` |
| `doctor` → `chrome: null` | Chrome/Edge 미설치 또는 `WIN_BROWSER_CHROME` 미지정 |
| `launch` → `bridge_unreachable` | relay 미구성 → 옵션 A/B setup. 방화벽 인바운드 확인 |
| `run` → `cdp_connect_failed` | Chrome 가 `--remote-allow-origins=*` 없이 떠 있음 → `down` 후 `launch` 재기동 |
| 포트 충돌 | `WIN_BROWSER_CDP_PORT` / `WIN_BROWSER_RELAY_PORT` 로 변경 (ps1 의 `-CdpPort`/`-RelayPort` 와 일치시킬 것) |
