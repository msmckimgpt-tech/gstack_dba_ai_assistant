---
run_at: 2026-09-03T12:42:00+09:00
session: ai/claude-corp/feature-0043-ai-ready-postdeploy
scope: 연결 칩 「답할 수 없음」 POST-DEPLOY 실 Windows 브라우저 실측 (배포 8da226b5)
verdict: PASS
---

# Run — TASK-20260903T180000 POST-DEPLOY (PB-0008)

직전 fragment 는 `verdict: PARTIAL` 이었다 — 새 상태의 입력이 이번 cycle 이 추가하는 서버
컬럼이라 배포 전에는 그 분기를 **원리적으로 재현할 수 없었다.** 배포 후 그것을 실측한다.

## Environment

- 배포 `8da226b5` (전 서비스 7개 동일 SHA)
- **Environment: Windows-browser** — `bin/win-browser.py` (실 Windows Chrome), `https://localhost/`
- 로그인 계정: `bootstrap_admin`(id=1) — **사용자 계정(`admin`, id=10)을 빌리지 않았다**.
  대신 그 계정에 **조건을 직접 구성**했다(아래 §2) — DB 를 손으로 조작하지 않고 러너→서버→
  화면 전 경로를 실제로 통과시켰으므로 배선이 진짜로 이어졌는지 증명된다.

## 1. 배포 전/후 대조 (배선 증거)

| 관측 | 배포 전 | 배포 후 |
|---|---|---|
| `connect_status` 의 `ai_ready` 키 | **부재** | **존재** (`has_ai_ready: true`) |
| 그 값 | — | `null` = 「모른다」 (**tri-state 보존**) |
| `WebOAuthTokens.RunnerAiReady` | — | `tinyint(1)` **NULL 허용** |
| `WebOAuthTokens.RunnerAiUnreadyReason` | — | `varchar(300)` NULL 허용 |
| 칩 (러너 없는 계정) | 「대기 안 함」 | 「대기 안 함」 (무회귀) |

**fast-path ALTER 가 실제 운영 DB 에 적용됐다** — `BridgeDefaultModel` 선례(slow path 전용이면
컬럼이 안 생겨 「테스트 전통과 + 기능 영구 폴백」)의 함정을 실물로 피한 것을 확인.

## 2. ⭐ 조건 구성 + 대조군 (인과 증명)

같은 계정·같은 토큰으로 **AI 의 응답성만** 바꿨다. 가짜 AI 2종을 만들어 PATH 로 주입:

- `dead/claude` — `--version`·`--help` 는 답하고 실제 질의는 **응답하지 않는다**(라이브
  `claude.exe` 와 같은 결말)
- `live/claude` — 능력 질의에 정상 JSON 을 답한다

| 조건 | 러너 협상 | 서버 저장 | **실 브라우저 칩** |
|---|---|---|---|
| 응답 없는 AI | `TimeoutExpired` | `RunnerAiReady=**0**` + 사유 | **「답할 수 없음」** `state=off` |
| 응답하는 AI (**대조군**) | 성공(모델 1종) | `RunnerAiReady=**1**`, 사유 없음 | **「대기 중」** `state=on` |

칩 `title` 실측(응답 없는 조건):

```
이 컴퓨터의 claude 가 응답하지 않습니다 — TimeoutExpired: Command '['/tmp/fakeai/dead/claude',
 '-p', '--strict-mcp-config', …
```

**대조군이 load-bearing 이다.** 「답할 수 없음」만 보면 「칩이 원래 그렇게 나오는 것」과
구분되지 않는다. 같은 토큰에서 응답성만 바꿔 양방향 전이를 관측했으므로 이 표시가 이
배선의 결과임이 증명된다. (이 세션에서 대조군 없이 단정해 두 번 틀린 이력이 있다 —
「무중단」·「자동 갱신 미발동」.)

## 3. tri-state 무회귀 (실측)

같은 계정의 **이전 토큰**(Id=216, 이 축을 신고하지 않은 러너)은 `RunnerAiReady = NULL` 로
남았고, 러너 없는 계정의 `connect_status.ai_ready` 는 `null` 이었으며 칩은 종전 상태를
유지했다 — 구 러너 사용자가 미연결로 오분류되지 않는다.

## 4. 정리 (검증 흔적 제거)

- 테스트 러너 프로세스 **0** (잔존 확인)
- 가짜 AI 디렉토리 삭제 (`/tmp/fakeai`)
- 테스트용 브리지 토큰 **폐기**(Id=238 `RevokedAt` 설정) — 그 러너가 배경 작업을 계속
  집어가지 않도록. 사용자 계정(10)의 러너·토큰은 **건드리지 않았다.**

## 5. 이 Run 이 덮지 못한 것

- 「모른다」(협상 진행 중) 창의 화면 표시 — **미구현 축**이므로 검증 대상이 아니다
  (`TASK-20260903T180000` §6 이월). 재기동 직후 첫 질문 200초 침묵은 그대로 남아 있다.
- 사용자 계정(10)의 실제 화면 — 자격증명 없이 접근하지 않았다. 그 계정의 러너는 현재
  `claude` OAuth 만료로 협상이 실패하므로, 다음 하트비트에 같은 표시가 나타날 것이다
  (같은 코드 경로 · 위 §2 로 그 경로가 실증됨).
