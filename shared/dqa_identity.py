"""feature-0043 — 개인 머신 클라이언트의 **명칭 단일 정본** (제품명 · URL 스킴 · 역-DNS id).

## 왜 이 모듈이 생겼나

2026-09-03 이전 이 이름은 `mysql-ai-bridge` 였고, **리터럴로 21곳에 흩어져** 있었다 —
설치 스크립트 `bridge_setup.sh` 20곳 · `.ps1` 7곳 · 러너 `src/agent/` 6곳 · 웹 4곳.
한 곳을 고치고 다른 곳을 놓치면 **웹은 새 스킴으로 열고 OS 에는 옛 스킴이 등록돼 있는**
상태가 되는데, 브라우저는 스킴 핸들러 부재를 **감지하지 못한다** — 버튼이 조용히 죽고
사용자는 「연결이 안 된다」만 본다. 이 저장소는 이미 그 형태를 겪었다
(`bridge_setup.sh` §3-a 의 2026-08-31 실측: 키 없음 · 버튼 무동작 · 토큰 4건 하트비트 없음).

그래서 값을 여기 한 번만 두고, `tests/test_name_ssot.py` 가 **여기 · 러너 `agent/base.py` ·
설치 스크립트 두 벌**을 파싱해 네 곳이 같은 값인지 단정한다.

## 왜 세 축인가 (한 토큰을 전 표면에 복사하지 않는다)

축마다 지배하는 규약이 다르다. 하나로 합치면 어느 한쪽 규약을 반드시 어긴다.

- `APP_NAME` — **사람이 읽는 것**. 설치 파일·트레이·프로그램 목록·안내 문구.
- `SCHEME` — **머신 전역 네임스페이스**. URL 스킴 · Windows 레지스트리 키 ·
  `x-scheme-handler/<scheme>` MimeType. RFC 3986 상 소문자·숫자·`+-.` 만 허용된다.
- `APP_ID` — **역-DNS**. macOS `CFBundleIdentifier`/`CFBundleURLName`, Linux `.desktop`
  파일명(freedesktop 권장 Application ID).

⚠ `SCHEME` 을 짧게(`dqa`) 두지 않은 것은 **보안 판단**이다. 이 스킴 URL 에는 세션 베어러
토큰이 실린다(`dqa-connect://start?token=mat_...`). 스킴 등록은 선착순이 아니라 마지막
등록자가 이기는 머신 전역 네임스페이스라, 같은 이름을 등록한 다른 앱이 있으면 **살아 있는
토큰이 그쪽으로 간다**. `DQA` 는 흔한 약어(Data Quality Assurance 등)이므로 브랜드 한정
없이 쓰면 충돌 표면이 넓어진다 — **다만 이것은 추정이지 실측이 아니다**(다른 프로그램이
`dqa://` 를 실제로 등록하는지 조사한 바 없다). 확실한 것은 개명 **여부와 무관하게** 스킴
하이재킹 위협이 원래 존재한다는 사실이고, 개명이 그것을 없애지 않는다는 점이다 —
길게 두는 것은 그 위협을 **줄이려는** 선택이지 해소가 아니다. 근본 해소(스킴 소유권 검증,
일회성 nonce 교환 등)는 별도 cycle 이다.

반대로 **MCP 서버 키는 짧게** 둔다(`MCP_SERVER_KEY = "dqa"`). 그것은 사용자 자기 AI CLI
설정 안의 **로컬 키**라 전역 충돌이 없고, 대신 사용자가 모든 도구 이름에서 매번 읽는다
(`mcp__dqa__execute_sql`). 두 축의 비대칭은 의도된 것이다.

## 무엇을 두지 않는가

- **하위호환 별칭을 두지 않는다.** 옛 스킴 `mysql-ai-bridge` 는 등록하지 않는다(사용자 결정
  2026-09-03 하드 컷오버). 설치 스크립트가 재실행 시 옛 등록·옛 홈을 **지우기만** 한다.
  여기 `LEGACY_*` 를 두는 목적은 그 정리 대상을 이름으로 고정하는 것뿐이다.
- 러너 동작·토큰·경로 해석. 그것은 `shared/bridge_tasks.py`(상태 술어) ·
  `shared/bridge_caps.py`(능력 원장) · 러너 `agent/base.py`(런타임 경로)의 몫이다.
  이 모듈은 **문자열만** 갖는다 — import 부작용이 없어야 어디서든 부를 수 있다.
"""
from __future__ import annotations

#: 사람이 읽는 제품명. 설치 파일·레지스트리 설명 등 **설치·패키징 층**의 이름.
APP_NAME = "DQA Connect"

#: **창·트레이·대화상자에 뜨는 이름** (사용자 결정 2026-09-04).
#:
#: ⚠ `APP_NAME` 과 왜 다른가: 사용자에게 이 프로그램은 「연결 도우미」가 아니라 **DQA 자체**다
#: (앱 창을 이 프로그램이 직접 그린다). 화면에 «Connect» 가 남으면 서비스와 별개의 무언가를
#: 여는 것처럼 읽힌다 — 사용자가 지적한 그 인상이다. 반대로 설치 폴더·레지스트리 키·제거
#: 항목까지 바꾸면 기존 설치본의 업그레이드 경로가 갈리므로, **보이는 이름만** 바꾼다.
DISPLAY_NAME = "DQA"

#: URL 스킴 = Windows 레지스트리 키 = `x-scheme-handler/<scheme>`.
#: 러너 설치 홈은 `~/.{SCHEME}` 이다(`agent/base.py` `_HOME_DIRNAME`).
SCHEME = "dqa-connect"

#: 역-DNS Application ID — macOS 번들 id · Linux `.desktop` 파일명.
#: ⚠ 루트(`com.masangsoft`)는 조직 도메인이다. 다른 조직에 배포하면 이 한 줄만 바꾼다.
APP_ID = "com.masangsoft.dqa-connect"

#: 사용자 AI CLI 설정(`mcpServers`)에 들어가는 키. 도구 이름이 `mcp__{key}__<tool>` 이 된다.
#: 위 docstring 의 비대칭 근거 참조 — 전역이 아니라 로컬 키라 짧게 둔다.
MCP_SERVER_KEY = "dqa"

#: 개명(2026-09-03) 전 이름 — **정리 대상 식별 전용**. 별칭으로 등록하지 않는다.
LEGACY_SCHEME = "mysql-ai-bridge"
LEGACY_MCP_SERVER_KEY = "mysql-ai"


def scheme_url(token: str, base: str = "", ca_sha256: str = "",
               agent_sha256: str = "") -> str:
    """웹 `[내 AI 실행]` 버튼이 여는 딥링크.

    토큰을 URL 에 싣는 것은 의도된 설계다 — 핸들러 스크립트에는 토큰이 없고(디스크에 쓰지
    않는다), 이 토큰은 웹 로그인 세션에 결속돼 로그아웃하면 즉시 무효다. 조립을 여기 두는
    이유는 스킴과 경로(`start`)가 **함께** 바뀌어야 하는 한 쌍이기 때문이다.

    ## 왜 토큰만으로는 부족한가 (실측 2026-09-03)

    이 URL 은 원래 **셸 설치본**을 위한 것이었다. 그 경로는 설치 때 서버 주소와 CA 를 이미
    디스크에 심어 두므로 토큰만 받으면 된다.

    네이티브 클라이언트에는 그 사전 상태가 없다. 그래서 토큰만 실린 URL 을 받으면 서버가
    어디인지 몰라 **「연결 정보가 없습니다」**만 띄웠다 — 사용자가 바로 앞에서 [연결 준비] 를
    누르고 [내 AI 실행] 을 눌렀는데도. 실제 제보가 그것이다.

    그래서 연결에 필요한 값을 **모두** 싣는다. 지문 두 개는 비밀이 아니고(무결성 대조용),
    셸 핸들러는 `[?&]token=([^&]+)` 로 토큰만 뽑으므로 추가 파라미터에 영향받지 않는다.

    ⚠ **`base` 를 URL 로 받는다는 것은 신뢰 판단이다.** 남이 만든 링크를 사용자가 클릭하면
    그 서버에서 러너를 받게 된다. 클라이언트는 처음 연결한 서버를 홈에 고정하고, 다른
    주소가 오면 **사용자에게 묻는다**(`core.pinned_server`). 여기서 조립만 하고 판단은
    받는 쪽이 한다 — 서버는 자기가 보낸 링크가 어디로 갈지 알 수 없기 때문이다.
    """
    import urllib.parse

    params = {"token": token}
    for key, value in (("base", base), ("ca_sha256", ca_sha256),
                       ("agent_sha256", agent_sha256)):
        if str(value or "").strip():
            params[key] = str(value).strip()
    return f"{SCHEME}://start?" + urllib.parse.urlencode(params)
