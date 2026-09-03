---
run_at: 2026-09-03T12:20:00+09:00
session: ai/claude-corp/feature-0043-runner-name-dqa-connect
scope: runner-name-dqa-connect — 웹이 발행하는 딥링크 스킴·MCP 키 (feature-0043 개명의 web 축)
verdict: PASS
---

# TASK-20260903T120000 — 웹 축 검증 기록 (PB-0008)

> 이 fragment 가 **feature-0003** 에 있는 이유: 이번 cycle 이 건드린 웹 자산
> (`src/static/index.html` · `src/routers/oauth_as.py` · `src/routers/ai_tools.py`)의 소유
> feature 가 여기이기 때문이다(check #13 은 파일 소유 feature 를 본다). 변경의 본체와 설계
> 근거는 `unit/feature-0043-external-llm-bridge/docs/` 가 정본이다.

## 1. Environment: Windows-browser (PB-0008)

| 항목 | 값 |
|---|---|
| 브리지 | `doctor` → `ok:true` · relay `http://172.26.144.1:9223` · Chrome/152.0.7977.75 |
| 진입 | `https://localhost/` → **status 200** · title `DQA — Database Query Assistant` |
| 세션 | `session-login` → `authenticated:true` · `bootstrap_admin` / role `admin` |
| 캡처 | `artifacts/feature-0043/20260903T120000/predeploy-connect.png` |

## 2. 배포 **전** baseline 실측 (이 cycle 이 뒤집어야 할 값)

`POST /api/ai/connect/token` 응답을 실 브라우저에서 호출해 측정:

| 측정 | 배포 전 (실측) | 배포 후 기대 |
|---|---|---|
| 딥링크 스킴 (`<scheme>://start?token=`) | **`mysql-ai-bridge`** | `dqa-connect` |
| 응답 본문의 `mysql-ai` 출현 | **4** | 0 |
| 응답 본문의 `dqa-connect` 출현 | **0** | ≥ 1 |

**왜 배포 전에 재는가.** 이 변경은 서버가 만드는 **문자열**을 바꾸는 것이라, 배포 후 값만 보면
「원래 그랬는지」와 구별되지 않는다. 두 점을 재야 이 cycle 이 그 값을 바꿨다는 것이 관측이 된다.
그리고 배포 전 값이 `mysql-ai-bridge` 라는 사실 자체가, 현재 라이브 사용자의 OS 에 등록된 것도
옛 스킴임을 뜻한다 — 하드 컷오버의 대가(재실행 전까지 버튼 무반응)가 실재함을 확인한 것이다.

## 3. 픽셀-클래스 변경 여부 (§16.6 evidence 분기)

**없다.** 이 cycle 의 웹 자산 변경은 ① `index.html` **주석 1줄** ② 라우터가 만드는 **문자열**
(딥링크·`mcpServers` 키·프롬프트 문안)뿐이다. 레이아웃·정렬·간격·overflow 에 영향을 주는 CSS·
DOM 구조 변경이 0 이므로 렌더된 기하가 바뀌지 않는다 — 그래서 판정을 element/응답 상태로 한다.
(§16.6 은 「element 상태로 충분」쪽에 입증 책임을 두므로 그 근거를 여기 적는다.)

## 4. 미수행 (은폐하지 않는다)

- **배포 후 재측정** — 위 표의 「배포 후 기대」 열은 아직 **미관측**이다. cycle-finalize →
  배포 후 같은 eval 을 다시 돌려 이 fragment 에 POST-DEPLOY 로 append 한다.
- **`[내 AI 실행]` 버튼의 실제 OS 핸들러 기동** — 이 머신에는 아직 옛 스킴만 등록돼 있고, 새
  스킴 등록은 사용자가 setup 을 재실행해야 생긴다. 버튼 클릭이 러너를 띄우는 것까지는 이
  cycle 에서 **관측 불가**이며, 그 사실이 곧 하드 컷오버의 알려진 대가다.
- **macOS 핸들러 경로** — 실측 수단 없음.


---

## POST-DEPLOY 대조 (배포 `c08047f8`, 2026-09-03)

배포 **전** 같은 방법으로 재 둔 baseline 과 대조한다 — 한 점만 재면 「원래 그랬는지」와
구별되지 않으므로 두 점을 잰다.

| 측정 (실 브라우저 `POST /api/ai/connect/token`) | 배포 전 | 배포 후 | 판정 |
|---|---|---|---|
| 딥링크 스킴 | `mysql-ai-bridge` | **`dqa-connect`** | 뒤집힘 |
| 응답 본문 `mysql-ai` 출현 | 4 | **0** | 뒤집힘 |
| 응답 본문 `dqa-connect` 출현 | 0 | **2** | 뒤집힘 |
| CLI 안내 `mcp add --transport http <키>` | (미측정) | **`dqa`** | 정본 파생 |

진입: `https://localhost/` → 200 · `DQA — Database Query Assistant` · `bootstrap_admin` 인증됨.

**서빙 실물 대조** (`curl -sk https://localhost/static/agent/…`):

| 파일 | `dqa-connect` | `mysql-ai-bridge` | 잔여의 성격 |
|---|---|---|---|
| `bridge_setup.sh` | 5 | 7 | 명칭블록 `LEGACY_*` 2 · 이력 주석 4 · 경고문 1 — **등록 경로 0** |
| `bridge_setup.ps1` | 3 | 3 | 명칭블록 `LEGACY_*` 2 · 주석 1 |
| `bridge_agent.py` | 4 | 1 | 개명 주석 1 |

**배포 무결성**: web-a/b·ask-worker·insight-worker·ext-tool-mcp-a/b 전부 `c08047f8` 동일 SHA ·
`no upstreams available` **0건**(무중단 실측) · surge 잔존 0 · 대화 경로 스모크 PASS.

## 여전히 미검증 (은폐하지 않는다)

- **실 OS 핸들러 재등록·옛 잔재 삭제** — 사용자 머신에서 setup 을 재실행해야 관측된다.
  이 검증이 보인 것은 «서버가 무엇을 발행하는가» 까지이고, «그 머신에 무엇이 등록되는가» 는
  아니다. 하드 컷오버라 **재실행 전까지 기존 설치자의 `[내 AI 실행]` 은 무반응**이다.
- **macOS 경로** — 실측 수단 없음.
