---
doc_type: DQA_SPIKE
initiative: onboarding-accessibility
spike_id: SPIKE-02
created_at: 2026-09-03
source_roadmap: ./ROADMAP.md
status: complete
verdict: conditional-go
---

# SPIKE-02 — 네이티브 클라이언트 실현가능성 판정

> ROADMAP `ITEM-08`(네이티브 클라이언트, **Major**)의 하드 선행. 타임박스 1 cycle.
> **「될 것 같다」로 Major 항목을 열지 않는다**는 것이 이 문서의 존재 이유다.

## 0. 판정 요약

| # | 항목 | 판정 | 근거 등급 |
|---|---|---|---|
| 1 | 3사 CLI 의 스크립트 가능 로그인 | **GO** (claude·codex) / **미실측** (gemini) | **실측** — 명령 실행 + 종료코드 |
| 2 | 서명 없는 설치의 실제 경고 | **조건부** — 벽이 낮아지지만 사라지지 않는다 | **문서** (실 화면 캡처 미실측) |
| 3 | 기술 스택 · 러너 동봉 | **GO** — stdlib 전용이라 동봉이 단순 | **실측**(의존성) + **추정**(스택) |
| 4 | Agent SDK 크레딧 풀 영향 | **영향 없음 — 전제가 틀렸다** | **문서** — 해당 변경은 **취소됨** |

**종합: conditional-go.** 기술적 장애물은 없다. 남은 것은 **코드 서명을 살 것인가**라는 조직 결정
하나이고, 그 답이 「아니오」여도 진행 경로가 존재한다(§2.3).

---

## 1. 3사 CLI 의 스크립트 가능 로그인 — **GO** (실측)

ROADMAP 이 물은 세 가지: ① 비대화형/GUI 에서 띄울 수 있는 로그인 명령이 있는가 ② 성공/실패를
종료코드나 출력으로 판정할 수 있는가 ③ 이미 로그인돼 있는지 확인하는 명령이 있는가.

### 1.1 실측 결과

| CLI | ① 로그인 | ② 판정 | ③ 상태 확인 | 판정 |
|---|---|---|---|---|
| **claude** | `claude auth login` | 종료코드 + **JSON** | `claude auth status` | **GO** |
| **codex** | `codex login` | 종료코드 + 문자열 | `codex login status` | **GO** |
| **gemini** | — | — | — | **미실측** (이 환경에 미설치) |

```
$ claude auth --help
  login [options]   Sign in to your Anthropic account
  logout            Log out from your Anthropic account
  status [options]  Show authentication status

$ codex --help | grep -i login
  login             Manage login          (하위: `codex login status`)
  logout            Remove stored authentication credentials
```

### 1.2 종료코드·출력이 실제로 갈리는가 (양방향 실측)

로그아웃하지 않고 **격리 설정 디렉토리**로 미로그인 상태를 만들어 대조했다 — 이 세션의 인증을
건드리지 않는다(실행 후 `loggedIn: true` 재확인).

| 상태 | claude | codex |
|---|---|---|
| 로그인됨 | `exit 0` + `{"loggedIn": true, "authMethod": "claude.ai", "email": …, "subscriptionType": …}` | `exit 0` + `Logged in using ChatGPT` |
| 미로그인 | `exit 1` + `{"loggedIn": false, …}` | `exit 1` + `Not logged in` |

**클라이언트 GUI 가 필요로 하는 것이 전부 있다**: 상태를 물어 화면을 그리고(로그인됨/안 됨),
로그인 명령을 subprocess 로 띄우고, 종료코드로 성공을 판정한다. claude 는 JSON 이라
**「누구로 로그인돼 있는지」까지 표시**할 수 있다.

### 1.3 이것이 §0.1 ToS 경계 안인가 — **예**

여기서 하는 일은 **벤더 공식 CLI 를 실행하는 것**뿐이다. 토큰을 읽지도, 저장하지도, 중계하지도
않는다. `claude auth status` 의 JSON 도 **우리가 만든 것이 아니라 CLI 가 내는 것**이고, 클라이언트는
그것을 화면에 옮길 뿐이다. ROADMAP §0.1 의 「대행 실행」 정의와 정확히 일치한다.

### 1.4 gemini — 미실측 (정직한 잔여)

이 환경에 `gemini` 가 없다. **추정하지 않는다.** ITEM-08 의 acceptance 2 가 요구하는 것은
「런타임별로 완주 확인, 실패하면 그 런타임은 감지·안내로 강등하고 화면이 그 사실을 말한다」이므로,
gemini 는 **구현 cycle 에서 실측하거나 강등**한다. 커버리지를 과장하지 않는 것이 계약이다(P0-I).

---

## 2. 서명 없는 설치의 실제 경고 — **조건부** (문서 근거, 화면 미실측)

### 2.1 무엇이 일어나는가

| 플랫폼 | 서명 없음 | 서명만 | 서명 + 공증 |
|---|---|---|---|
| **Windows** | SmartScreen 「Windows 가 PC 를 보호했습니다」 → **[추가 정보] → [실행]** 2클릭 | 평판 축적 전까지 경고 잔존(OV) / EV 는 즉시 통과 | — |
| **macOS** | Gatekeeper **차단** — 사용자가 명시적으로 우회해야 함 | 공증 없으면 **여전히 차단**(10.15+) | 통과 |

### 2.2 비용 (2026 기준)

- Windows EV: 클라우드 서명 **~$226/년**부터, 하드웨어 토큰 방식 **$400~700/년**
- Apple Developer Program: **$99/년** (공증 포함)

### 2.3 ⚠ 이것이 ITEM-08 을 막는가 — **막지 않는다. 판단이 갈릴 뿐이다**

ROADMAP 은 서명을 **하드 선행**으로 못박았고 그 근거는 *"서명 없이 배포하면 경고가 터미널 벽을
그대로 대체한다"* 였다. 이 조사는 그 문장을 **일부 수정**한다:

- **벽의 높이가 다르다.** 터미널 벽은 「무엇을 어디에 붙여넣는지 모른다」이고, SmartScreen 벽은
  「경고를 읽고 2번 클릭한다」다. 후자가 낮다 — 사용자가 할 일을 **화면이 말해 주기** 때문이다.
- **사내 배포는 예외 취급이 통용된다.** 알려진 수신자에게 「이 경고가 뜨면 [추가 정보]→[실행]」을
  안내할 수 있는 내부 도구는 서명을 선택으로 두는 것이 일반적이다.
- **그러나 우리 대상은 정확히 「경고를 무서워하는 사람」이다.** 이 로드맵의 수요자는 비개발자이고,
  보안 경고를 만나면 멈추는 것이 정상 반응이다. 안내가 있어도 이탈이 생긴다.
- **macOS 는 사정이 다르다** — 서명+공증 없이는 Gatekeeper 가 **차단**한다(경고가 아니라 차단).
  즉 macOS 사용자가 있으면 Apple Developer Program($99/년)은 **사실상 필수**다.

**판정**: 서명 미확보를 **차단 사유가 아니라 범위 축소 사유**로 재분류할 것을 제안한다 —
Windows 만 서명 없이 먼저 내고(안내 동반), macOS 는 $99 확보 후. 최종 결정은 사용자 몫이며
ROADMAP §2 의 게이트 문구를 그에 맞게 고칠지도 함께 결정한다.

### 2.4 미실측 (정직한 잔여)

**실 Windows/macOS 에서 서명 없는 설치 파일을 만들어 경고 화면을 캡처하지 못했다** — 이 환경에
두 OS 의 실행 수단이 없다. 위 표는 공개 문서 근거이고, 「비개발자가 통과할 수 있는 경고인가」라는
ROADMAP 의 원 질문(화면으로 판정)은 **여전히 미답**이다. ITEM-08 착수 시 첫 빌드로 확인한다.

---

## 3. 기술 스택 · 러너 동봉 — **GO** (의존성 실측 + 스택 추정)

### 3.1 러너 동봉 난이도 — **실측: 단순하다**

```
러너 규모        : 5,971행 (src/agent/ 19 모듈)
최상위 import    : 19개
서드파티 의존    : 0개  ← AST 전수 검사, stdlib 전용
최소 파이썬      : 3.8+
```

**서드파티가 0이라는 사실이 이 항목의 답이다.** wheel·네이티브 확장·플랫폼별 바이너리가 없으므로
PyInstaller 동결이나 임베디드 CPython 동봉 어느 쪽이든 **플랫폼별 특수 처리가 필요 없다.**
러너의 「stdlib 전용」 계약(P0-K)이 여기서 배당금을 낸다.

### 3.2 스택 권고 — **Tauri + PyInstaller sidecar** (⚠ 추정, 미실측)

| 후보 | 장점 | 단점 | 판정 |
|---|---|---|---|
| **Tauri** | 시스템 webview 사용 → 번들 작음 · MSI/NSIS·dmg/pkg 생성 · 서명 검증 내장 업데이터 · sidecar(외부 바이너리 동봉) 일급 지원 | Rust 툴체인 도입 | **권고** |
| Electron | 생태계·자료 풍부 | Chromium 동봉으로 번들 큼 | 차선 |
| Go + 트레이 | 단일 바이너리·의존성 최소 | GUI 표현력 낮음(설정 화면·로그인 진행 표시가 빈약) | 부적합 |

러너는 **PyInstaller 로 동결해 sidecar 로 동봉**한다 — 포팅(러너를 Rust/JS 로 재작성)은
**기각**이다. 5,971행을 재작성하면 ROADMAP §0.2 의 재사용 지렛대를 통째로 버리고, 러너가 겪은
결함 이력(인코딩·명령줄 상한·supersede 등)을 새 언어에서 다시 겪는다.

⚠ **번들 크기·3플랫폼 빌드 난이도는 미실측이다** — 실제 빌드 없이는 알 수 없다. 위 표는 각
프레임워크의 공개 특성에 근거한 **추정**이고, ITEM-08 첫 주에 hello-world 빌드로 확인해야 한다.

---

## 4. Agent SDK 크레딧 풀 영향 — **전제가 틀렸다 (영향 없음)**

### 4.1 정정

ROADMAP 과 RESEARCH §9.0.1 은 *"`claude -p` subprocess 호출이 2026-06-15부터 일반 구독 한도가
아니라 Agent SDK 크레딧 풀에서 차감된다는 보고"* 를 실측 대상으로 올렸다. **그 변경은 시행되지
않았다.**

- 2026-05-14 Anthropic 이 「Agent SDK · `claude -p` 사용을 구독 풀에서 분리해 별도 월 크레딧으로」
  발표
- **2026-06-15 그 계획을 취소**했다고 Help Center 에서 확인
- **현재(2026-09): `claude -p` 는 여전히 구독 한도에서 차감된다.** 별도 계량기는 없다

### 4.2 그래서 무엇이 달라지는가

**아무것도 달라지지 않는다** — 사용자 실질 한도에 대한 우려는 근거가 사라졌다. `/ai/connect`
안내에 크레딧 풀을 반영할 필요가 없다.

> ⚠ **이 항목은 「보고를 실측으로 승격」하려다 「보고가 틀렸음」을 찾은 경우다.** 앞선 세션 대화에서
> 이 내용을 **주의사항으로 사용자에게 전달했는데, 그것은 정정되어야 한다.** SPIKE 를 두지 않고
> 로드맵에 사실로 적었다면 안내 문구를 잘못 고쳤을 것이다.

### 4.3 로컬 관측 불가 (방법론 기록)

`claude auth status` 는 `subscriptionType` 은 내지만 **잔여 한도·크레딧 필드는 내지 않는다**
(응답 키 전수: `analyticsDisabled · apiProvider · authMethod · email · loggedIn · orgId ·
orgName · projectsDirectory · subscriptionType`). 즉 이 축은 **문서로만 확인 가능**하고, 그
사실 자체를 기록해 다음에 같은 시도를 반복하지 않게 한다.

---

## 5. ITEM-08 spec 초안 (ROADMAP 반영용)

SPIKE 결과로 확정되는 부분:

- **로그인 대행 실행** — `claude auth login` / `codex login` 을 subprocess 로 띄우고,
  `claude auth status`(JSON) · `codex login status` 로 **전/후 상태를 판정**해 GUI 에 표시한다.
  claude 는 JSON 이라 계정 표시까지 가능. **gemini 는 구현 cycle 에서 실측 후 지원/강등 결정.**
- **러너 동봉** — PyInstaller 동결 후 Tauri sidecar. 포팅 금지.
- **크레딧 풀 안내 불요** — 4장 근거.
- **서명** — Windows 는 미서명 + 안내 동반으로 착수 가능(단 이탈 위험 감수), **macOS 는 Apple
  Developer Program 없이는 차단**되므로 지원 대상에 macOS 를 넣는 순간 $99/년이 필수.

## 6. 미실측으로 남긴 것 (전수)

| 무엇 | 왜 | 언제 닫히나 |
|---|---|---|
| gemini CLI 로그인 명령 | 이 환경에 미설치 | ITEM-08 구현 cycle |
| 서명 없는 설치의 **실 경고 화면** | 실 Windows/macOS 실행 수단 없음 | ITEM-08 첫 빌드 |
| Tauri/Electron **번들 크기·빌드 난이도** | 실제 빌드 없이 불가 | ITEM-08 첫 주 hello-world |
| PyInstaller 동결본의 **실제 동작** | 위와 동일 | ITEM-08 첫 주 |

## 7. 출처

- 실측: 이 환경의 `claude` / `codex` CLI (`--help`, `auth status`, `login status`, 격리 설정 대조)
- 실측: `unit/feature-0043-external-llm-bridge/src/agent/` AST 전수 의존성 검사
- [Use the Claude Agent SDK with your Claude plan — Anthropic Help Center](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- [Claude Credit Overhaul 2026: Anthropic Pauses the June 15 Change](https://www.digitalapplied.com/blog/anthropic-claude-credit-overhaul-june-15-2026)
- [Claude Code Billing in 2026: Subscription Usage vs the Agent Credit Pool](https://tygartmedia.com/claude-code-billing-credit-pool-2026/)
- [Code Signing Certificate Costs (2026 Pricing Comparison)](https://desktopcore.com/compare/code-signing-costs)
- [Code-signing certs for your own binaries in 2026](https://www.bigiron.cc/guides/code-signing-certs-for-your-own-binaries-when-it-matters)
- [What Does a Signed Installer Mean on Windows and macOS?](https://orthiclabs.com/notes/signed-installer/)
- [Code Signing | electron-builder](https://www.electron.build/docs/features/code-signing/)
