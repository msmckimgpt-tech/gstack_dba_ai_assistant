# Run — TASK-20260828T170000-runtime-model-selector (web 자산 측)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) — **Windows-browser: 미수행(사유 아래)**
- **대상 web 자산**: `static/app/composer.js`(모델·추론등급 렌더) ·
  `routers/system.py`(카탈로그 응답) · `static/agent/bridge_agent.py`(배포 러너 사본)

## 결과

`make test` 전량 PASS (exit 0) · ruff clean. 화면 배선은 소스 계약으로 잠갔다 —
`test_runtime_model_selector.py` 의 composer 3건(등급 목록 출처 · `model_selector_source`
명시값 판정 · 모델 변경 시 등급 재렌더)과 `test_model_catalog_bridge_mode.py` 의 반환값 삼중 계약.

## Windows-browser 시각검증 미수행 — 사유

`visual_verification_scope: always` 대상이 맞다. 그럼에도 이번 cycle 의 커밋 시점에는 수행할 수
없다. **이 화면은 배포만으로 나타나지 않기 때문이다.**

선택기가 보이려면 세 가지가 순서대로 성립해야 한다:

1. 새 코드 배포 (카탈로그가 신고를 읽을 수 있게)
2. 사용자가 **새 러너 사본을 받아 재기동** (`/static/agent/bridge_agent.py` 가 바뀌었다)
3. 그 러너의 하트비트가 도착해 `RunnerCapabilities` 가 채워짐

2번에는 **새 `mat_` 토큰**이 필요하다 — 러너는 토큰을 저장하지 않으므로 브라우저 로그인 후
`/ai/connect` 에서 재발급해야 한다. 즉 AI 가 무인으로 완결할 수 있는 경로가 아니다.

배포 직후 러너 재기동 이전에 화면을 열면 **선택기는 정상적으로 숨겨져 있다**(신고가 없으므로).
그 상태의 화면 확인은 "신고 없음 → hidden" 이라는 계약의 한쪽만 검증한다 — 무가치하지는 않으나
이번 변경의 요지(선택기 노출·플랫폼 그룹·런타임별 등급)는 확인하지 못한다.

→ **배포 후 러너 재기동을 마친 시점에 PB-0008 시각검증을 수행하고 이 fragment 에 Run 을
추가한다.** 그 전까지 이 항목은 미검증이며, 그렇게 표기한다(직전 cycle TASK-20260828T120000 에서
"소스는 green 인데 화면에는 옛 문안" 이 드러난 전례가 있어, 소스 green 을 화면 확인으로
대신하지 않는다).

## 확인한 사실 (증거)

- 카탈로그 응답 3갈래를 반환값으로 단정 — 신고없음 `hidden` / 신고있음 `visible` +
  `runtime:model` 접두 + `group` = 런타임 라벨 + `reasoning_levels_by_runtime` / 게이트 해제 시
  원래 서버 카탈로그 복원.
- 프런트 숨김 가드(`_composerModelSelectorHidden`)와 메뉴 열기 가드는 **손대지 않았다** —
  서버가 `visible` 을 실을 때만 풀린다. 즉 화면이 스스로 판정을 만들지 않는다.
- `composer.js` ESM 구문 검사 통과(`node --check`).
