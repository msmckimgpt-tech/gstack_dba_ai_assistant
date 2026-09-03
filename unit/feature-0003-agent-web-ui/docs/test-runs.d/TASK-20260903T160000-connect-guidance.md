---
run_at: 2026-09-03T16:00:00+09:00
session: ai/claude/feature-0043-connect-guidance
scope: /ai/connect 연결 단계 체크리스트 + 클라이언트 우선 안내 (ROADMAP ITEM-03·ITEM-06)
verdict: PASS
---

# Run — PB-0008 실 Windows 브라우저 시각검증

**Environment: Windows-browser** (실 Windows Chrome 152.0.7977.75, WSL→CDP relay,
전용 프로필 `win-browser-cdp`, `WIN_BROWSER_HOST_MAP` 으로 호스트 해석)

## 방법 — 무접촉 미리보기

미머지 브랜치이므로 라이브 `web-a`·`web-b` 에 변경 파일만 임시 주입하고(`docker cp`) 재기동해
확인한 뒤, **배포 이미지로 재생성해 원복**했다(원복 후 `healthz 200` 확인). 저장소·이미지는
무접촉이다.

⚠ 처음에 **web-a 만** 주입했더니 Caddy 로드밸런싱으로 web-b 가 응답해 화면이 그대로였다 —
두 replica 를 모두 맞춰야 미리보기가 성립한다.

## 관측

| 상태 | 결과 |
|---|---|
| 비로그인 | 체크리스트·클라이언트 섹션 **양쪽 숨김** — 구 서버/미인증에서 거짓 경보 없음 |
| 로그인 (bootstrap_admin) | 요약 「연결 정보 발급 차례입니다」 + 4행 렌더 |
| 4행 내용 | `⏳ 연결 정보 발급` · `⏳ 내 컴퓨터가 듣는 중` · `⏳ 답할 AI 있음` · `⏳ 첫 답변 받음` (각 행 아래 다음 행동 문장) |
| API 응답 | `steps` 4건 · `steps_summary` · `client_download: null` |
| 클라이언트 섹션 | **숨김** — 배포 채널이 없어 `client_download` 가 `null`. 종전 터미널 경로 유지(설계대로) |
| 기존 UI | 배경 작업 동의 토글·토큰 경고 박스 불변 |

스크린샷 확보(53,017 bytes).

## ⚠ 이 검증이 잡은 결함 2건 (단위 테스트는 green 이었다)

1. **`bridge_heartbeat` 의 `NameError`** — 존재하지 않는 `account` 를 퍼널에 넘겼고 fail-open 이
   삼켜 `first_heartbeat` 가 **한 번도 기록되지 않았다**(ITEM-00 회귀, main 반영분). 라이브 로그
   `하트비트 기록 실패 account=10: NameError` 에서 드러났다.
2. **`/api/ai/connect/status` 500** — `_reported_caps` 가 조건부 블록 안에서만 대입되는데 새
   코드가 무조건 읽었다. 브라우저가 받는 응답이 `Internal Server Error` 인 것으로 확인.

둘 다 수정 후 **재주입·재검증**해 위 관측을 얻었다.

## 미수행

연결 완주(토큰 발급 → 러너 기동 → 첫 답변)까지의 상태 전이는 **미관측** — 실 러너 왕복이
필요하다. 각 상태의 판정 자체는 단위 테스트 16건이 잠근다.
