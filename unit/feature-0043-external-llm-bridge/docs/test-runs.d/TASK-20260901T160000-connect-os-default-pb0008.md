---
run_at: 2026-09-01T16:55:00+09:00
session: ai/claude/feature-0043-connect-os-default
scope: PB-0008 실 Windows 브라우저 — 1단계 기본 OS 탭 (PRE-DEPLOY baseline)
verdict: PASS (결함 재현)
---

# Run — PB-0008 PRE-DEPLOY baseline

- **Environment: Windows-browser** (`bin/win-browser.py`, 실 Windows Chrome →
  `https://localhost/ai/connect`, 배포본 = 현 라이브)
- 계정: `bootstrap_admin` (로그인 상태 확인 — `#connectLogin` 숨김)

## 1. 결함 재현 (수정 전 상태를 실물로 고정한다)

`[연결 준비]` 클릭 후 1단계 탭·명령 실측:

| 관측 | 값 |
|---|---|
| `#tabPosix.className` | `aic-btn` (비활성) |
| `#tabWin.className` | `aic-btn aic-btn--primary` (**선택됨**) |
| `#launchCmd` 앞 90자 | `iwr -UseBasicParsing -Uri 'http://localhost/static/agent/bridge_setup.ps1' -OutFile bridge…` |

→ 제보 그대로다: **Windows 가 항상 먼저 뽑힌다.** 이 브라우저가 Windows 에서 돌기 때문이며,
이 계정이 마지막으로 무엇으로 연결했는지와 무관하다.

## 2. 서버가 아직 그 사실을 말하지 않는다

`/api/ai/connect/status` 응답 키 실측:

```
logged_in, username, display_name, endpoint, guide, connected, listening,
ready, bridge_mode, compose_blocked, runner_stale
```

`last_os` 없음 — 화면이 추측 외에 쓸 사실이 **애초에 없었다**. 이번 변경이 그 축을 추가한다.

- 증적 스크린샷: `predeploy-osdefault.png` (세션 스크래치패드, 커밋 대상 아님)

## 3. 남은 것 (POST-DEPLOY)

배포 후 별 fragment 에 기록한다 — 실제로 러너를 붙여 `BridgeLastOs` 가 `posix` 로 새겨지고,
같은 화면이 **macOS·Linux** 를 먼저 보이는지까지.
