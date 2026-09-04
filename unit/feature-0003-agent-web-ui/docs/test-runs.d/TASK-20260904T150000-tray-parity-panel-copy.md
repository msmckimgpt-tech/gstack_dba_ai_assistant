---
run_at: 2026-09-04T15:30:00+09:00
session: ai/claude/feature-0046-tray-background
scope: static/ai-connect.{js,html} — 클라이언트 패널 상주 안내 문구
verdict: PASS (Windows-browser 미수행 — 사유 명시)
---

# Run — 클라이언트 패널 상주 안내 (feature-0046 재구성의 웹 표면)

## 변경

`#clientPanel` 에 `#clientResidency` 한 줄을 추가하고, `paintResidency(resident)` 가
`status.resident` 를 받아 두 문구를 **갈라 말한다**:

- `resident=true` → 「이 창을 닫아도 알림 영역에서 연결이 유지됩니다. 완전히 끝내려면
  알림 영역 아이콘에서 [종료] 를 누르세요.」
- `resident=false` → 「이 창을 닫으면 연결이 끝납니다.」

판정 근거는 **브리지가 세운 사실 하나**다(`br.resident = tray is not None`). 프런트가
추정하면 트레이 없는 머신에서 거짓이 되고, 사용자는 창을 닫고 연결을 잃는다(P0-R).

## 검증

- **DOM 렌더 확인** (`unit/feature-0046-native-client/tests/verify_residency_dom.mjs`, jsdom):
  실제 마크업에 함수를 물려 두 경우를 그리고 결과 텍스트를 대조. `#clientResidency` 가
  마크업에 **실재**함도 함께 확인.
- **대조군**: 두 분기를 같은 문구로 바꾸면 FAIL(exit=1) — 검사가 실제로 결함을 잡는다.
  추출 파손(exit=2)과 결함(exit=1)의 종료코드를 갈라, 「무엇을 잡았는지」가 구별된다.
- pytest 계약 테스트 2건이 CI 에서 함께 돈다(문구 분기 존재 · 대상 요소 실재).

## ⛔ Environment: Windows-browser — **미수행**, 사유

이 패널은 `?client_port=&client_nonce=` 가 붙었을 때만 나타나고, 그 값은 **Windows 에서
도는 네이티브 클라이언트의 브리지**가 만든다. 화면을 띄우려면 ① 유효한 연결 토큰으로
클라이언트를 기동하고 ② 그 브리지에 붙은 앱 창을 열어야 하는데, **이 세션에는 유효 토큰이
없다**. 또한 바뀐 `static/` 을 라이브에 반영하려면 **병렬 세션이 공유하는 web 컨테이너**를
건드려야 하므로 §13.2.9(배포 단계 격리)가 금지한다.

⚠ 위 DOM 확인은 「무엇이 그려지는가」(이 변경의 위험 축 = 문구 분기)를 실측한 것이고,
**PB-0008 을 대체하지 않는다**. 라이브 왕복이 가능한 다음 cycle 에서 수행한다.
