---
run_at: 2026-08-28T19:30:00+09:00
session: ai/claude/feature-0043-ai-assisted-setup
scope: 연결 모달 · /ai/connect 단독 페이지 — 셋째 경로 블록 추가
verdict: PASS
---

# Run — TASK-20260828T193000 (feature-0003 측 변경분)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) — **Windows-browser 시각검증은 배포 후로 미룸(사유 아래)**
- **대상**: 연결 화면 두 곳에 「AI에게 조사만 맡기기」 `<details>` 블록 + 복사 버튼

## 이 feature 에서 바뀐 것

| 파일 | 변경 |
|---|---|
| `static/index.html` | 연결 모달에 셋째 경로 `<details>` (①명령 → **②조사** → ③전부위임 순) |
| `static/ai-connect.html` | 단독 페이지에 같은 블록 — 문안이 갈리면 어떤 사용자는 옛 안내를 받는다 |
| `static/app/connect-modal.js` | `_launch.probe` 렌더 + 부재 시 블록 숨김 + 복사 버튼 |
| `static/ai-connect.js` | 동일 (이쪽은 non-module 스크립트) |
| `routers/oauth_as.py` | `compose_probe_setup_instruction` 신설 · `launch.probe` 응답 추가 |
| `static/agent/bridge_setup.{sh,ps1}` | 정본 동기화(배포 사본) |

화면 계약은 회귀로 잠갔다 — 두 화면 모두 블록이 있는가, probe 부재(구 서버) 시 감추는가,
그리고 **검증되지 않는 동일성("결과가 같다")을 주장하지 않는가**.

## PB-0008 Windows-browser 시각검증 — 이번 커밋에서는 미수행 (사유)

**미수행 사유: 아직 배포 전이라 라이브에 이 화면이 없다.** 이 블록은 서버 응답의 `launch.probe`
가 있어야 나타나므로, 배포되지 않은 상태에서 실 브라우저로 열면 **구 화면**을 보게 된다 —
그 확인은 이 변경에 대한 증거가 되지 못한다.

대신 다음 순서로 완결한다(이 feature 가 `a5d2e6a8` 등에서 쓴 POST-DEPLOY 패턴):

1. 이 cycle 을 머지 → 배포
2. 배포본에서 실 Windows 브라우저로 연결 모달·단독 페이지를 열어 확인
3. 결과를 POST-DEPLOY fragment 로 추가 기록

배포 전 확인한 것(브라우저 없이 가능한 축):

| 축 | 결과 |
|---|---|
| HTML `<details>` 균형 | index 3/3 · ai-connect 2/2 |
| JS 문법 | `connect-modal.js`(ESM) · `ai-connect.js` 양쪽 OK |
| 서버 산출물 | `launch.probe` 가 실제로 생성되고 빈칸이 명령에 실재 |
| 화면 계약 회귀 | 두 화면 노출 · probe 부재 시 숨김 · 동일성 주장 없음 |

확인 예정 항목(배포 후): 블록이 접힌 채로 뜨는가 · 펼치면 지시문이 보이는가 · 복사 버튼이
동작하는가 · 세 경로의 순서가 의도대로인가 · 모바일 폭에서 `<pre>` 가 넘치지 않는가.
