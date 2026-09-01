# TASK-20260901T140000-orphan-claim-reclaim — PRE-DEPLOY 라이브 화면 확인 (PB-0008)

- **Environment: Windows-browser** (`bin/win-browser.py` relay → Chrome/151.0.7922.170,
  `https://localhost/` · 계정 `bootstrap_admin`)
- **일시**: 2026-09-01 14:12~14:15 KST
- **배포본**: `7fb2dca4` · 자산 스탬프 `static/app.js?v=da49561ff923`

이 cycle 은 브리지 고아 점유 회수 + 무진행 국면(`stalled`) 을 넣는다. feature-0003 소유
파일이 함께 바뀌었으므로(`routers/ai_tools.py` · `static/app/composer.js` ·
`static/agent/bridge_agent.py`) 같은 Run 을 이쪽에도 기록한다.

**정본 증적 (표·스크린샷·별건 발견 전문)**:
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260901T140000-orphan-claim-reclaim.md`

요지:

| 축 | 결과 |
|---|---|
| 배포본 서버 `stalled` (`grep -c`) | **0** — 무진행을 말할 축이 아예 없다(baseline) |
| 배포본 `composer.js` 의 `phase === "stalled"` | **0** |
| 제보 대화 말풍선 6건 실측 | 12:07 질문은 **답 없이** 대체 · 13:34·13:40 답변은 **거부** |
| 컴포저 상단 | 「내 AI가 실행 중이 아닙니다」 (연결 축/러너 축 분리는 이미 동작) |
| 스크린샷 | `/tmp/pb0008-pre-orphan.png` (1902×946 전체) |

**범위 정직 표기**: 이번 변경의 화면 축은 배포 전에 잴 수 없다 — JS 는 `docker cp` QA 에서
자산 스탬프가 주입되지 않아 브라우저가 구 모듈을 캐시에서 실행한다(이 저장소의 기록된 함정).
고쳐졌다는 확인은 POST-DEPLOY fragment 가 맡는다(확인 항목 4건은 정본 증적 §5 에 예약).
