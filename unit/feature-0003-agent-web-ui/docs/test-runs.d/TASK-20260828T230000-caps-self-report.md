# Run — TASK-20260828T230000-caps-self-report (web 자산 측)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) — **Windows-browser: 미수행(사유 아래)**
- **대상 web 자산**: `static/agent/bridge_agent.py` (배포되는 러너 사본만 — 이번 cycle 은
  서버·프런트 코드를 바꾸지 않았다)

## 결과

`make test` 전량 PASS (exit 0) · ruff clean.

이번 변경은 **러너 안에서 끝난다**. 서버가 받는 신고의 모양(`{runtime,label,models,efforts}`)도,
카탈로그·컴포저 계약도 P0-Z3 그대로다 — 달라진 것은 그 목록의 *내용을 누가 정하는가* 이고,
그것은 서버에게 보이지 않는다. 그래서 화면 로직 변경이 0 이다.

## Windows-browser 시각검증 미수행 — 사유

`visual_verification_scope: always` 대상이 맞다(`static/` 아래 파일이 바뀌었다). 그러나 이
파일은 **브라우저가 렌더하는 자산이 아니라 사용자가 내려받는 스크립트**이고, 화면에 영향을
주려면 다음이 순서대로 성립해야 한다:

1. 배포 (새 러너가 `/static/agent/bridge_agent.py` 로 서빙됨)
2. 사용자가 그 사본을 받아 **재기동** (새 `mat_` 토큰 필요 — 러너는 토큰을 저장하지 않는다)
3. 최초 기동에서 각 AI 에게 질의(2~3분) → 하트비트로 신고 도착

3번까지 끝나야 화면의 모델 목록이 "AI 가 답한 것" 으로 바뀐다. 그 전까지는 **구 러너의 신고
(내장 표 기반)가 그대로 보인다** — 즉 배포 직후 화면 확인은 이번 변경의 효과를 보여주지 못한다.

→ 배포 + 사용자 재기동 후 PB-0008 로 확인하고 이 fragment 에 Run 을 추가한다.

## 확인한 사실 (증거)

- 러너 정본/배포본 byte-identical (`test_runner_copies_are_byte_identical`).
- 서버로 나가는 신고에 호출법(플래그)이 **없음**을 실측 — 화면·서버 계약 불변의 근거.
- 러너 stdlib 전용 계약 유지(`re` 추가, 표준 라이브러리이므로 무설치 계약 그대로).
