---
doc_type: FUNCTION
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

**Windows 네이티브 클라이언트** — 사용자가 터미널을 열지 않고 자기 AI 를 이 서비스에 연결한다.
`bridge_setup.ps1`(669행 PowerShell)이 하던 일을 **같은 계약으로** 하되 껍데기를 GUI 로 바꾼다.

사용자가 하는 일: **설치 파일 실행 → 쓸 AI 선택 → [로그인] → [연결]**. 끝.

## 2. Goal

- REQ-20260903-native-client: 「AI 연결」의 터미널 의존을 제거한다. 근본 원인은
  `docs/improvements/onboarding-accessibility/RESEARCH.md` §9.1 — **연결을 우리가 만든
  배포물로 구현하고 런타임·설치 UX·설정 UI·업데이트 채널을 전부 자체 구현해 넷 모두가 마찰이 됐다.**

## 3. In Scope

### P0-A. 계약은 그대로, 껍데기만 교체

`bridge_setup.ps1` 과 **같은 순서·같은 대조·같은 중단 지점**:

1. 사내 CA 수신 → **DER 지문** 대조 (파일 해시가 아니다 — 그 혼동이 feature-0006 REQ-0286 의 실측 결함)
2. `bridge_agent.py` 수신 → sha256 대조
3. `--check` 로 연결 확인 (**상주 전에**)
4. 통과하면 러너 상주

CA 는 **평문 HTTP** 로 받는다(부트스트랩 데드락 — 엣지 인증서를 서명한 것이 그 CA 다).
그 위험은 지문 대조가 덮는다. 전역 신뢰 저장소는 **건드리지 않는다.**

### P0-B. 로그인은 **「위임」이 아니라 「대행 실행」** (ROADMAP §0.1 불변 제약)

2026년에 3사가 구독 OAuth 의 제3자 사용을 차단했다 — Anthropic 2026-04-04, Google 은
2026-02 에 **유료 구독자 계정을 정지**했다. 그래서 클라이언트는 **벤더 공식 명령을 subprocess 로
띄우고 종료코드로 판정할 뿐, 토큰을 읽지도 저장하지도 중계하지도 않는다.**

| CLI | 로그인 | 상태 | 로그인됨 | 미로그인 |
|---|---|---|---|---|
| claude | `claude auth login` | `claude auth status` | exit 0 + JSON `loggedIn:true` | exit 1 |
| codex | `codex login` | `codex login status` | exit 0 | exit 1 |
| gemini | — | — | **미실측** → 「감지·안내」로 강등 |

`test_client_never_touches_vendor_credentials` 가 이 경계를 잠근다.

### P0-C. 연결 축과 AI 축을 **갈라 말한다**

러너 `--check` 의 **종료코드 4 = 「서버 연결은 정상인데 쓸 수 있는 AI 가 없다」**. 이것을 「연결
확인 실패」로 뭉치면 사용자는 서버를 의심한다(feature-0043 REQ-20260901-win-ai-detect 의 실제 제보).

### P0-D. 감지는 **PATH 밖 표준 위치까지**

실측 2026-09-01: Claude Code 의 Windows 설치기는 `%USERPROFILE%\.local\bin\claude.exe` 에 넣는데
**그 폴더가 사용자 PATH 에 없었다.** `shutil.which` 만 쓰면 설치돼 있는데 「없음」이 된다.
Microsoft Store 앱 실행 별칭 스텁(`\WindowsApps\`)은 「있다」로 세지 않는다.

### P0-E. 토큰은 **환경변수로만**

명령줄에 실으면 프로세스 목록에 뜬다. `check_connection`·`spawn_runner` 둘 다 `BRIDGE_TOKEN` env.

### P0-F. GUI 앱은 **콘솔로 말하지 않는다** (실 Windows 실측 2026-09-03)

`--windowed` PyInstaller 빌드는 `sys.stdout` 이 `None` 이다. `print()` 를 부르면 예외 → 미처리
예외 대화상자 → **프로세스가 사용자 입력을 기다리며 멈춘다**(실제로 그렇게 걸려 강제 종료했다).
사용자 안내는 `tell()`(tkinter messagebox)로 한다.

## 4. Out of Scope (이번 cycle)

- **macOS** — 사용자 결정 2026-09-03: Windows 우선. macOS 는 서명·공증 없이 Gatekeeper 가 **차단**한다.
- **코드 서명** — 사용자 결정: 미서명 진행, SmartScreen 경고 2클릭 감수.
- **자동 업데이트 · 로그온 자동시작 · 벤더 설치기 자동 실행** — 후속.
- **러너 동봉** — 하지 않는다. 서버에서 받아 체크섬 대조(설치 스크립트와 같은 계약). 동봉하면
  서버 배포와 클라이언트 배포가 갈려 「고쳤는데 그대로」가 재발한다.

## 5. 빌드

`src/scripts/build_client.py` — PyInstaller `--onefile --windowed`. **Windows 에서 실행해야 한다**
(크로스 컴파일 불가). 소스는 커밋, **배포본은 빌드 생성물**(러너와 같은 규약).
