---
run_at: 2026-08-31T17:36:00+09:00
session: ai/claude/feature-0043-compact-evidence
scope: 추론 구간 한 줄 표시 + 실시간 누적 티커 + 말풍선 목록 제외 · POST-DEPLOY 시각검증
verdict: PASS
---

# Run — TASK-20260831T170034-live-steps-compact · **POST-DEPLOY**

- **일시**: 2026-08-31
- **Environment**: **Windows-browser** (PB-0008) — 실제 Windows Chrome/151, 라이브 `https://localhost`,
  세션 `bootstrap_admin`
- **배포본**: `mysql-ai-web:21fadc7b` ×2 · 워커 `mysql-ai-agent:7c047dcf`
  — `21fadc7b` 는 본 cycle 머지 커밋 `7c047dcf` 의 **자손**(`git merge-base --is-ancestor` 확인).
  병렬 세션이 상위 SHA 로 재배포해 web 이 더 앞선 커밋이며, 본 변경은 그 안에 포함된다.

## evidence 의 identity 대조 (§16.6 (c))

배포본이 **실제로 서빙하는 모듈**에 이번 변경의 식별자가 있는지 직접 확인했다 — "배포했다" 와
"도달했다" 를 구분한다.

```
GET /static/app.js?v=034db1e69d81            → _buildStepActivityRow·_paintStepPanelLiveTimes·dataset.liveFrom  7 hits
GET /static/app/messages.js?v=034db1e69d81   → bubbleVisibleSteps                                               3 hits
```

렌더는 페이지가 로드한 그 URL 로 `import()` 해 **같은 모듈 인스턴스**로 수행했다(주입 사본 아님).

## 배포 체크리스트

| # | 항목 | 결과 |
|---|---|---|
| 1 | web replica 2대 동일 SHA + soak | PASS |
| 1b | 대화 경로 스모크 | PASS (전환 모드 — 서버 계정 LLM 차단 확인) |
| 2 | 워커 롤아웃 | PASS — insight/ask/ops-scheduler/ext-tool-mcp-a·b = `7c047dcf` |
| 2b | surge 잔존 | 0 |
| 3 | 캐시 무효화 | PASS — 서빙 stamp `034db1e69d81`(placeholder 아님) |
| 4 | 실 사용자 표면 | PASS — 아래 5개 표시면 |
| 5 | 무중단 실측 | **`no upstreams available` 0건** |

> ⚠ **CI 는 이번 랜딩의 게이트가 아니었다.** 2026-08-31 07:50 이후 `main` 을 포함한 모든
> GitHub Actions 실행이 계정 결제/한도 사유로 **러너 시작 전에** 실패했다(2초, `The job was not
> started because recent account payments have failed…`). 사용자 결정으로 Actions 를 게이트에서
> 제외하고 진행했으며, 대체 근거는 **CI 와 동일한 8개 테스트 디렉토리를 동일 격리 env 로
> 머지 base 에서 컨테이너 실행**한 결과(전량 green)다. 회피가 아니라 **같은 스위트를 다른
> 러너에서** 돌린 것이다.

## [4] 표시면 5개 — 미리 열거한 대로 (직전 cycle 의 누락 재발 방지)

직전 cycle 은 사이드 패널만 확대 캡처하고 **접힌 말풍선 여닫이를 보지 않아** 반복 노이즈를
놓쳤다. 그래서 이번엔 PRE-DEPLOY fragment 에 볼 표시면을 먼저 적어 두고 그대로 확인했다.

### ① 내부 동작이 한 줄인가 · 외곽선·배경이 없는가

```
activityRows      3          toolCards 2
activityHeights   [22, 22, 22] px        ← 한 줄
toolCardHeights   [121, 121] px          ← 카드는 그대로
activityStyle     border: none 0px · background: rgba(0, 0, 0, 0)
activityBadge     0건        ← 「내부 동작」 배지 제거
```

행 높이 **22px vs 카드 121px**. 사용자가 지적한 "비교적 큰 범위" 가 실측으로 해소됐다.
긴 문구는 ellipsis 로 접힌다(`질문을 가져왔습니다 — 대화 맥락과 첨부를 확인합니…`).

캡처: `artifacts/pb0008-live-steps-compact/compact-live.png` ·
`compact-live-panel-2x.png` (**패널 2배 확대 — 판독 가능 캡처**)

### ② 최하단 누적이 실시간으로 갱신되는가

같은 화면에서 3.2초 간격 3회 판독:

```
t1   진행 중 1분 34초 · 누적 3분 18초
t2   진행 중 1분 38초 · 누적 3분 22초
t3   진행 중 1분 41초 · 누적 3분 25초
```

증가폭이 경과와 일치한다. 산출은 사용자가 지정한 그대로 `지금 − 첫 단계 기록 시각`.

### ③ 말풍선 「▼ 쿼리 결과」 목록에 내부 동작이 없는가

```
summary               "쿼리 결과"
activityRows          0
activityBadges        0
「결과를 검토하고 다음 작업을 정합니다」 등장 횟수   0    ← 제보 화면의 ×8 소멸
```

### ④ 내부 동작만 있는 시점에 빈 확장이 생기지 않는가

```
renderMessageDetails({ steps: 내부동작만 })  →  null (여닫이 없음)
```

codex 1R P2 로 잡힌 경계다 — 여닫이만 생기고 본문이 비면 눌러 봐야 빈 칸을 본다.

### ⑤ 완료된 답변 패널은 정지 화면인가

```
liveNodes  0        ([data-live-from] 없음 = 티커 대상 없음)
2.6초 후 값 동일    frozen: true
```

흐르는 숫자는 끝난 run 에서 거짓이 된다 — 정지 화면이 맞다. 또한 마지막 내부 동작에 후속
기록이 없으면 **소요 칸 자체를 만들지 않는다**(모르는 값을 지어내지 않는다).

## 미수행 (정직 표기)

- **실 러너 end-to-end 왕복** — 사용자 머신 AI CLI + 새 `mat_` 토큰이 필요해 무인 완결 불가.
  위 ①~⑤ 의 단계 데이터는 **서버가 지금 내보내는 모양 그대로**를 배포본 렌더러에 넣은 것이며,
  서버가 그 모양을 만든다는 사실은 `test_bridge_live_steps_window.py` 가 실제 함수 실행으로
  확인한다.

## 잔류물

없음. 읽기 + 클라이언트 렌더만 했고 대화·첨부·DB 를 변경하지 않았다. 임시 핸들(`window.__pb`)과
패널은 검증 후 정리했다. 캡처는 git 밖 `artifacts/` (§2).
