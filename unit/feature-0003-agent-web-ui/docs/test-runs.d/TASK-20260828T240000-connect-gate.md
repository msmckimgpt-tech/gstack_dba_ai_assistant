# Run — TASK-20260828T240000-connect-gate (feature-0043 P0-AB·P0-AC 의 웹 자산 축)

- **일시**: 2026-08-28
- **Environment**: **Windows-browser** (PB-0008) + container (`make test`)
- **대상**: 이 feature 의 웹 자산 변경 — `index.html`(잠금 안내 패널·모달 재구성) ·
  `app/connect-modal.js` · `app/composer.js` · `app.js` · `css/chat.css` · `css/search-audit.css`

정본 Run 기록은 **feature-0043** 에 있다(계약·설계가 그쪽 소유):
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260828T240000-connect-gate.md`.
여기에는 이 feature 의 자산이 실제 화면에서 어떻게 나왔는지만 남긴다.

## 실측 (라이브 무접촉 — 라이브 web 이미지 + 이 브랜치 `routers/`·`static/` bind-mount)

| 확인 | 결과 |
|---|---|
| 잠금 패널 렌더 · 사유별 문구 | PASS — "내 AI가 실행 중이 아닙니다" / "내 AI 실행하기" |
| 입력창·전송 버튼·컴포저 잠금 | PASS — `inputDisabled:true` · `sendAria:"true"` · `is-bridge-locked` |
| 패널 위치(입력창 **위**) | PASS — `gateTop 757 < boxTop 831` |
| 해제 시 활성화 | PASS — `gateHidden:true` · `inputDisabled:false` · `conn:"내 AI 대기 중"` |
| 연결 모달(명령 우선·OS 탭·복사·[내 AI 실행]) | PASS |
| 연결 상태 칩 가시 | **초기 FAIL → 수정 후 PASS** (아래) |

## 이 feature 의 자산에서 드러난 결함 2건

1. **`#aiConnState` 가 한 번도 보이지 않았다** — `.composer-footer:has(…)` 접힘 규칙이
   status·hint 가 비고 provider 상태점이 숨겨졌을 때 footer 를 통째로 `display:none` 으로
   만드는데, **그게 평상시 화면**이다. 칩은 `inline-block` 으로 살아 있었고 부모만 접혀 있었다.
   → `chat.css` 접힘 조건에 `:has(.ai-conn.hidden)` 추가. 재검증 `footerDisp:"flex"`.
   P0-T 가 약속한 "연결 상태 상시 표시" 가 그동안 화면에 도달하지 못했다는 뜻이다.
2. **안내 패널이 입력창 아래** — 잠긴 입력창을 먼저 만나 고장으로 읽은 뒤에야 사유를 본다.
   → 다른 배너(provider 제한·실행시간 연장)와 같은 자리로 이동.

## 미수행 (정직 표기)

- 실 러너 기동 후의 해제·프로토콜 핸들러 등록은 사용자 머신이 필요해 미수행.
  화면 거동(서버가 `compose_blocked:false` 를 줄 때 잠금이 풀리는가)은 실제 브라우저로 구동함.
- 검증 중 브라우저가 구 `chat.css` 를 캐시해 캐시버스트 후 재확인. 배포본은
  `inject_asset_stamp.py` 가 스탬프를 새로 주입하므로 해당 없음.
