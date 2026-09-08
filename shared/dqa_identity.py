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


#: 앱 창이 열 수 있는 목적지 경로의 **길이 상한**. 스킴 URL 은 OS 를 거쳐 오므로 길이를
#: 제한하지 않으면 레지스트리·argv 경로에서 잘린 채 도착할 수 있다(잘린 경로는 다른 페이지다).
MAX_APP_PATH = 512


def safe_app_path(path: str) -> str | None:
    """앱 창이 열어도 되는 **같은 origin 안의 경로**인가. 아니면 `None`.

    ## 왜 «경로» 를 따로 검증하는가

    `scheme_url()` 의 `base` 검증(`core.usable_base`)은 **어느 서버인가**를 본다. 이 함수는
    그 서버 **안의 어디인가**를 본다 — 두 축은 다르고, base 만 검사하면 다음이 통과한다:

        dqa-connect://open?base=https://ours&path=//evil.example/x

    `//evil.example/x` 는 경로처럼 생겼지만 브라우저는 **protocol-relative URL** 로 읽어
    다른 origin 을 연다. 즉 우리 주소를 통과시킨 뒤 남의 사이트를 앱 창에 띄운다.

    ## 규칙 (조립·수용 양쪽이 같은 것을 본다)

    - 빈 값은 `/` — 목적지가 없으면 서비스 루트다(종전 동작).
    - `/` 하나로 시작해야 한다. `//` 는 위 이유로 거부.
    - `\\`(역슬래시) 거부 — 일부 브라우저가 `/` 로 정규화해 `/\\evil.example` 이 위와 같아진다.
    - `..` 거부 — origin 을 벗어나지는 못하지만, 목적지를 흐리는 경로를 받아 둘 이유가 없다.
    - **`?`·`#` 거부 — 이것이 두 번째 위험 축이다.** 이 값의 싱크는 origin 이 아니라
      `client/appwindow.panel_url` 이 **브리지 좌표를 붙이는 자리**다:

          f"{base}{path}?client_port=…&client_nonce=…"

      `path` 가 `?` 를 품으면 쿼리가 두 벌이 되고, 브라우저의 `URLSearchParams.get()` 은
      **첫 값**을 취한다 — 즉 링크를 만든 쪽이 `client_port`·`client_nonce` 를 **덮어쓴다**.
      그 좌표는 앱 창이 이 컴퓨터의 브리지를 부를 때 쓰는 자격이므로, 통과시키면 「우리
      주소로 검사를 통과한 뒤 앱이 공격자가 지정한 로컬 포트로 자기 자격을 배달」한다.
      `#` 는 반대로 진짜 좌표를 프래그먼트로 밀어내 앱 창이 자기를 앱 밖으로 판정하게 만든다.
      (적대 리뷰 2026-09-08 F1 — 실행으로 재현 확인.)
    - 제어문자(개행·NUL 포함) 거부 — 로그·argv·레지스트리 경계를 넘는 주입 표면.
    - 길이 상한 `MAX_APP_PATH`.

    ⚠ 이 함수는 **경로만** 받는다. 목적지에 쿼리를 실어야 할 필요가 생기면 그것은 별도
    파라미터로 설계할 일이지, 경로 문자열에 끼워 넣을 일이 아니다.

    ⚠ **이 규칙의 사본이 클라이언트에도 있다** (`client/core.py`). 클라이언트는 동결 배포본이라
    `shared/` 를 import 하지 않는다(`SCHEME` 리터럴과 같은 사정). 두 벌이 갈리지 않도록
    `feature-0046/tests/test_wsl_and_scheme.py` 가 양쪽을 같은 표로 대조한다.
    """
    raw = str(path or "").strip()
    if not raw:
        return "/"
    if len(raw) > MAX_APP_PATH:
        return None
    if not raw.startswith("/") or raw.startswith("//"):
        return None
    if "\\" in raw or ".." in raw:
        return None
    if "?" in raw or "#" in raw:
        return None
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw):
        return None
    return raw


def app_open_url(base: str, path: str = "/") -> str | None:
    """웹 화면이 여는 **「이 페이지를 DQA 앱에서 열어라」** 딥링크. 경로가 부적격이면 `None`.

    ## `scheme_url()` 과 무엇이 다른가 (왜 함수를 나눴나)

    | | `scheme_url()` | `app_open_url()` |
    |---|---|---|
    | 목적 | 내 AI 를 서비스에 **연결**한다 | 이미 있는 화면을 **앱 창으로 옮긴다** |
    | 토큰 | **싣는다** (러너가 그 자격으로 붙는다) | **싣지 않는다** |
    | 여는 사람 | 자기 계정 소유자 | 남이 보낸 공유 링크를 받은 사람일 수 있다 |

    **토큰을 싣지 않는 것이 핵심이다.** 이 링크는 *공유 링크를 받은 사람*의 화면에서
    만들어진다 — 그 사람의 브라우저에는 이미 로그인 세션이 있고, 앱 창은 기본 브라우저
    프로필로 열리므로 그 세션이 따라온다(`client/appwindow.py`). 여기에 베어러 토큰을 한 번
    더 실으면 **얻는 것 없이 노출 지점만 늘어난다**.

    ## 구버전 클라이언트에서 무슨 일이 일어나는가 (의도된 degrade)

    `path` 를 모르는 구버전은 `parse_scheme_url()` 이 허용 키만 뽑으므로 그 값을 **버리고**
    `base` 만 읽어 **서비스 루트**를 연다. 즉 「앱은 뜨는데 그 대화로 가지 않는다」이지
    「아무 일도 없다」가 아니다 — 사용자가 무엇을 해야 하는지는 여전히 보인다.
    """
    import urllib.parse

    safe = safe_app_path(path)
    if safe is None:
        return None
    params = {"path": safe}
    if str(base or "").strip():
        params["base"] = str(base).strip()
    return f"{SCHEME}://open?" + urllib.parse.urlencode(params)
