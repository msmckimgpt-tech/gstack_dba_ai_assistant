---
run_at: 2026-08-31T11:33:50+09:00
session: ai/claude/feature-0043-live-steps-reasoning
scope: 브리지 실행 단계 — 추론 구간 표시(R1) + 진행 갱신 중단 해소(R2)
verdict: PASS (자동) · Windows-browser 는 POST-DEPLOY 로 이월(사유 아래)
---

# Run — TASK-20260831T113350-live-steps-reasoning (PRE-DEPLOY)

- **일시**: 2026-08-31
- **대상**: `routers/ai_tools.py` · `static/app.js` · `static/app/composer.js` · `static/css/chat.css`

## 1. 컨테이너 pytest — 전량 green

`mysql-ai-agent:dae0903d` 이미지에 worktree 마운트(`PYTHONDONTWRITEBYTECODE=1`), `make test`
와 같은 격리 env(`DB_PORT=1` 등).

```
unit/feature-0002-agent-core/tests  unit/feature-0003-agent-web-ui/tests
unit/feature-0023-…  unit/feature-0014-…  unit/feature-0020-…
unit/feature-0041-…  unit/feature-0043-…  unit/feature-0008-…
→ 전량 PASS (F 0건)
```

신규 25건:

| 파일 | 축 |
|---|---|
| `feature-0003/tests/test_bridge_live_steps_window.py` (12) | 추론 구간 기록(W1) · 최신 쪽 창 + 생략 수 파생(W2) · 커넥션 close(W3) · 폴링/스트림 필드 동형 |
| `feature-0043/tests/test_live_steps_progress_continuity.py` (13) | abort↔오류 분리 · 시간 예산 · 단조 시계 · 횟수 상한 ≥ 시간 예산 · 절단 고지 · 진행 중 표기 |

기존 계약 2건은 **새 계약에 맞춰 갱신**(회피가 아니라 정정):
`test_live_steps_in_panel.py::test_steps_button_count_and_source_are_updated_together`
(개수 = 창 크기 → **총 단계 수**), `test_bridge_interrupt_stream.py::test_stream_skips_pointless_queries_before_claim`
(반환 모양 `[]` → `([], 0)`; 잠그는 계약은 동일).

## 2. node 동작 하네스 — 18/18

```
$ node unit/feature-0003-agent-web-ui/tests/verify_bridge_live_step_progress.mjs
  PASS  T1 첫 추론(질문 수령 → 첫 도구)이 10초로 잡힌다
  PASS  T2 도구 소요는 도구 자기 실측이다(0.4초·0.3초)
  PASS  T3 **도구 사이 추론 90초**가 그 구간 단계에 붙는다 (제보의 핵심)
  PASS  T4 도구 실행분을 뺀 값이라 근사가 아니다
  PASS  T5 진행 중 마지막 단계는 소요를 지어내지 않는다
  PASS  T7 병렬 도구 구간이 가짜 추론 시간으로 새지 않는다(0 으로 clamp)
  PASS  T6 (역검증) 추론 구간 단계가 없으면 90초가 어느 단계에도 귀속되지 않는다
  PASS  S1 회선 오류 → "error"(재접속 대상)
  PASS  S2 사용자 취소 → "aborted"(종결)
  PASS  S3 회선 오류 뒤 **다시 붙는다**(스트림 2회 시도)
  PASS  S3b 최종적으로 정상 종결로 보고한다
  PASS  S3c 오류 전에 받은 단계는 화면에 반영됐다
  PASS  S4 연속 회선 오류 → false(폴링 강등)
  PASS  S5 감시 예산이 30분(시간 기준)으로 선언돼 있다
  PASS  S5b 횟수 상한이 시간 예산보다 먼저 닿지 않는다
  PASS  S7 getReader() 실패도 "error" 로 수렴한다(예외가 재시도 로직을 우회하지 않는다)
  PASS  S8 감시 예산이 단조 시계(performance.now)를 쓴다
  PASS  S6 (역검증) 옛 코드에서는 오류 1회로 감시가 끝난다 — 이 하네스가 그 결함을 잡는다

  18 passed, 0 failed
```

정본 함수를 **소스에서 추출해 그대로 실행**한다(로직 재구현 0). **뮤테이션 역검증 2종**:

- **T6** — 추론 구간 단계를 빼면(수정 전 동작) 90초가 어느 단계에도 귀속되지 않는다
  (귀속 합계 10.7초 vs 지금 100.7초).
- **S6** — `catch` 를 옛 코드(`return "aborted"`)로 되돌린 사본에서 스트림 재접속이 일어나지
  않는다(시도 1회). 즉 이 하네스는 그 결함을 **실제로 잡는다**(§16.7 G11-b).

## 3. Environment: Windows-browser — **미수행 (POST-DEPLOY 로 이월)**

**사유**: 이번 변경의 실질은 **JS**(`app.js`·`app/composer.js`)다. 이 저장소에서 미머지 JS 는
실 브라우저로 검증할 수 없다 — `docker cp` 로 web-a/b 에 넣어도 빌드 시 주입되는 자산 스탬프
(`?v=<hash>`)가 없어 **브라우저 모듈 캐시가 구버전을 계속 실행**하고, 서버 파일이 신버전이어도
화면은 옛 코드다(기록된 함정). CSS 만이 cp 로 안전하다.

따라서 `deploy_scope: included` 에 따라 머지·배포한 뒤 **배포본**에서 PB-0008 을 수행하고
`TASK-20260831T113350-live-steps-reasoning-postdeploy.md` fragment 로 기록한다. 그 시점까지
본 cycle 의 시각검증은 **미충족**으로 표기한다 — 자동 검증 통과를 시각검증으로 갈음하지 않는다.

**POST-DEPLOY 에서 볼 것**:

1. 「단계 보기」 사이드 패널에 **추론 구간 카드**(「내부 동작 — 결과를 검토하고 다음 작업을
   정합니다」)가 도구 카드 사이에 그려지고 소요가 붙는가 (판독 가능한 시각 캡처).
2. 진행 중 마지막 단계에 **「진행 중」** 이 강조색으로 표시되는가.
3. 생략 안내 1줄과 「단계 보기 (총 N)」 개수가 창 크기가 아니라 총 수인가.
4. 라이브 배포본의 자산 스탬프가 placeholder 가 아닌가.

**여전히 무인 완결 불가한 것 (정직 표기)**: 실제 개인 AI 러너를 띄워 도구를 여러 번 호출시키고
그 사이 회선을 끊어 재접속을 관측하는 **완전 end-to-end 왕복**은 사용자 머신의 AI CLI + 새
`mat_` 토큰이 필요하다. 그 축은 위 자동 검증(하네스 S1~S8)이 함수 수준에서 덮는다.
