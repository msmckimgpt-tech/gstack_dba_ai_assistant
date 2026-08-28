# Run — TASK-20260828T240000-connect-gate (P0-AB · P0-AC)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) + **Windows-browser** (PB-0008, bind-mount 격리 인스턴스)
- **대상**: 브리지 연결 게이트(요청 차단·입력 잠금·가이드) + 원클릭 연결(LLM 비경유)

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전량 (feature-0002·0003·0014·0020·0023·0041·0043·0008) | **PASS** (exit 0) |
| ruff | All checks passed |
| feature-0043 스위트 | **PASS** — 신규 32건(`test_connect_gate.py`) + 기존 계약 9건 갱신 |

## PB-0008 실 Windows 브라우저 검증

라이브 서비스 **무접촉**. 라이브 web 이미지(`mysql-ai-web:f814f9a1`) + 이 브랜치의
`routers/`·`static/` 만 bind-mount 한 별도 컨테이너(`web-verify-gate`, `https://localhost:18098`).
세션은 `bin/win-browser.py session-login` (bootstrap_admin).

### ① 잠금 — 토큰 있음 + 러너 꺼짐

```
{"gate":true, "gateHidden":false,
 "title":"내 AI가 실행 중이 아닙니다",
 "desc":"연결은 되어 있지만 답변할 프로그램이 꺼져 있습니다. 다시 실행하면 입력창이 열립니다.",
 "btn":"내 AI 실행하기",
 "inputDisabled":true, "locked":true, "sendAria":"true",
 "conn":"AI 대기 안 함"}
```

두 상태 구분이 실제로 작동한다 — 토큰이 있으므로 "연결하세요" 가 아니라 **"실행하세요"** 다.

서버 판정도 같은 값을 말한다 (`/api/ai/connect/status`):

```
{"connected":true, "listening":false, "ready":false,
 "bridge_mode":true, "compose_blocked":true}
```

### ② 해제 — `compose_blocked: false` 가 되는 순간

러너를 실제로 띄우려면 사용자 머신의 AI CLI 와 새 토큰이 필요해 무인으로 완결할 수 없다.
대신 **그 응답이 왔을 때 화면이 어떻게 되는가**를 실제 브라우저에서 구동했다(`fetch` 를
잠시 가로채 `compose_blocked:false` 를 돌려주고 `visibilitychange` 발화):

```
{"gateHidden":true, "inputDisabled":false, "locked":false,
 "sendAria":null, "conn":"내 AI 대기 중"}
```

**"연결 완수 후 활성화" 가 실제로 일어난다.** 이 경로는 P0-V 가 라이브에서 겪은 결함
(상태는 바뀌었는데 아무도 다시 그리지 않아 버튼이 박제)의 재발 지점이라 직접 구동해 확인했다.

### ③ 원클릭 연결 모달

`[연결 준비]` → 명령 생성 확인:

```
osLabel        Windows PowerShell        (navigator 로 자동 선택)
launchHidden   false                     ([내 AI 실행] 노출 = protocol URL 있음)
status         "준비했습니다. 이 창을 닫으면 다시 볼 수 없습니다."

Windows: iwr -UseBasicParsing -Uri 'http://<host>/static/agent/bridge_setup.ps1' -OutFile bridge_setup.ps1
         if ((Get-FileHash bridge_setup.ps1 -Algorithm SHA256).Hash -ne 'EB2DBF9D5AD1DB1DB5B8…') { throw … }
         $env:BRIDGE_BASE=…; $env:BRIDGE_TOKEN='mat_…'; $env:BRIDGE_CA_SHA256='F5:B9:C5:81:5C:9B:47:…';
         $env:BRIDGE_AGENT_SHA256='1bce1c5c4fbd003a1ac3337947e376ab4487ff7d46d0ee749364​0db2b2fa8719'; .\bridge_setup.ps1

POSIX  : curl -fsS -o bridge_setup.sh http://<host>/static/agent/bridge_setup.sh
```

무결성 값 3종(설치 스크립트·CA·러너)이 전부 실려 있다. 탭 전환도 동작(`macOS·Linux` ↔ `Windows`).
AI 지시문은 `<details>` 로 접힌 보조 경로(「터미널을 쓸 수 없다면 — AI에게 맡기기」).

## 실 브라우저에서만 드러난 결함 2건 (그 자리에서 수정)

1. **연결 상태 칩이 한 번도 보이지 않았다** — P0-T 가 "상시 표시" 로 넣은 `#aiConnState` 는
   `.composer-footer` 안에 있는데, 그 footer 는 status·hint 가 비고 provider 상태점이 숨겨지면
   통째로 `display:none` 이 된다(`:has()` 규칙). **그게 평상시 화면이다.**
   실측: `footerDisp:"none"` / `connDisp:"inline-block"` — 칩은 살아 있는데 부모가 접혀 있었다.
   → 접힘 조건에 `:has(.ai-conn.hidden)` 추가. 재검증에서 `footerDisp:"flex"` · 칩 가시.
   **넣은 것과 보이는 것은 다른 사실이다** — 소스 검사로는 영원히 안 잡히는 부류.

2. **안내 패널이 입력창 아래에 있었다** — 사용자는 잠긴 입력창을 먼저 만나 고장으로 읽은 뒤에야
   사유를 본다. 다른 배너(provider 제한·실행시간 연장)와 같은 자리(입력창 위)로 옮겼다.
   실측: `gateTop 757 < boxTop 831`.

## 코드 판독으로 드러난 결함 1건 (엣지)

3. **설치 스크립트가 부트스트랩 데드락에 걸린다** — 엣지는 `/trust/*` **만** 평문 HTTP 로 열고
   나머지는 https 로 301 한다. 그런데 이 스크립트가 하는 첫 일이 사내 CA 를 받아 신뢰시키는
   것이므로, 스크립트 자신을 https 로만 주면 CA 가 없는 머신은 **그것부터 받을 수 없다**.
   → Caddyfile `http://` 블록에 `bridge_setup.sh`/`.ps1` **두 파일만** 명시 추가
   (`/static/*` 통째로 열지 않는다 — 예외가 감당하려던 것보다 넓어진다).

## 미수행 (정직 표기)

- **실 러너 기동 후의 해제** — 사용자 머신의 AI CLI + 새 `mat_` 토큰이 필요해 AI 가 무인으로
  완결할 수 없다. ②에서 *서버 응답이 왔을 때의 화면 거동*은 실제 브라우저로 구동했으나,
  *러너가 실제로 떠서 하트비트가 도달하는 것*은 사용자 확인 항목이다.
- **프로토콜 핸들러 등록·기동** — 같은 사유(설치 스크립트를 실제 머신에서 실행해야 한다).
  등록 실패 시의 거동(연결은 되고 버튼만 안 됨 + 그 사실 고지)은 스크립트 소스에 고정하고
  테스트로 잠갔다.
- **서버 409 차단 경로의 라이브 왕복** — bootstrap_admin 은 토큰을 보유하고 있어 그 상태를
  만들려면 토큰을 폐기해야 하고, 그건 라이브 세션을 건드린다. 계약은 테스트 2건
  (`test_server_rejects_when_no_token_and_stores_nothing` ·
  `test_block_response_carries_the_axes_to_the_frontend`)이 고정한다.
- **정적 자산 캐시** — 검증 중 브라우저가 구 `chat.css` 를 잡고 있어 캐시버스트 후 재확인했다.
  배포본은 `inject_asset_stamp.py` 가 스탬프를 새로 주입하므로 이 문제가 없다.
