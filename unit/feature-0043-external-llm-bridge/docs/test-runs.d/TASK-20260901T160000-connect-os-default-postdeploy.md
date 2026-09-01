---
run_at: 2026-09-01T16:30:00+09:00
session: ai/claude/feature-0043-connect-os-postdeploy
scope: POST-DEPLOY 라이브 실측 — 기본 OS 탭이 «마지막으로 연결됐던 OS» 를 따라간다
verdict: PASS (양방향 end-to-end)
---

# Run — POST-DEPLOY (배포본 `b50513e0`)

- **Environment: Windows-browser** (`bin/win-browser.py` → 실 Windows Chrome, `navigator.platform = "Win32"`)
- 계정: `bootstrap_admin` · 러너는 **제품 경로 그대로** 붙였다(화면에서 발급한 토큰 + 배포본 러너)
- 배포: `make deploy-web` scope=all · 엣지 `no upstreams available` **0건** · 대화 스모크 PASS

## 왜 이 실측이 필요한가

이 cycle 이 만진 것은 **JS 와 신규 DB 컬럼**이다. JS 는 `docker cp` QA 가 성립하지 않고(자산
스탬프 미주입 + 브라우저 모듈 캐시로 구버전이 실행된다), 컬럼은 부트스트랩이 실제로 도는지가
바로 codex P1-1 이 지적한 지점이다 — 둘 다 **배포본에서만** 참·거짓이 갈린다.

## 1. 「모른다」 상태 — 종전 추측으로 폴백 (회귀 없음)

배포 직후, 이 계정은 아직 계열을 신고한 러너로 연결한 적이 없다.

| 관측 | 값 |
|---|---|
| `/api/ai/connect/status` → `last_os` | `""` |
| 1단계 기본 탭 | **Windows** (`#tabWin` primary) + `iwr …bridge_setup.ps1` |

→ 값이 없으면 **정확히 종전 동작**이다. 「모른다」를 한쪽으로 굳히지 않는다는 계약이 실물로 성립.

## 2. posix 방향 — WSL 러너를 실제로 붙인다

WSL(리눅스)에서 배포본 러너를 그대로 실행:

```
python3 bridge_agent.py --base https://localhost --token <화면 발급> --ca rootCA.crt --check
  → [bridge] 연결 정상. / 사용할 AI: claude     (exit 0)
python3 bridge_agent.py … (상주, 하트비트 1회 이상)
```

| 관측 | 값 |
|---|---|
| `/api/ai/connect/status` → `last_os` | **`posix`** · `listening: true` |
| `/ai/connect` 1단계 기본 탭 | **macOS·Linux** (`#tabPosix` primary) |
| 그 탭의 명령 | `curl -fsS -o bridge_setup.sh …` |
| `navigator.platform` | `Win32` — **브라우저는 여전히 Windows 다** |
| 대화 화면 모달 (`#connectModalTabPosix`) | `is-active` · 라벨 `macOS·Linux` |

→ 제보의 상황(브라우저는 Windows, 러너는 WSL)에서 **표시면 둘 다** 뒤집혔다.
그리고 이것은 `BridgeLastOs` 컬럼이 **기존 운영 DB 에 실제로 생겼다**는 증거이기도 하다
(codex P1-1 의 수정이 라이브에서 성립 — 안 생겼다면 값은 영원히 `""` 다).

## 3. windows 방향 — 사용자가 예고한 PowerShell 재등록 시나리오

> "이후 powershell 테스트를 진행하며 해당 명령문으로 다시 등록했을 때 windows로 선택되어야"

실 Windows 파이썬(`C:\…\Python314\python.exe`)으로 같은 배포본 러너를 PowerShell 에서 기동:

| 관측 | 값 |
|---|---|
| `--check` | `연결 정상. / 사용할 AI: claude` |
| `/api/ai/connect/status` → `last_os` | **`windows`** · `listening: true` |
| `/ai/connect` 1단계 기본 탭 | **Windows** + `iwr …bridge_setup.ps1` |

→ 요청의 두 방향이 **모두** 실물로 성립한다. 같은 토큰으로 계열만 바뀐 경우도 연결 사건으로
잡힌다(토큰 행 `RunnerOs` 가 달라지므로).

## 4. 사용자 조작이 이긴다

모달에서 `Windows` 탭을 직접 누르면 `is-active` 가 옮겨가고 라벨이 `Windows PowerShell` 로
바뀐다 — 서버 값과 무관하게 사용자의 선택이 유지된다.

## 미검증 · 부수 사항

- **구 러너(신고 없음)가 기존 값을 지우지 않는다**: 단위 계약으로만 잠겨 있다. 라이브에서는
  구 러너 실물을 띄우지 않았다(배포본 러너에는 이미 신고가 들어 있다).
- **두 러너 동시 진동 차단**(codex P1-2)도 단위 계약으로만 확인했다 — 라이브에서 서로 다른
  OS 의 러너를 **동시에** 살려 두는 조건은 만들지 않았다(순차로만 검증).
- 검증 중 Windows 쪽 `~/.mysql-ai-bridge/config.json` 이 러너에 의해 재작성됐다. 값은 종전과
  같은 `base`·`ca` 이고 **토큰은 들어가지 않는다**. 사용자의 설치본
  (`.mysql-ai-bridge/bridge_agent.py`)은 건드리지 않았고, 검증용 사본은 삭제했다.
