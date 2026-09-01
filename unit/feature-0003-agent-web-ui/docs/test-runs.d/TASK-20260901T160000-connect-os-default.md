---
run_at: 2026-09-01T16:55:00+09:00
session: ai/claude/feature-0043-connect-os-default
scope: PB-0008 — 연결 화면 1단계 기본 OS 탭 (static/ai-connect.js · static/app/connect-modal.js)
verdict: PASS (PRE-DEPLOY baseline — 결함 재현)
---

# Run — PB-0008 PRE-DEPLOY (자산 소유 feature 쪽 기록)

- **Environment: Windows-browser** (`bin/win-browser.py` → 실 Windows Chrome,
  `https://localhost/ai/connect`, 계정 `bootstrap_admin`)
- 이 cycle 이 만지는 웹 자산: `static/ai-connect.js` · `static/app/connect-modal.js`
  (동작 명세·판단 근거의 정본은 feature-0043 — 화면은 그 값을 표시만 한다)

## 실측 (수정 전 라이브 배포본)

| 관측 | 값 |
|---|---|
| `#tabWin.className` | `aic-btn aic-btn--primary` — **Windows 가 선택됨** |
| `#tabPosix.className` | `aic-btn` |
| `#launchCmd` | `iwr -UseBasicParsing -Uri 'http://localhost/static/agent/bridge_setup.ps1' …` |
| `/api/ai/connect/status` 키 | `last_os` **없음** (화면이 추측 외에 쓸 사실이 없었다) |

제보(“windows가 항상 기본적으로 선택된 상태”)가 라이브에서 그대로 재현된다.

## 남은 것

POST-DEPLOY 에서 러너를 실제로 붙여 `posix` 신고 → 같은 화면이 **macOS·Linux** 를 먼저 보이는지
확인한다. **JS 변경은 `docker cp` QA 가 성립하지 않으므로**(자산 스탬프 미주입 + 브라우저 모듈
캐시로 구버전이 실행된다) 배포 후 검증이 유일한 실물 경로다.
증적 정본: `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260901T160000-*.md`
