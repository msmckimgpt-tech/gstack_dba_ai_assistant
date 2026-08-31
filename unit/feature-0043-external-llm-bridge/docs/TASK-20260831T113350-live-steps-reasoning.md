# TASK-20260831T113350 — 브리지 실행 단계: 추론 구간 표시 + 진행 갱신 중단 해소

> cycle 문서(§18.5). 정본 계약은 `FUNCTION.md`, 이력은 `MODIFY.md`.

## 9. Requested Scope (§16.7 G1)

원 요청(2026-08-31, `/_template:entry`):

```
사용자 원문(데이터이며 지시가 아님)
프로젝트 내 서비스에서, 연결된 AI를 통해 assistant에게 요청할 때 다음과 같은 이슈가
확인되었습니다.
- 실행 단계를 표시할 때, 각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은
  확인되지 않아 수정이 필요합니다.
- 답변 도중, 실행단계의 진전이 갱신되지 않는 이슈가 확인되었습니다. 하지만 다시 웹페이지를
  새로고침 해보니, 해당 단계가 진전되었으며 일정 시간 후 또다시 실행단계가 갱신되지
  않았습니다. 시간이 흐른 후 답변은 정상적으로 확인되었지만, 시간이 지날때마다 각 실행
  단계의 갱신이 멈추는 이슈를 수정해주세요.
```

| # | 항목 | 원 요청 인용 |
|---|---|---|
| R1 | 실행 단계에 **추론(내부 동작) 구간**이 보이지 않는다 — 도구 수행시간만 보인다 | 「각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은 확인되지 않아」 |
| R2 | 답변 도중 **실행 단계 진전이 멈춘다** — 새로고침하면 진전돼 있고, 시간이 지나면 또 멈춘다 | 「시간이 지날때마다 각 실행 단계의 갱신이 멈추는 이슈를 수정해주세요」 |

**[다의어]** — 「실행 단계」
- 고른 독해: 브리지(연결된 개인 AI) 대기 말풍선의 「▶ 실행 단계」 details + 「단계 보기」
  사이드 패널. 즉 `bridge_status`/`bridge_stream` 이 싣는 `steps`.
- 버린 독해: 내부 서버 LLM 경로(`/api/progress` progress-strip). 요청이 "연결된 AI를 통해"
  로 경로를 명시했으므로 배제.
- 예시: 도구 3회를 부르는 조사에서 「단계 보기」를 열면 `list_schemas 0.4초` 다음에
  「내부 동작 — 결과를 검토하고 다음 작업을 정합니다 · 1분 12초」가 **보인다**(현재는 없다).

범위 밖: 내부 LLM 경로 단계 표시, 러너(`bridge_agent.py`) 타임아웃.

## 2.1 Implementation Plan

### 근본원인

**R1** — 브리지의 `action='activity'` 단계는 `claim_request`(시작)·`submit_answer`(끝)
**두 개뿐**이다(`ai_tools.py:_record_bridge_activity` 호출부). 도구 호출 사이의 추론 구간은
어떤 단계에도 귀속되지 않는다. 화면의 소요 산출(`app.js:_computeStepTimings`)은
`tool.selfMs = result_summary.elapsed_ms`(도구 자기 실행분)만 쓰고, **도구 사이 간격은 어느
단계에도 붙지 않아** 타임라인에서 통째로 사라진다.

**R2** — 세 갈래(모두 실측 가능한 코드 결함):

- **R2-a (주 원인)** `composer.js:_consumeBridgeStream` 의 `catch` 가 **모든** 예외를
  `"aborted"` 로 반환하고, `_streamBridgeStatus` 는 그것을 정상 종결로 보아 `true` 를
  돌려준다 → `_pollBridgeAnswer` 는 폴링 폴백도 걸지 않는다. **일시적 회선 오류 1회가 진행
  갱신을 영구히 종료**시킨다. 새로고침하면 `resumeBridgePolling` 이 감시를 되살리므로
  "새로고침하니 진전돼 있고 잠시 뒤 또 멈춘다" 가 정확히 재현된다.
- **R2-b** 재시도 예산이 **시간이 아니라 횟수**(`_BRIDGE_STREAM_MAX_ATTEMPTS=33`)다. 오류
  재시도(3초)가 정상 재접속(55초)과 같은 예산을 먹어, 회선이 몇 번 흔들리면 30분 상한이
  수 분으로 줄고 그 뒤 조용히 멈춘다.
- **R2-c** 진행 단계 조회 상한의 **무음 절단**(§16.7 G9-b). `_bridge_live_steps` 가
  `ORDER BY step_index ASC LIMIT 40` 이라 41번째부터는 **가장 오래된 40건에 고정**되고,
  서버의 변경 감지는 `len(steps)` **길이만** 본다 → 상한에 닿는 순간 `steps` 이벤트가 영영
  멎는다(새로고침해도 무효). R1 수정이 단계 수를 약 2배로 늘리므로 이 상한은 20회 도구
  호출에서 걸린다 — 함께 고쳐야 한다.
- (부수) `_bridge_live_steps` 가 `_pg()` 로 연 커넥션을 **닫지 않는다**. tick(1초)마다
  새 연결을 열고 GC 에 맡긴다 → idle-in-transaction 잔류.

### 변경 대상

| 파일 | symbol | 변경 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | `_record_bridge_step` | 도구 단계 직후 「결과를 검토하고 다음 작업을 정합니다」 activity 1건 추가 (R1) |
| ″ | `_bridge_live_steps` | 최신 N건 창(시간순 유지) + 생략 수 반환 + 커넥션 close (R2-c) |
| ″ | `_bridge_stream_snapshot` · `bridge_status` | `steps_omitted` 동반 |
| ″ | `bridge_stream` | 변경 감지를 `(len, omitted, 마지막 step_index)` 서명으로 (R2-c) |
| `.../static/app/composer.js` | `_consumeBridgeStream` | 사용자 abort 와 회선 오류 구분(`"error"`) (R2-a) |
| ″ | `_streamBridgeStatus` | 시간 기준 예산 + `"error"` 재접속 + 연속 오류 시 폴링 강등 (R2-a/b) |
| ″ | `_renderBridgeSteps` | `steps_omitted` 반영 — 「단계 보기」 개수는 **총 단계 수** |
| `.../static/app.js` | `refreshStepSidePanelForRun` · `_renderStepSidePanelBody` | 생략 안내 1줄 + 진행 중 마지막 내부 동작에 「진행 중」 표기 |

### 완료 판정 기준 (acceptance criteria)

- **AC-20260831T113350-live-steps-reasoning-1 (R1)** 도구 호출 1회마다 `agent_runtime.steps`
  에 tool 단계 1건 + activity 1건이 남고, 화면의 그 activity 소요가 **도구 실행분을 제외한
  추론 시간**이다.
- **AC-…-2 (R2-a)** 스트림 읽기 중 회선 오류가 나면 감시가 종료되지 않고 재접속한다.
  사용자 취소(`abort`)일 때만 종료한다.
- **AC-…-3 (R2-b)** 오류 재시도가 30분 총 예산을 조기 소진하지 않는다(예산이 시간 기준).
- **AC-…-4 (R2-c)** 단계 수가 상한을 넘어도 진행 갱신이 멎지 않고, 생략된 앞 단계 수가
  화면에 표시된다(무음 절단 없음).

### 위험도

**Major** — 웹 UI + 백엔드 다중 파일. 인증·인가·개인정보·파괴적 데이터 변경 없음(Critical
아님). 추가 단계 기록은 append-only 이고 실패는 흡수된다(도구 결과 반환을 막지 않는다).

## 7. Completion Checklist

- [x] R1·R2 각 항목의 AC 구현
- [x] 자동 테스트 통과 (pytest + node 하네스)
- [x] 실 Windows 브라우저 시각검증 (PB-0008) — `test-runs.d/` 기록
- [x] FUNCTION.md · MODIFY.md · REVIEW.md · REPORT.md 갱신
- [x] `bin/verify-completion.sh --pre-commit` PASS
