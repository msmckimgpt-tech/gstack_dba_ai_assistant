---
doc_type: DQA_RESEARCH
initiative: onboarding-accessibility
created_at: 2026-09-02
focus: 최초 사용자 온보딩 접근성 — 터미널 무지·AI CLI 부재·GUI 편향 3축 (상용 서비스 벤치마크)
status: draft
---

# 개선 리서치 — onboarding-accessibility

> 사용자 요청(2026-09-02): *"프로젝트 내 서비스를 각 사용자들이 처음 사용하는 입장에서 접근성이
> 너무 떨어지는 것으로 확인되었습니다. — powershell, wsl 자체를 모르는 사람 / 각 ai cli가 설치되지
> 않은 사람 / GUI 위주, 텍스트형 동작을 고려하지 않는 사람"*
>
> 본 문서는 **현 온보딩 경로의 코드 실측** + **상용 서비스 웹 리서치**를 대조해 해소안 후보를
> 정리한다. 구현 로드맵은 `/_dqa:improve_listup` 이 본 문서를 입력으로 산출한다 (ROADMAP.md).

---

## 0. 현재 상태 실측 — 「최초 사용자가 통과해야 하는 벽」

**결론부터**: 신규 사용자가 첫 답변 1건을 받기까지 통과해야 하는 관문이 **5겹**이고, 그중 **3겹이
터미널을 요구**하며, **1겹은 유료 AI 구독 보유를 전제**한다. 어느 하나라도 없으면 이 서비스는
**답변을 0건 반환**한다 — 서버측 LLM 이 fail-closed 로 차단돼 있어 대체 경로가 없기 때문이다.

| # | 관문 | 근거 (코드/문서) | 터미널 | GUI 대안 |
|---|---|---|---|---|
| W1 | 사내 사설 Root CA 를 PC 신뢰 저장소에 설치 (`.company.local` 내부 도메인이라 공인 CA 발급 불가) | `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md` REQ-0283·REQ-0285 | 스크립트 실행 1회 | `/trust/` 다운로드 페이지 (스크립트는 여전히 실행) |
| W2 | 로그인 → 질문 전송 → **답변 대신 「AI 연결하기」 안내** | `FUNCTION.md` P0-F·P0-G | — | ✅ 모달 |
| W3 | `/ai/connect` [연결 준비] → **셸 명령 3줄 복사 → 터미널 붙여넣기** | `routers/oauth_as.py:1056-1058` (`posix`/`windows`) | **필수** | ❌ (최초 1회) |
| W4 | 러너 실행에 **Python 3.8+** 필요 | `bridge_setup.ps1:191`, `bridge_setup.sh:140` | winget 설치 동의 프롬프트 | ❌ |
| W5 | 머신에 **AI CLI 설치 + 로그인** 필요 — 없으면 `exit 4` 로 기동 거부 | `agent/lifecycle.py:725-728` (상주 거부) · `:714-717` (`--check`) · `agent/discovery.py:193` | **필수** | ❌ |

추가 상시 조건:
- **부팅 자동 등록을 하지 않는다** — `bridge_setup.sh` 헤더 「하지 않는 일」. 재부팅하면 러너가
  사라지고, 비개발자에게는 *"어제는 됐는데 오늘 안 된다"* 로 나타난다.
- **서버측 LLM 은 코드 기본값이 차단** — `shared/llm_gate.py`. `.env` 미배포 환경에서도 잠기도록
  안전측 기본값으로 설계됨(의도적). 즉 **연결에 실패한 사용자를 위한 폴백 티어가 존재하지 않는다.**
- **BYOK(개인 API 키 붙여넣기) 경로가 없다** — `/api/api-vault/options` 는 *모델 카탈로그*이지
  키 보관소가 아니다 (`routers/system.py:448`). 추론 경로는 「사용자 머신의 AI CLI」 단 하나다.

### 0.1 이미 보유한 자산 (재발명 금지선)

온보딩을 다시 설계할 때 **아래는 이미 있다**. 새로 만들지 말고 확장한다.

- **원클릭 재실행 스킴**: `mysql-ai-bridge://start?token=…` 프로토콜 핸들러 + 웹 [내 AI 실행] 버튼
  (`compose_launch_commands()` 의 `protocol` 키). 브라우저 샌드박스를 넘어 로컬 프로세스를 띄우는
  유일한 구현 수단. **단 최초 1회 설치 이력(`BridgeLastOs`)이 있어야 발동한다.**
- **러너 자기 갱신**: 스킴 런처가 기동 직전 최신본으로 교체 (`agent/selfupdate.py`, `try_self_update`).
- **무결성 계약**: CA 지문·러너 체크섬·설치 스크립트 체크섬을 명령 안에 실어 대조하고, 어긋나면 중단.
  평문 HTTP 부트스트랩(`/trust/*`, `/static/agent/bridge_setup.*`)의 위험을 이 대조가 덮는다.
- **하트비트 채널**: 30초 주기로 러너→서버 (`RunnerCapabilities`·`RunnerOs`·`superseded`). 설치·기동
  진행 상태를 웹에 표시할 **배관이 이미 깔려 있다.**
- **등록형(무설치) 경로**: MCP 설정에 URL + `Authorization: Bearer` 헤더만 넣는 방법 A
  (`compose_connect_handoff()`). 파이썬·터미널·상주 프로세스가 **전부 불필요**하다.
  현재는 `/ai/connect` 화면의 접힌 `<details>` 「터미널을 쓸 수 없다면」 안에 있다
  (`static/ai-connect.html:66-76`).
- **OS 자동 판정**: 러너 신고 기반 기본 탭 선택 (`agent_os` → `BridgeLastOs`, 2026-09-01).

---

## 1. 사용자가 지목한 3축의 코드상 착지점

| 사용자 표현 | 실제로 막히는 지점 | 현재 사용자가 보는 것 |
|---|---|---|
| **"powershell, wsl 자체를 모르는 사람"** | W1·W3·W4 — 세 관문 모두 셸 실행이 유일 경로 | 명령 3줄이 담긴 코드 블록. 「터미널」이 무엇인지·어디서 여는지는 화면이 말하지 않는다 |
| **"각 ai cli가 설치되지 않은 사람"** | W5 — `pick_ai()` 가 `None` → `exit 4` | *"이 컴퓨터에서 쓸 수 있는 AI 를 찾지 못했습니다"* + Claude Code 설치 문서 링크. **그 링크 끝에는 유료 구독 결제가 있다** (Pro/Max/Team/Enterprise 필요) |
| **"GUI 위주, 텍스트형 동작을 고려하지 않는 사람"** | 실패 진단이 **러너 로그(터미널)에만** 남는 구간 | 실측된 최악 사례: 능력 협상 실패로 **240초 침묵** — 그동안 하트비트·로그·질문 수신 0인데 설치 스크립트는 2초 뒤 「완료」를 선언했다 (`REPORT.md` TASK-20260902T140000 ②) |

### 1.1 부수 발견 — 온보딩 표면 드리프트 1건 (실측)

`ollama` 가 **설치 스크립트·서버 안내의 허용 목록에는 남아 있는데, 러너는 더 이상 지원하지 않는다.**

| 위치 | ollama 포함 여부 |
|---|---|
| `bridge_setup.sh:152` `_KNOWN_AI_CLIS` | **포함** |
| `bridge_setup.ps1:206` `$KnownAiClis` | **포함** |
| `routers/oauth_as.py` `_PROBED_AI_ALLOWLIST` | **포함** |
| `agent/runtimes.py` `_RUNTIME_SPECS` | **제거됨** (P0-Z6.1, 사용자 결정 2026-09-01) |

`_CLI_ADAPTERS` 는 `_RUNTIME_SPECS` 파생이므로 `dict(_CLI_ADAPTERS).get("ollama")` 는 `None` 이다.
결과: `BRIDGE_PROBED_AI='ollama'` 를 채운 사용자(또는 그 사용자의 AI)는 **설치 단계는 통과하고
런타임에서 실패**한다. `oauth_as.py` 주석이 스스로 못박은 계약 —
*"설치 스크립트의 `_KNOWN_AI_CLIS` 와 **같은 목록**이어야 한다"* — 은 지켜졌으나, **양쪽 모두 러너와
갈렸다.** 세 자리를 함께 좁혀야 한다.

---

## 2. 상용 서비스 벤치마크 (웹 리서치, 2026-09)

### 2.1 동종 — DB 자연어 질의 어시스턴트

| 제품 | 추론 위치 | 사용자 설치물 | 온보딩 |
|---|---|---|---|
| Snowflake **Cortex Analyst** | 서버(완전관리형) · REST 엔드포인트 | **없음** | 시맨틱 뷰 저작이 유일한 준비물 |
| Databricks **Genie** (2026: Genie Agents) | 서버 | **없음** | 데이터 분석가가 Genie space 를 구성, 비즈니스 사용자는 채팅만 |
| **Outerbase** | 서버 | 없음 | 셋업 30분 미만 · 마찰 「중」 |
| **Vanna.AI** | 자체 호스팅(파이썬 프레임워크) | 있음(개발자) | *"비기술 사용자를 위한 것이 아니다"* 로 명시 |
| **Chat2DB** | 데스크톱 클라이언트 | GUI 앱 | DBeaver/TablePlus 계열 GUI 설치 |
| **본 서비스** | **사용자 머신** | **CA + Python + AI CLI + 상주 러너** | 터미널 필수 |

> **관찰**: 상용 동종은 예외 없이 **추론을 서버에 두고 사용자 설치물을 0으로 만든다.**
> 본 서비스가 반대 방향에 선 것은 계정 쿼터 소진 사고(2026-08-07)에 대한 **의도적 설계 결정**이며
> (`shared/llm_gate.py` 도입 배경), 그 대가가 지금의 온보딩 벽이다. 즉 이것은 버그가 아니라
> **트레이드오프**이고, 접근성 개선은 그 트레이드오프를 **어디까지 되사올 것인가**의 문제다.

### 2.2 로컬 에이전트/러너를 사용자 PC 에 얹는 상용 패턴

| 제품 | 설치 방식 | 터미널 필요 |
|---|---|---|
| **Tailscale** | Windows **MSI** / 트레이 앱 · 무인 설치 스위치 제공 · Intune 배포 문서 | ❌ |
| **Ollama** | 원클릭 설치 마법사 (5분 미만) | ❌ (설치는) |
| **LM Studio** | GUI 앱 — 모델 브라우저·원클릭 다운로드·로컬 OpenAI 호환 서버(:1234) | ❌ |
| **GitHub Actions self-hosted runner** | 셸 스크립트 + `svc.sh install` 로 **서비스 등록** | ✅ (개발자 대상) |
| **본 서비스 러너** | 셸 명령 3줄 · **자동시작 없음** | ✅ |

핵심 격차 2개:
1. **패키징** — 상용은 서명된 네이티브 설치 관리자(MSI/PKG). 본 서비스는 `curl | 검증 | sh`.
2. **수명** — 상용은 서비스/트레이 앱으로 로그온 시 자동 기동. 본 서비스는 재부팅 시 소멸.

### 2.3 「개인 AI 를 서비스에 연결」하는 2026 표준 경로

| 경로 | 설치 | 우리 서비스 적용 가능성 |
|---|---|---|
| **MCPB(Desktop Extensions, `.mcpb`)** — Chrome `.crx`/VS Code `.vsix` 계열 번들. 더블클릭 또는 [Browse and Install] 로 **원클릭 설치**, `claude_desktop_config.json` 편집 불필요. Anthropic 이 *"비개발자가 명령줄로 MCP 서버를 설치하지 못하는 문제"* 를 위해 만든 포맷 | 없음(호스트 앱이 처리) | **✅ 높음** — 로컬 실행이라 사설 CA·LAN 도달 가능 |
| **Remote MCP 커스텀 커넥터** — Settings → Connectors 에 **URL 만 등록**, OAuth. 로컬 설치 완전 0. 조직 단위 프로비저닝 가능 | 없음 | **❌ 낮음** — 콜백이 `https://claude.ai/api/mcp/auth_callback` 이고 **Anthropic 인프라가 우리 서버로 아웃바운드**해야 하는데, `.company.local` LAN + 사설 CA 라 도달 불가 |
| **MCP 설정에 URL + Bearer 헤더 직접 기입** (= 본 서비스 방법 A) | 없음(설정 편집) | **✅ 이미 구현** — 단 `NODE_EXTRA_CA_CERTS` 필요 |
| **Claude Code 데스크톱 앱** — macOS/Windows **GUI 설치 관리자**, Node.js·npm·CLI 별도 설치 불필요. Code/Cowork/Chat 3탭, *"No terminal required"*. 커넥터·플러그인을 GUI 로 추가 | GUI 설치 | **✅ 높음** — 단 `claude` **CLI 는 별도 설치**이므로 *러너* 경로는 이것만으로 충족되지 않는다 |

> **가장 중요한 발견**: 우리가 이미 가진 「등록형 무설치 경로(방법 A)」가 상용 표준
> (MCPB/커넥터)과 정확히 같은 계열인데, **화면에서는 접힌 `<details>` 안 마지막에 있다.**
> 상용은 이것을 1급 경로로 두고 CLI 를 부가 경로로 둔다. 순서가 뒤집혀 있다.

### 2.4 사용자 AI 가 아예 없을 때 — BYOK · AI 게이트웨이

- **BYOK 는 2026 엔터프라이즈 표준 기능**이 되었다. 제품 표면은 동일하게 두고 **자격증명 출처만
  바꾸는** 패턴(관리형=SMB, BYOK=엔터프라이즈)이 일반적. 구매·규제 심사에서 「키 보관 주체」가
  쟁점이 되기 때문.
- **LiteLLM virtual keys** — 키별 예산·RPM/TPM·모델 allowlist·만료·팀 격리. **2026-08-07 쿼터 소진
  사고의 근본 원인(계정 1개 공유)에 정확히 대응하는 표준 도구**다. 본 프로젝트는 이미
  `litellm bedrock-gateway` 를 운영 중이므로 **인프라가 이미 있다.**
- **Anthropic ToS 경계 (중요)**: *"one human, one subscription, one beneficiary"* — 개인 Pro/Max
  좌석으로 **타인의 요청을 라우팅하는 순간 API 키로 전환해야 한다.** OAuth 인증은 개인의 통상
  사용 전용. 조직 단위 제공은 Team/Enterprise 좌석 또는 API 키(Commercial Terms)가 정규 경로.
  → **현 아키텍처(각자 자기 머신·자기 좌석)는 이 선을 지키고 있다.** 반면 「서버가 한 좌석으로
  전원에게 서비스」로 되돌리는 처방은 ToS 위반이므로 **채택 불가**. 폴백 티어를 만든다면
  **API 키(Commercial Terms)** 또는 **Team/Enterprise 좌석 지급**이어야 한다.

### 2.5 온보딩 활성화 벤치마크

- 온보딩 플로우 **20단계 초과 시 완주율 30~50% 하락**, **10단계 이상은 완주 18%**.
  권장 구간은 **핵심 3~7단계 + 나머지는 progressive disclosure**.
- 첫 가치(first value) 도달 목표 **2~5분**, 활성화 이벤트는 첫 로그인 후 24시간 내.
- **첫 주에 시작에 어려움을 겪으면 75% 가 이탈.** 14일 내 첫 가치 도달 고객은 12개월 잔존 80%+,
  30일 내 미도달은 35~50%.

> 본 서비스의 현 경로를 위 척도로 재면: 관문 5겹 · 각 관문의 하위 단계까지 세면 **10단계 초과** ·
> 첫 가치까지 **분(分) 단위가 아니라 「AI 구독 결제 → 설치 → 로그인」의 시(時) 단위**가 될 수 있다.

---

## 3. Findings

### F-001 · 등록형(무설치) 경로를 1급 경로로 승격
- **dimension**: functional
- **source_kind**: commercial (Anthropic MCPB · Remote MCP 커넥터)
- **source**: https://claude.com/docs/connectors/building/mcpb · https://www.anthropic.com/engineering/desktop-extensions
- **무엇을**: `/ai/connect` 화면의 경로 순서를 뒤집는다. ① **"내 AI 앱에 주소만 등록"**(현 방법 A —
  파이썬·터미널·상주 프로세스 0) ② 터미널 명령 ③ AI 위임 지시문. 현재 ①은 접힌 `<details>`
  「터미널을 쓸 수 없다면」 안에 마지막으로 있다 (`ai-connect.html:66-76`).
- **현재 상태**: 구현은 되어 있고 **노출 순서만 뒤집혀 있다** — `compose_connect_handoff()` 가 이미
  방법 A 를 첫 순서로 조립한다. 화면이 그것을 「예외 경로」로 표시한다.
- **정직한 한계** (같이 표시해야 함): AI 앱을 **켜 두어야** 답이 온다. 상주 러너는 자리를 비워도
  처리한다 (P0-K). 두 경로는 대체가 아니라 **트레이드오프**이므로 화면이 그렇게 말해야 한다.
- **raw_impact**: ★5
- **confidence**: high
- **note**: 코드 변경 최소(프론트 재배치 + 문안). DOM id 13개 불변 계약 유지 (P0-G). 웹 자산
  변경이므로 **PB-0008 실 Windows 브라우저 시각검증 필수**
  (`<project_root>/FIRST_REQUEST.md` `visual_verification_scope: always`).

### F-002 · 러너를 단일 실행파일로 패키징 — Python 전제 제거
- **dimension**: structural
- **source_kind**: commercial (Tailscale MSI · Ollama 설치 마법사 · LM Studio)
- **source**: https://tailscale.com/docs/install/windows/msi
- **무엇을**: `bridge_agent.py`(stdlib 전용 단일 파일)를 **PyInstaller/`zipapp`** 으로 동결해
  `.exe`/Mach-O 단일 바이너리로 배포. 관문 **W4(Python 3.8+)가 통째로 사라진다.**
- **현재 상태**: 없음 — `bridge_setup.ps1:144-191` 이 winget 으로 Python 을 **설치해 주는** 우회를
  이미 넣었는데, 이는 벽을 낮춘 것이지 없앤 것이 아니다.
- **raw_impact**: ★5
- **confidence**: high
- **note**: 「stdlib 전용 단일 파일」 사용자 계약은 유지된다 — 소스는 여전히 `src/agent/` 18모듈이고
  `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` 가 번들을 만든다 (2026-09-02).
  동결 단계를 그 **빌드 파이프라인 뒤에 붙이면** 된다. ⚠ 체크섬 계약(`_runner_checksum`)의 대상이 `.py` 에서 바이너리로 바뀌므로
  `/static/agent/` 서빙·`bridge_runner_verify` 배포 게이트를 함께 옮겨야 한다. OS·아키텍처별
  산출물이 늘어난다(win-x64 · win-arm64 · darwin-universal · linux-x64).

### F-003 · 네이티브 설치 관리자(.msi / .pkg) — 터미널 0 회 온보딩
- **dimension**: functional
- **source_kind**: commercial (Tailscale · Ollama · LM Studio)
- **무엇을**: 웹에서 내려받아 **더블클릭**하면 ① 사내 Root CA 신뢰(W1) ② 러너 배치(W2·W4)
  ③ `mysql-ai-bridge://` 스킴 등록 ④ **로그온 자동시작 등록** ⑤ 토큰 수령을 한 번에 끝낸다.
  토큰은 설치 파일에 굽지 않고 **설치 직후 스킴 링크로 전달** (기존 `protocol` 경로 재사용).
- **현재 상태**: 없음. 스킴 핸들러·자기갱신·무결성 대조 등 **구성요소는 전부 있고 포장만 없다.**
- **raw_impact**: ★5
- **confidence**: med
- **note**: ⚠ **코드 서명이 없으면 SmartScreen/Gatekeeper 경고**가 뜨고, 그것은 W1(사설 CA 경고)과
  같은 부류의 새 벽이다 — 서명 인증서 확보 또는 F-004(사내 배포)와 **묶어서만** 효과가 있다.
  ⚠ 스킴 URL 에 토큰이 실리는 기존 함정(사용자 활성화 끊김 — P0-K)을 그대로 상속한다.

### F-004 · Intune/GPO 사내 배포 — 사용자 온보딩 자체를 0단계로
- **dimension**: operational
- **source_kind**: commercial (Microsoft Intune 표준 운영)
- **source**: https://learn.microsoft.com/en-us/intune/device-configuration/certificates/pkcs-profiles · https://www.intuneget.com/blog/deploy-winget-apps-to-intune
- **무엇을**: ① **Trusted Root 인증서 프로파일**로 사내 CA 를 전 단말에 푸시 → **W1 소멸**.
  ② 러너를 **Win32 앱(.intunewin)** 또는 사내 winget 소스로 무인 배포 → **W3·W4 소멸**.
  ③ AI CLI/데스크톱 앱도 같은 경로로 배포 → **W5 완화**.
- **현재 상태**: 없음 — 현재는 사용자 각자가 `/trust/` 에서 스크립트를 받아 실행 (REQ-0285).
- **raw_impact**: ★5 (**단일 최대 레버**)
- **confidence**: high
- **note**: **코드 변경이 거의 없다 — 운영·조직 결정**이다. 사내 MDM 이 있는 환경이면 F-002·F-003
  보다 먼저 검토할 것. 없으면 F-003 으로 대체. 서명된 PowerShell 스크립트 요구가 있는 조직이면
  코드 서명 인증서가 선행 조건.

### F-005 · AI 를 보유하지 않은 사용자를 위한 폴백 티어
- **dimension**: functional
- **source_kind**: commercial (BYOK 표준 · LiteLLM virtual keys)
- **source**: https://docs.litellm.ai/docs/proxy/virtual_keys · https://docs.litellm.ai/docs/proxy/users · https://www.augmentcode.com/guides/byok-enterprise-agent-rollouts
- **무엇을**: 현재 `pick_ai()` → `None` → `exit 4` **막다른 길**을 티어로 바꾼다.
  - **(a) 조직 API 키 + 사용자별 virtual key** — 이미 운영 중인 `litellm bedrock-gateway` 에
    사용자별 예산·RPM 상한을 건다. **2026-08-07 쿼터 소진(계정 1개 공유)의 재발을 막는 것이
    정확히 이 도구의 목적**이며, `AGENT_SERVER_LLM_ENABLED` 게이트를 「전부 아니면 전무」에서
    「사용자별 상한이 있는 폴백」으로 정밀화한다.
  - **(b) Claude Team/Enterprise 좌석 지급** — 현 아키텍처를 그대로 두고 W5 만 해소. ToS 정합.
- **현재 상태**: 없음. `shared/llm_gate.py` 는 **불리언 게이트 하나**다(의도적 fail-closed).
- **raw_impact**: ★5
- **confidence**: high
- **note**: ⚠ **§12.3 Major~Critical — 외부 비용 발생 + 보안 경계 변경이므로 사람 승인 필수.**
  ⚠ 게이트를 여는 순간 P0-T/P0-Z3 가 다룬 **모델 선택기 3분기**(차단+신고있음/차단+신고없음/
  게이트해제)에 4번째 상태가 생긴다 — 세 곳(카탈로그·조작면·전송)을 함께 봐야 한다.
  ⚠ **ToS 경계**: 서버가 개인 Pro/Max 좌석으로 타인 요청을 처리하는 형태는 **금지** — (a)는 API 키
  (Commercial Terms), (b)는 각자 좌석이어야 한다.

### F-006 · 설치·기동 진행 상태를 웹 화면이 끝까지 표시
- **dimension**: functional
- **source_kind**: commercial (SaaS 온보딩 체크리스트 · progressive disclosure)
- **source**: https://www.digitalapplied.com/blog/customer-onboarding-time-to-value-2026-saas-metrics-framework
- **무엇을**: 5관문(CA · 설치 · 런타임 · AI 감지 · 연결)을 웹의 **체크리스트 5행**으로 그리고,
  각 행에 ✅/⏳/❌ + **실패 시 다음 행동 1개**를 붙인다. 데이터는 **이미 오는 하트비트**
  (`RunnerCapabilities`·`RunnerOs`·능력협상 결과)에 필드를 더해 싣는다.
- **현재 상태**: 부분 — 「대기 중」 칩과 모달 성공 조건(`listening && !stale`)은 있으나, **실패
  사유가 러너 로그(터미널)에만 남는 구간**이 실측됐다: 능력 협상 240초 침묵 동안 설치 스크립트는
  2초 뒤 「완료」를 선언 (`REPORT.md` TASK-20260902T140000 ②). 그 cycle 이 하트비트를 앞으로
  당겨 완화했으나, **화면이 단계를 그리는 것은 아직 아니다.**
- **raw_impact**: ★4
- **confidence**: high
- **note**: GUI 편향 사용자에게 **가장 직접적인 처방**이다 — "터미널을 안 봐도 된다" 를 참으로 만든다.
  웹 자산 변경 → PB-0008 필수.

### F-007 · Claude Code 데스크톱 앱을 「AI 없음」 안내의 1순위로
- **dimension**: functional
- **source_kind**: commercial (Anthropic)
- **source**: https://code.claude.com/docs/en/desktop-quickstart
- **무엇을**: `_no_ai_message()`(`agent/discovery.py:193`)와 `/ai/connect` 의 「AI 가 없을 때」 안내가
  현재 가리키는 곳은 **CLI 설치 문서**(`_AI_SETUP_URL = .../claude-code/setup`)다. 비개발자에게는
  **GUI 설치 관리자**가 정답이다 — 데스크톱 앱은 Node.js·npm·CLI 별도 설치 없이 설치되고
  *"No terminal required"* 를 표방한다.
- **⚠ 정확히 구분해야 할 사실**: 데스크톱 앱만 설치해도 **`claude` CLI 는 생기지 않는다**(공식 문서
  명시: *"To use `claude` from the terminal, install the CLI separately"*). 따라서 데스크톱 앱은
  **러너 경로(W5)를 충족하지 않고**, **F-001 의 등록형 경로**로 안내해야 맞다. 두 경로를 뭉뚱그리면
  사용자는 설치를 마치고도 러너가 안 뜨는 상태를 만난다.
- **현재 상태**: 안내가 CLI 문서 한 곳만 가리킨다.
- **raw_impact**: ★4
- **confidence**: high
- **note**: 코드 변경 소(小) — 문안·링크. 단 **분기 정확도가 생명**이다(위 ⚠). 구독 요건(Pro/Max/
  Team/Enterprise)도 함께 표시해야 「설치했는데 Code 탭이 잠김」을 막는다.

### F-008 · 로그온 자동시작 등록
- **dimension**: functional
- **source_kind**: commercial (Tailscale 트레이 앱 · GitHub runner `svc.sh install`)
- **무엇을**: 러너를 작업 스케줄러(Windows) / LaunchAgent(macOS) / systemd user unit(Linux)에 등록.
- **현재 상태**: **의도적으로 하지 않음** — `bridge_setup.sh` 헤더 「하지 않는 일 · 부팅 자동 등록」.
  근거는 「사용자 머신에 상주물을 남기지 않는다」는 절제이며, 그 자체는 옳은 판단이었다.
- **raw_impact**: ★4
- **confidence**: med
- **note**: ⚠ **기존 설계 결정의 명시적 번복**이므로 `docs/DECISIONS.md` ADR 경유가 맞다.
  절충안: **기본 꺼짐 + 설치 시 체크박스**(사용자 동의 1회). 토큰이 세션 결합이라 재부팅 후
  자동 기동해도 **로그아웃하면 무효**라는 성질이 안전판이 된다.

### F-009 · 공인 인증서 도달성 확보 — W1 제거 + 클라우드 커넥터 개방
- **dimension**: structural
- **source_kind**: commercial (Remote MCP 커넥터 요구사항)
- **무엇을**: 서비스 진입점을 **공인 CA 로 서명 가능한 도메인**(공인 서브도메인 + DNS-01 발급, 또는
  리버스 프록시)으로 옮기면 ① **W1(사설 CA 설치)이 통째로 사라지고** ② `claude.ai` 커스텀
  커넥터(**로컬 설치 완전 0**)가 처음으로 가능해진다.
- **현재 상태**: `.company.local` 내부 도메인 → 공인 CA 발급 불가가 **사설 CA 도입의 원인**
  (REQ-0283). 즉 이것이 W1 의 뿌리다.
- **raw_impact**: ★4 (성사 시), 실현 가능성은 조직 네트워크 정책에 종속
- **confidence**: low
- **note**: ⚠ **§12.3 Critical 후보** — 내부망 전용 서비스를 외부 도달 가능하게 만드는 것은 보안
  경계 변경이다. **인증·인가·WAF·감사 전면 재검토 없이는 진행 불가.** 「W1 만 없애고 외부
  도달은 열지 않는」 부분 채택(내부 DNS + DNS-01 와일드카드 인증서)도 가능하며 그쪽이 현실적이다.

### F-010 · AI CLI 허용 목록 3자리 정합 (드리프트 수정)
- **dimension**: structural
- **source_kind**: internal (실측)
- **무엇을**: `bridge_setup.sh:152` · `bridge_setup.ps1:206` · `oauth_as.py:_PROBED_AI_ALLOWLIST`
  에서 `ollama` 제거 — 러너 `_RUNTIME_SPECS` 는 P0-Z6.1 에서 이미 제거됨. 세 자리가 러너를
  **단일 출처로 삼도록** 회귀 테스트로 잠근다.
- **현재 상태**: §1.1 표 참조 — 설치는 통과하고 런타임에서 실패한다.
- **raw_impact**: ★2
- **confidence**: high
- **note**: 소(小)·저위험. 「목록이 세 곳에 손으로 복제돼 있다」는 구조가 원인이므로, 제거만 하고
  **동기화 테스트를 안 걸면 다음 런타임 추가 때 같은 드리프트가 재발**한다 (AGENTS.md §16.7 G10).

---

## 4. 마찰 축 ↔ 처방 매핑

| 사용자가 지목한 축 | 즉효 (小~中) | 근본 (大) |
|---|---|---|
| **터미널을 모른다** | F-001(등록형 1급 승격) · F-006(웹 진행 표시) | F-004(Intune 배포) → F-003(설치 관리자) → F-002(단일 실행파일) |
| **AI CLI 가 없다** | F-007(데스크톱 앱 안내 분기) · F-010(드리프트) | **F-005(폴백 티어)** — 유일한 근본 해소. §12 승인 필요 |
| **GUI 편향** | **F-006** · F-001 | F-003(더블클릭 설치) · F-008(자동시작) |

### 4.1 권장 착수 순서 (종속성)

```
[운영 트랙]  F-004(Intune)  ─── 조직 결정. 성사되면 F-002/F-003 우선순위 하락
                  │
[제품 트랙]  F-001 ──┬── F-006 ──┬── F-003 ──requires── F-002
             F-007 ──┘           └── F-008(ADR 선행)
                  │
[승인 트랙]  F-005 ──── §12 Major/Critical 사람 승인 ──── F-009(Critical, 별도 검토)

[정리]       F-010 (독립·즉시)
```

- **F-001 · F-006 · F-007 · F-010** 은 서로 독립이고 전부 코드 변경 소~중이다 → **1차 배치**.
- **F-002 → F-003** 은 순서 종속(패키징이 먼저).
- **F-005 · F-009** 는 사람 승인이 선행이며, 승인 없이는 착수하지 않는다.

---

## 5. 이 프로젝트가 상용 패턴을 그대로 쓸 수 없는 제약

로드맵 작성 시 **아래를 위반하는 항목은 자동 기각**이다.

| 제약 | 근거 | 무엇을 막는가 |
|---|---|---|
| C1. 서버 계정 LLM 은 fail-closed 차단이 **코드 기본값** | `shared/llm_gate.py` · 사용자 결정 2026-08-26 | "그냥 서버가 답하게 하자" 류 처방. 되돌리기는 **사용자 결정 사항**이며 F-005 도 승인 대상 |
| C2. LAN 전용 + 사설 CA | feature-0006 REQ-0283 | `claude.ai` 클라우드 커넥터(무설치 최단 경로). F-009 없이는 불가 |
| C3. 러너는 **사용자 머신 파일** — 서버 배포로 갱신 불가 | P0-Z6 실측(낡은 러너가 계속 오신고) | "러너를 고치면 끝" 류 처방. **집행은 서버 수신 지점에 둬야 한다** |
| C4. Anthropic ToS — 1인 1구독, 좌석 공유 금지 | https://anthropic.com/legal/terms | 서버가 한 좌석으로 전원 서비스하는 폴백. API 키/Team 좌석만 정규 경로 |
| C5. 웹/UI 변경은 **PB-0008 실 Windows 브라우저 시각검증 필수** | `<project_root>/FIRST_REQUEST.md` `visual_verification_scope: always` | 프론트 항목(F-001·F-006·F-007)의 완료 판정에 반드시 포함 |

---

## 6. 보류·기각

| 후보 | verdict | 사유 |
|---|---|---|
| 로컬 LLM(Ollama/LM Studio) 어댑터 복원으로 "AI 없음" 해소 | **기각** | P0-Z6.1 에서 사용자 결정으로 제거됨. 게다가 그 축은 *"고칠수록 결함을 만드는 자리"* 로 실증됨(캐시 가드 반전 결함). F-010 은 그 결정의 **잔재 정리**이지 복원이 아니다 |
| 브라우저 확장(WebExtension)으로 러너 대체 | **보류** | 확장은 임의 로컬 프로세스를 띄우지 못한다(native messaging host 를 또 설치해야 함) — 벽을 옮길 뿐 없애지 않는다 |
| 서버가 사용자 대신 AI 구독에 로그인 | **기각** | C4 ToS 위반 |
| `claude.ai` 커넥터 즉시 채택 | **보류 → F-009 종속** | C2. 네트워크·보안 경계 변경이 선행 |

---

## 7. 다음 단계 — **superseded by §9 (사용자 결정 2026-09-02)**

> 아래는 결정 **이전**의 제안이다. 기록으로 남긴다 — §9 가 무엇을 닫았는지 읽으려면 필요하다.

1. ~~**사용자 결정 필요 (블로킹)**~~ → §9 에서 응답됨
2. **승인 불요 · 즉시 착수 가능**: F-001 · F-006 · F-007 · F-010 — §9 이후에도 유효.
3. **로드맵화**: 본 문서를 입력으로 `ROADMAP.md` 산출 → **완료** (`./ROADMAP.md`).

---

## 9. 사용자 결정 (2026-09-02) — 범위 재확정

초판(§0~§7)은 온보딩 벽 5겹 전체를 다뤘다. 사용자 결정으로 **범위가 「AI 연결」 축 하나로 좁혀졌다.**

| 축 | 결정 | 본 문서에 미치는 영향 |
|---|---|---|
| 추론 주체 | **개인 AI(자기 계정) 방식 보존.** 서버 추론 복원은 **보류** | F-005 **보류**(기각 아님 — 되살아날 수 있다). 서버측 폴백 티어는 로드맵에서 제외 |
| 미터링 | 서버 추론 복원이 보류이므로 **해당 없음** | LiteLLM virtual key 항목 제외 |
| TLS 신뢰 (W1) | **논외** — 아직 배포 전이며 현재 병목이 아니다 | F-009 **논외**. 단 MCPB 번들은 `NODE_EXTRA_CA_CERTS` 를 manifest `env` 로 주입할 수 있어 **부수적으로** AI 클라이언트 측 CA 마찰을 흡수한다(그것을 목적으로 삼지는 않는다) |
| 사내 MDM 존재 여부 | 미응답 | F-004 **미판정 보류** — 존재하면 최대 레버라는 판단은 유효하나 확인 전까지 로드맵에 넣지 않는다 |
| 착수 순서 | **로드맵 먼저** | `./ROADMAP.md` 산출 |

> **사용자 원문**: *"기본적으로 자기 계정을 사용하는 방법은 보존되어야 합니다. 다만, 사용자가 이
> 방법으로 어떻게 손쉽게 접근할 수 있는지를 검토해주세요."* / *"현재 가장 큰 걸림돌은 'AI 연결'
> 입니다."*

### 9.0 2차 결정 (같은 날) — 네이티브 클라이언트 채택, MCPB 기각

> *"현재 서비스는 claude 뿐만 아니라, 다른 ai 모델을 모두 수용 가능해야 합니다. 혹시, 설치 가능한
> 클라이언트를 각 사용자 머신에 구성해두고 해당 머신에서 사용하려는 ai에 로그인 하는것만으로도
> 접근성을 향상시킬 수 있을까요? 클라이언트가 실제 종속성 대응(powershell/wsl 에서 러너 역할 수행,
> 로그인 oauth등 위임, 필요한 패키지 설치, 등등 모든 게이트) 하는 방법으로 해소할 수 있나요?"*

| 축 | 결정 | 영향 |
|---|---|---|
| 주 경로 | **네이티브 설치형 클라이언트** — MCPB(F-011)를 **대체** | F-011 **기각**. MCPB 는 Claude Desktop 전용이라 「모든 AI 수용」 요구를 원리적으로 만족하지 못한다 |
| 클라이언트 책임 범위 | **설치 + 로그인 대행** (최대 범위) | 벤더 CLI 설치기 실행 + 로그인 명령 대행 실행까지 |
| 코드 서명 | **미정 — 조사 필요** | ROADMAP 에서 ITEM-08 의 **하드 선행**으로 못박음. 미확보 상태에서 착수 금지 |
| 착수 방식 | **SPIKE 먼저** | SPIKE-02(타임박스 1 cycle)가 ITEM-08 spec 을 확정 |

### 9.0.1 ⚠ 이 결정이 부딪히는 하드 제약 — 2026년 3사 OAuth 차단

사용자가 제안한 넷 중 **셋은 허용, 하나는 3사가 모두 차단한 패턴**이다.

| 제안 | 판정 | 근거 |
|---|---|---|
| 러너 역할 수행 (PowerShell/WSL 대체) | ✅ | `claude -p` subprocess 호출은 2026-04 중순 **명시적 허용 확인** — 금지된 것은 "OAuth 토큰을 추출해 제3자 API 클라이언트에서 쓰는 것" |
| 필요한 패키지 설치 | ✅ | `bridge_setup.ps1:144-191` 이 winget 으로 Python 설치를 **동의 받고** 대행하는 선례 |
| 모든 게이트 대응 (CA·스킴·자동시작·토큰) | ✅ | 설치 관리자의 표준 역할 |
| 모든 AI 수용 | ✅ | 러너 `_RUNTIME_SPECS` 가 이미 claude·codex·gemini + P0-Z4 로 표 밖 CLI 지목 가능 |
| **로그인 OAuth «위임»** | ❌ **금지** | Anthropic 2026-02-20 약관 → **2026-04-04 차단**(OpenClaw·OpenCode 등) · Google 2026-02 Gemini CLI 토큰 프록시 금지 + **유료 Ultra 구독자 계정 대량 정지** · OpenAI 는 "automatically or programmatically" 제약(해석 모호) |

**해소**: 「위임」이 아니라 **「대행 실행」** — 클라이언트가 벤더의 공식 로그인 명령을 subprocess 로
띄우고 **진행 상황만 GUI 로 표시**한다. 토큰은 벤더 자격증명 저장소에만 남고 우리는 보지도
저장하지도 중계하지도 않는다. **사용자 체감은 동일**하다(버튼 클릭 → 브라우저 승인 → 끝).

> **경계는 「누가 토큰을 만지는가」다.** 현행 러너가 이미 허용 쪽에 있다는 것이 이 설계의 근거이자
> 안전판이다 — 클라이언트는 그 방식을 바꾸지 않고 껍데기만 씌운다.

**부수 확인 필요**: `claude -p` subprocess 호출이 2026-06-15부터 일반 구독 한도가 아니라 **Agent
SDK 크레딧 풀**에서 차감된다는 보고가 있다. 사용자 실질 한도에 직결되므로 SPIKE-02 항목 4 로 실측.

### 9.1 「AI 연결」 축의 근본 원인 — 우리는 **배포 포맷을 발명했다**

BYO-AI 를 보존한다는 전제에서 §0 의 벽을 다시 보면, W3·W4 와 재발성 마찰의 원인은 하나로 수렴한다:

> **연결을 우리가 만든 배포물(파이썬 상주 러너 + 셸 설치 스크립트 1,506줄)로 구현했다.**
> AI 클라이언트 생태계는 같은 문제를 위한 **1급 배포 포맷**을 이미 갖고 있고(MCPB `.mcpb` ·
> Claude Code 플러그인), 그 포맷은 **런타임 · 설치 UX · 설정 UI · 업데이트 채널을 함께 가져온다.**
> 우리는 그 넷을 전부 자체 구현했고, **넷 모두가 각각 마찰이 됐다.**

| 우리가 자체 구현한 것 | 포맷이 이미 주는 것 | 현재 마찰 |
|---|---|---|
| 셸 설치 스크립트 (`bridge_setup.sh` 837줄 + `.ps1` 669줄) | 더블클릭 / 드래그드롭 설치 UI | **W3 터미널 필수** |
| Python 3.8+ 확보 (winget 설치 대행까지) | **Node.js 가 Claude Desktop 에 동봉** — 별도 런타임 불요 | **W4** |
| 토큰 전달 (URL·환경변수·스킴, 1회 노출) | `user_config` 자동 설정 UI (민감정보 처리 포함) | 재발급 왕복 |
| 러너 갱신 (`try_self_update`·supersede·지문 대조) | 확장 버전·업데이트 채널 | **C3 / P0-Z6 4차 재발** |
| CA 주입 안내 (`NODE_EXTRA_CA_CERTS` 를 사람이) | manifest `env` 주입 | (TLS 논외이나 부수 해소) |

**Anthropic 공식 문서가 우리 사례를 정확히 MCPB 권장 케이스로 열거한다** — *"Access to systems
behind your firewall (… private databases)"* · *"Zero-trust compliance inside corporate network
boundaries"* · *"No cloud infrastructure, VPN configuration, or firewall rules"* ·
*"Organization-level admin controls"* · *"One-click install with bundled Node.js runtime, no
dependencies to manage"* · *"Full control over authentication, authorization, and audit logs"*.

### 9.2 그렇다고 러너가 사라지지는 않는다 — 축을 갈라야 한다

러너의 **고유** 존재 이유는 P0-K 한 줄이다: *"블로킹 대기는 AI 가 켜져 있는 동안만 동작한다.
자리를 비워도 처리하려면 상주 프로세스가 필요하다."*

| 사용 상황 | 필요한 것 | 등록형(MCPB) | 러너 |
|---|---|---|---|
| **지금 화면 앞에 있다** — 질문하고 답을 기다린다 | MCP 도구 접근 | ✅ 충분 (설치물 0) | ✅ (과잉) |
| **자리를 비웠다** — 나중에 답이 와 있기를 원한다 | 무인 pull 루프 | ❌ — MCP 서버는 도구만 제공하고, 답을 만드는 것은 사용자가 말을 걸어야 도는 세션이다 | ✅ 고유 |

**현재 결함은 이 두 축이 갈라져 있지 않다는 것이다.** 「지금 답 받기」만 원하는 사용자(대부분)도
무인 처리를 위해 만든 상주 러너의 설치 벽을 통과해야 한다. **필요하지 않은 사람에게 부과된
비용**이며, 이것이 「AI 연결이 가장 큰 걸림돌」의 구조적 정체다.

## 10. 신규 Findings (「AI 연결」 축)

### ~~F-011 · MCPB 번들(`.mcpb`)~~ — **기각 (사용자 결정 2026-09-02, §9.0)**

> **기각 사유**: Claude Desktop 전용이라 「모든 AI 수용」 요구를 원리적으로 만족하지 못한다.
> **네이티브 클라이언트(F-016)가 대체**한다. 아래는 기록 — 클라이언트가 코드 서명 부재로
> 좌초할 경우의 대안 후보이므로 지우지 않는다.

### F-011 (기각) · MCPB 번들(`.mcpb`) — 무터미널·무런타임 등록 경로
- **dimension**: structural
- **source**: https://claude.com/docs/connectors/building/mcpb
- **무엇을**: 얇은 stdio↔HTTP 프록시(Node + MCP SDK)를 `.mcpb` 로 패키징해 `/ai/connect` 에서
  배포. 사용자는 **더블클릭 → 설정 UI 에 토큰 붙여넣기 → 끝**. manifest `user_config` 가 서버
  주소·토큰 입력 UI 를 자동 생성하고(민감정보 처리 포함), `env` 로 `NODE_EXTRA_CA_CERTS` 를 준다.
- **현재 상태**: 없음. 등록형 경로는 사람이 JSON 을 손으로 편집하거나 AI 에게 시켜야 한다.
- **핵심 이득**: **W3(터미널)·W4(Python) 동시 소멸.** Node 는 Claude Desktop 이 들고 온다.
- **raw_impact**: ★5 / **confidence**: high
- **note**: ⚠ **Claude Desktop 전용**(macOS·Windows). codex·gemini 사용자는 미커버 → F-013.
  ⚠ 프록시는 여전히 「우리 코드」다 — 다만 배포·설치·설정 UI·업데이트를 포맷이 가져간다.

### F-012 · 비-러너 클라이언트의 연결 수명 — F-011 의 **전제**
- **dimension**: structural
- **source**: 코드 실측
- **무엇을**: 확장에 붙여넣은 토큰은 **최대 12시간 뒤 죽는다.** 수명 연장은
  `POST /api/ai/bridge_heartbeat` (`ai_tools.py:4661`) 가 `ExpiresAt` 를 미는 것으로만 일어나고
  (`oauth_store.heartbeat` :516, `HEARTBEAT_EXTEND_SEC`), **하트비트를 보내는 것은 러너뿐**이다.
  → MCPB 프록시가 30초 주기로 같은 엔드포인트를 호출하면 **서버 변경 없이** 수명이 유지되고,
  `/api/ai/connect/status` 의 `listening` 도 참이 된다.
- **⚠ 이 항목이 없으면 F-011 은 「하루 두 번 끊기는 확장」이 된다.** 하드 종속.
- **⚠ 최대 위험 — 러너 축출**: supersede 판정(`_stale_runner_yield_to`, `ai_tools.py:328`)은
  **하트비트 이력이 있는 행끼리 연결 순서(토큰 Id)로** 승자를 정한다. 프록시가 하트비트를
  시작하는 순간 「당사자」가 되어, 같은 계정에서 돌던 **사용자의 러너를 축출**할 수 있다.
  FUNCTION.md P0-K 가 *"하트비트를 모르는 등록형 MCP 클라이언트는 이 판정에 걸리지 않는다"* 로
  안전을 보장하던 전제를 F-012 가 **직접 깬다.** → 하트비트 payload 에 클라이언트 종류를
  선언하고 supersede 를 `runner` 끼리로 한정하는 가드가 **필수**.
- **raw_impact**: ★5 (F-011 의 전제) / **confidence**: high

### F-013 · Claude Code 플러그인 — CLI·비-Desktop 사용자 경로
- **dimension**: functional
- **source**: https://www.morphllm.com/claude-code-marketplace
- **무엇을**: 플러그인이 MCP 서버를 번들하고 `/plugin marketplace add <repo>` + `/plugin install`
  **두 명령**으로 팀 전체가 동일 설정을 받는다. 터미널을 쓰지만 **우리 스크립트가 아니라 Claude 의
  명령**이고, 설정 파일 손편집이 사라진다.
- **현재 상태**: 없음.
- **raw_impact**: ★3 / **confidence**: med
- **note**: Claude Code 사용자 한정. codex·gemini 는 여전히 기존 경로.

### F-014 · 무인 처리를 「선택」으로 분리 + Desktop 스케줄 태스크
- **dimension**: functional
- **source**: https://code.claude.com/docs/en/desktop-scheduled-tasks
- **무엇을**: `/ai/connect` 가 **두 축을 나눠 묻는다** — 「지금 답을 받는다」(등록형, 설치물 0) /
  「자리를 비워도 처리한다」(러너 또는 Desktop 스케줄 태스크). 러너를 **필수에서 선택으로** 강등.
- **Desktop 로컬 스케줄 태스크 실측 사양**: 최소 간격 **1분** · **열린 세션 불요** · MCP 커넥터
  사용 가능 · 재시작 후에도 유지 · 권한 always-allow 저장. 단 **앱이 열려 있고 컴퓨터가 깨어
  있어야** 한다.
- **⚠ 정직한 한계 — 비용**: 스케줄 태스크는 질문이 없어도 **매 실행마다 새 세션**을 띄운다 =
  사용자 구독 쿼터 소모. 러너는 HTTP long-poll 만 하고 질문이 있을 때만 CLI 를 부른다. 그래서
  스케줄 태스크는 러너의 **대체재가 아니라 낮은 빈도(시간 단위) 대안**이다. 1분 주기로 두면
  P0-J 의 「환경 차이 금지」는 만족하지만 사용자 쿼터를 태운다 — **권장 기본값은 러너**.
- **raw_impact**: ★4 / **confidence**: high

### F-015 · 연결 퍼널 계측 — 다른 모든 항목의 **측정 선행**
- **dimension**: operational
- **source**: 정합 축 6(측정 가능성) — 측정 수단이 없으면 선행 항목으로 끌어올린다
- **무엇을**: `/ai/connect` 진입 → 경로 선택 → 설치 완료 → **첫 하트비트** → **첫 답변** 각
  단계 도달률을 `WebAuditEvents` 에 적재. 현재 `/api/ai/connect/status` (`oauth_as.py:534`)가
  `connected`·`listening` 을 이미 계산하므로 **판정 로직은 재사용**하고 기록만 더한다.
- **현재 상태**: 없음 — 「어느 단계에서 사람들이 떨어지는가」를 아무도 모른다. F-011·F-014 를
  하고도 나아졌는지 증명할 수 없다.
- **raw_impact**: ★4 / **confidence**: high
- **note**: 개인정보 최소 — 계정 id + 단계 + 타임스탬프. 토큰·명령문 미기록.

### F-016 · 네이티브 설치형 클라이언트 — **주 처방** (사용자 결정 2026-09-02)
- **dimension**: structural
- **source_kind**: 사용자 제안 + 상용 패턴(Tailscale MSI · Ollama 설치 마법사 · LM Studio)
- **무엇을**: 서명된 설치 파일이 ① 러너 엔진 동봉(파이썬 불요) ② CA 신뢰(프로세스 한정)
  ③ AI CLI 감지 → 없으면 벤더 공식 설치기를 **동의 받고** 실행 ④ **로그인 대행 실행**(§9.0.1)
  ⑤ 상주 + 로그온 자동시작 ⑥ 자동 업데이트 ⑦ 스킴으로 토큰 수령 을 한 번에 처리.
- **현재 상태**: 없음. 같은 일을 셸 스크립트 1,531행 + 사용자의 터미널 조작이 나눠 하고 있다.
- **왜 이것이 MCPB 보다 나은가**: 러너 `_RUNTIME_SPECS` 를 그대로 쓰므로 **claude·codex·gemini 를
  모두 덮는다**(MCPB 는 Claude Desktop 전용). 그리고 **C3**(러너가 사용자 머신 파일이라 우리가
  갱신할 수 없다 — P0-Z6 4차 재발의 뿌리)가 자동 업데이트로 닫힌다.
- **재사용 지렛대 (핵심)**: 엔진 5,849행 · 런타임 감지 · caps 신고 · 무결성 대조 · 스킴 핸들러가
  **전부 존재**한다. 신규는 GUI·설치 관리자·자동 업데이트뿐이고, 그 대가로 셸 스크립트 1,531행이
  소멸한다 — **순 코드량이 줄 가능성이 있다.**
- **raw_impact**: ★5 / **confidence**: med (SPIKE-02 가 확정)
- **note**: ⚠ **하드 선행 2건** — ① 코드 서명 확보(없으면 SmartScreen/Gatekeeper 경고가 터미널
  벽을 대체할 뿐) ② SPIKE-02 실현가능성 판정. ⚠ **제품이 하나 더 생긴다** — 3플랫폼 빌드·자동
  업데이트 인프라·타사 설치기 파손 시 지원 부담이 영구적이다.

---

## 11. 출처

> 문서 순서상 §8 이었으나 §9·§10 추가로 말미에 오도록 번호를 옮겼다(본문 참조는 「출처」로 지칭).

**§9.0.1 (ToS 경계 — 2026년 3사 OAuth 차단) 출처**
- [Anthropic clarifies ban on third-party tool access to Claude — The Register](https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/) — 2026-02-20 약관 개정
- [What Is the OpenClaw Ban? Why Third-Party Harnesses Were Blocked — MindStudio](https://www.mindstudio.ai/blog/anthropic-openclaw-ban-third-party-harnesses) — 2026-04-04 차단 시행
- [Anthropic Banned Third-Party Claude Auth: Full Guide 2026 — KERSAI](https://kersai.com/anthropic-killed-third-party-claude-access-heres-every-workaround-that-still-works/) — **`claude -p` subprocess 허용 확인(2026-04 중순)** + Agent SDK 크레딧 풀(2026-06-15)
- [Anthropic Bans OAuth Tokens from Consumer Plans in Third-Party Tools](https://openclaw.report/ecosystem/anthropic-bans-oauth-tokens-third-party-tools)
- [Service update: mitigating abuse and prioritizing traffic — google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli/discussions/22970) — Google 2026-02 토큰 프록시 금지·계정 정지
- [Does forking/modifying Codex CLI affect ToS when using "Sign in with ChatGPT"? — openai/codex](https://github.com/openai/codex/discussions/8338)

**§9·§10 (「AI 연결」 축) 추가 출처**
- [Build a desktop extension with MCPB](https://claude.com/docs/connectors/building/mcpb) — MCPB 권장 케이스 표 · Node.js 동봉 · `user_config` 자동 UI · 설치 3경로
- [Schedule recurring tasks in Claude Code Desktop](https://code.claude.com/docs/en/desktop-scheduled-tasks) — 로컬 태스크 사양(최소 1분 · 열린 세션 불요 · MCP 커넥터 · 앱 열림 필요)
- [Claude Code Plugins and Marketplaces (2026)](https://www.morphllm.com/claude-code-marketplace) · [Claude Code Plugins Complete Guide](https://hidekazu-konishi.com/entry/claude_code_plugins_complete_guide.html) — 플러그인이 MCP 서버를 번들해 팀 배포
- [MCPB Files (.mcpb): Format Reference](https://www.mcpbundles.com/docs/concepts/mcpb-files) — 「로컬 stdio 프록시 + 원격 HTTP」 번들 패턴의 상용 선례

**Anthropic 공식**
- [Build a desktop extension with MCPB](https://claude.com/docs/connectors/building/mcpb)
- [Desktop Extensions — Engineering at Anthropic](https://www.anthropic.com/engineering/desktop-extensions)
- [modelcontextprotocol/mcpb](https://github.com/modelcontextprotocol/mcpb)
- [Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Third party connectors with remote MCP](https://claude.com/docs/connectors/custom/remote-mcp)
- [Get started with the desktop app — Claude Code Docs](https://code.claude.com/docs/en/desktop-quickstart)
- [Claude Code and new admin controls for business plans](https://www.anthropic.com/news/claude-code-on-team-and-enterprise)
- [Consumer Terms of Service](https://anthropic.com/legal/terms)

**설치·배포 패턴**
- [Install Tailscale on Windows with MSI](https://tailscale.com/docs/install/windows/msi)
- [Deploy Winget Apps to Microsoft Intune (2026)](https://www.intuneget.com/blog/deploy-winget-apps-to-intune)
- [PKCS certificate profiles in Microsoft Intune](https://learn.microsoft.com/en-us/intune/device-configuration/certificates/pkcs-profiles)
- [Deploy Trusted Root Certificate Using Intune](https://www.prajwaldesai.com/deploy-trusted-root-certificate-using-intune/)
- [Configuring the self-hosted runner application as a service — GitHub Docs](https://docs.github.com/ja/actions/how-tos/hosting-your-own-runners/managing-self-hosted-runners/configuring-the-self-hosted-runner-application-as-a-service)
- [Ollama vs LM Studio vs Jan AI vs GPT4All: one-click installers (2026)](https://www.promptquorum.com/local-llms/local-llm-one-click-installers)
- [LM Studio complete guide (2026)](https://www.aimadetools.com/blog/lm-studio-complete-guide/)

**BYOK · AI 게이트웨이**
- [LiteLLM — Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [LiteLLM — Budgets, Rate Limits](https://docs.litellm.ai/docs/proxy/users)
- [BYOK: Why It Matters for Enterprise Agent Rollouts — Augment Code](https://www.augmentcode.com/guides/byok-enterprise-agent-rollouts)
- [Best BYOK AI Coding Assistants 2026](https://copilot-alternatives.com/blog/best-byok-ai-coding-assistants-2026/)
- [A Claude Code Subscription Is Not a Developer Credential](https://yage.ai/share/claude-code-subscription-not-a-developer-credential-en-20260321.html)

**동종 제품 (DB 자연어 질의)**
- [Text to SQL Tools Comparison 2026: What Actually Works for Enterprise](https://promethium.ai/guides/text-to-sql-comparison-2026-enterprise-solutions/)
- [Cortex Analyst vs. Genie (2026): Accuracy, Pricing, Limits](https://colrows.com/blogs/cortex-analyst-vs-genie/)
- [What Is Cortex Analyst? — Datus](https://datus.ai/blog/what-is-cortex-analyst/)
- [10 Best AI Tools to Query Your Database Without Writing SQL](https://www.aifordatabase.com/blog/best-ai-database-query-tools-2026/)
- [Outerbase](https://outerbase.com/)

**온보딩 활성화 벤치마크**
- [Time to Value: The 2026 SaaS Onboarding Metrics Framework](https://www.digitalapplied.com/blog/customer-onboarding-time-to-value-2026-saas-metrics-framework)
- [SaaS Onboarding 2026: Beat the 37.5% Activation Trap](https://www.flowjam.com/blog/saas-onboarding-best-practices-2025-guide-checklist)
- [Customer Onboarding Statistics 2026: 412K-User SaaS Benchmark](https://visionary-marketing.co.uk/blog/customer-onboarding-statistics-2026)
