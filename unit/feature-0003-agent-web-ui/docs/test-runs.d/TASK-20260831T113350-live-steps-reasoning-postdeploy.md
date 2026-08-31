---
run_at: 2026-08-31T13:25:00+09:00
session: ai/claude/feature-0043-live-steps-postdeploy
scope: 브리지 실행 단계 — 추론 구간 표시 + 절단 고지 · POST-DEPLOY 시각검증
verdict: PASS
---

# Run — TASK-20260831T113350-live-steps-reasoning · **POST-DEPLOY** (배포본 `74e2672c`)

- **일시**: 2026-08-31
- **Environment**: **Windows-browser** (PB-0008) — 실제 Windows Chrome/151, 라이브 배포본
  `https://localhost` (Caddy :443 단일 문), 세션 = `bootstrap_admin`
- **대상**: 머지·배포 후 실제 사용자 표면. 직전 PRE-DEPLOY fragment 가 「JS 는 배포 전 실
  브라우저 검증 불가」로 이월한 항목을 여기서 완결한다.

## 배포 체크리스트 (feature-0014 RUNBOOK §10)

| # | 항목 | 결과 |
|---|---|---|
| 1 | web-a·web-b 가 대상 SHA + soak | PASS — `mysql-ai-web:74e2672c` ×2 |
| 1b | 대화 경로 스모크 | PASS (전환 모드 — 서버 계정 LLM 차단 확인) |
| 2 | 워커 롤아웃 | PASS — insight/ask/ops-scheduler/ext-tool-mcp-a·b 전부 `mysql-ai-agent:74e2672c` |
| 2b | surge 잔존 | 0 |
| 3 | 캐시 무효화 | PASS — `.asset-stamp = cb0480b0bd8e`, 서빙 모듈 `app.js?v=cb0480b0bd8e` (placeholder 아님) |
| 4 | 실 사용자 표면 | PASS (아래) |
| 5 | 무중단 실측 | **`no upstreams available` 0건** |

## [4] 실 사용자 표면 — 배포본에서 직접 렌더

**evidence 의 identity 대조 (§16.6 (c))**: 페이지가 실제로 로드한 모듈 URL 을 DOM 에서 읽어
그 URL 로 `import()` 했다 — 즉 **배포본과 같은 모듈 인스턴스**다. 주입한 사본이 아니다.

```
stamp   https://localhost/static/app.js?v=cb0480b0bd8e
exports openStepSidePanel · refreshStepSidePanelForRun · buildStepDetailEl · _computeStepTimings
```

### (A) 추론 구간이 보이는가 — 제보 ①의 직접 확인

브리지 진행 중 목록(도구 2회 + 추론 구간)을 배포본 렌더러에 넣고 실 화면을 캡처했다.

```
badge            5단계
cards            5        activity 배지 3
1. 13:20:00 · 12초                            내부 동작 — 질문을 가져왔습니다…
2. 13:20:12 · 0.4초 · 누적 12초                SQL 실행 — 스키마 목록을 확인한다
3. 13:20:12 · 1분 31초 · 누적 1분 43초         내부 동작 — 결과를 검토하고 다음 작업을 정합니다  ← 추론 구간
4. 13:21:43 · 0.3초 · 누적 1분 43초            SQL 실행 — users 테이블 구조를 확인한다
5. 13:21:43 · 진행 중 · 누적 1분 43초          내부 동작 — (아직 진행 중)
running 강조     rgb(29, 78, 216) / font-weight 600
```

**판정**: 도구는 자기 실측(0.4초·0.3초)을, **도구 사이의 추론 91초가 3번 카드에 붙었다**.
수정 전에는 이 91초가 어느 단계에도 없었다(하네스 T6 이 역검증). 5번 카드가 「진행 중」으로
강조되어 "아직 안 끝났다" 가 완료 단계와 구별된다.

캡처: `artifacts/pb0008-live-steps-reasoning/A-live-reasoning.png` (전체) ·
`A-live-reasoning-panel-2x.png` (**패널 2배 확대 — 판독 가능 캡처**, §16.6 escalate)

### (B) 절단이 조용하지 않은가 — 제보 ②의 남은 층

122단계 중 최신 2건만 실린 창을 렌더했다.

```
badge      122단계        ← 창 크기(2)가 아니라 **총 단계 수**
안내       "앞선 120단계는 진행 중 목록에서 생략했습니다. 답변이 도착하면 전체가 표시됩니다."
누적 표기  없음           ← 창 기준 누적을 "처음부터 누적" 으로 오표기하지 않는다
진행 중    마지막 내부 동작에 표시
```

캡처: `B-truncated.png` · `B-truncated-panel-2x.png`

### (C) 저장된 답변 경로 무회귀 — 실 데이터

라이브 대화 `20260831025448-12af0eb5` 의 저장 답변 steps(2건)를 **app.js 가 실제로 쓰는 호출
형태**(`{steps, runId, convId}` — `live`/`omitted` 없음)로 열었다.

```
badge 2단계 · cards 2 · 생략 안내 0 · 진행중 표시 0 · 누적 표기 있음
times ["11:54:49 · 1.0초", "11:54:50 · 누적 1.0초"]
```

새 인자의 기본값이 종전 동작을 그대로 재현한다 — 완료본 화면은 바뀌지 않았다.

## 미수행 (정직 표기)

- **개인 AI 러너를 실제로 띄운 end-to-end 왕복** — 사용자 머신의 AI CLI + 새 `mat_` 토큰이
  필요해 AI 가 무인으로 완결할 수 없다. 즉 「러너가 도구를 여러 번 부르는 동안 회선을 끊어
  재접속을 눈으로 관측」하는 축은 여기서 확인하지 못했다. 그 축은 node 하네스 S1~S8 이
  **정본 함수 수준**에서 덮고, 그중 S6 은 옛 코드에서 실제로 FAIL 함을 실증한다.
- 위 (A)·(B) 의 단계 데이터는 **서버가 지금 내보내는 모양 그대로**를 넣은 것이지 라이브 조사가
  만든 행은 아니다. 서버가 그 모양을 만든다는 것은 `test_bridge_live_steps_window.py` 가
  실제 함수 실행으로 확인한다(도구 1회 → tool 단계 + 추론 구간, 창·생략 수 파생).

## 잔류물

없음. 검증은 **읽기 + 클라이언트 렌더**만 했고 대화·첨부·DB 를 변경하지 않았다.
사이드 패널은 검증 후 닫아 원상 복구했다. 캡처 파일은 git 밖 `artifacts/` 에 있다(§2).
