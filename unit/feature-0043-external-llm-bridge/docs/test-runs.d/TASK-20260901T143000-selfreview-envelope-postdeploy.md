---
run_at: 2026-09-01T18:15:00+09:00
session: ai/claude/selfreview-envelope-and-light-models
scope: "봉투 수정 + 콘솔 경량 모델 — 라이브 배포본 fe60866c POST-DEPLOY 실측"
verdict: PASS
---

# Run — TASK-20260901T143000-selfreview-envelope (POST-DEPLOY)

- **Environment**: **Windows-browser**(PB-0008) + 실 러너, 라이브 `https://localhost`,
  배포본 `GIT_COMMIT=fe60866c` (web·워커·MCP 전 서비스 동일 SHA)

## 배포 게이트

| 항목 | 결과 |
|---|---|
| 전 서비스 동일 SHA | PASS (`fe60866c`) |
| 대화 경로 스모크 | PASS (deploy-web 로그) |
| `no upstreams available` | **0** |
| surge 잔존 | 0 |
| 코드 도달 | `from_runner_payload` · 진입점 사용 · `CONSOLE_JOB_LIGHT_MODELS` · `pick_console_job_model` 전부 확인 |

## ① 자가 검증 — 라이브에서 원장에 앉는다

```
[bridge 18:10:24] INFO task.review task=t_agRxTIgcrVlElJz3 model=fable effort=high
                       dur_ms=15155 | 자가 검증 완료 — 제출에 동봉
[bridge 18:10:24] INFO task.submit.ok task=t_agRxTIgcrVlElJz3 delivered=True
```

```
id=399  source=external  task_id=t_agRxTIgcrVlElJz3  verdict=revise
block_count=1  warn_count=1  model=fable  reasoning_level=high  latency_ms=15155
```

**직전 배포에서는 같은 자리가 0 rows 였다** — 봉투 미해제 결함이 실제로 라이브를 막고
있었고, 이 배포가 그것을 뚫었다는 실측이다.

이번에도 검증이 **실제 결함을 잡았다**: 답변 생성이 `ai.fail exit=1` 로 실패해 자동 안내문이
나갔고(`task.answer.degraded reason=ai_failed`), 검증자가 그 안내문을 결함으로 지목했다.
설계대로 답변은 그대로 전달되고 판정만 남았다.

## ② 콘솔 작업 경량 모델 — 같은 러너·같은 창

```
[bridge 18:10:54] INFO task.dispatch task=j_DoSjw17SPSeKOJyF runtime=claude model=haiku kind=job
[bridge 18:10:04] INFO task.dispatch task=t_agRxTIgcrVlElJz3 runtime=claude model=fable effort=high
```

콘솔 작업(`kind=job`)은 `haiku`, 대화(`kind=chat`)는 사용자가 고른 `fable` — **한 러너에서
두 축이 갈린다**. 대화 축은 건드리지 않았다는 계약이 실측으로 확인된다.

## ③ 콘솔 화면 (라이브)

| 자리 | 값 |
|---|---|
| KPI | `자가 검증 / 3건 / 결함 지적 2 · BLOCK 2 · WARN 5` |
| 축별 표 | 완전성 B2 · 질의 정확성 W2 · 정직성 W2 · 근거 W1 |
| 브리지 작업 | 콘솔 작업 행 `자가 검증 = —`(검증 대상 아님) · 대화 행 `BLOCK 1 WARN 1` |

**콘솔 작업 행이 `—` 인 것이 옳다** — 자가 검증은 대화 답변 축이고, 기계적 산출물에는
적용하지 않는다. 화면이 「검증 없음」과 「통과」를 가르는 설계가 여기서도 작동한다.

- 증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/evidence/selfreview-live-final.png`

## ⚠ 이 실측 중 관측한 것 — 같은 계정에 러너가 여럿이면 질문이 갈린다

첫 시도에서 내 질문을 **다른 bootstrap_admin 세션**이 가로챘다(`task.claim.skip http=409`).
이 세션이 검증 과정에서 만든 토큰이 11개 살아 있었고, 그중 빌드를 신고하지 않는(구) 러너가
먼저 집어 검증 없이 제출했다. 내 검증 토큰 11개를 폐기해 해소했다(사용자 `admin` 토큰은
**건드리지 않았다** — 조건에서 계정으로 배제).

관측 자체는 제품 결함이 아니라 **테스트 위생 문제**다. 다만 같은 계정에 러너가 여럿일 때
「어느 러너가 집을지 모른다」는 성질은 실재하며, 그 축의 개선(낡은 러너 양보)은 병렬 세션이
`stale-runner-yield` 로 이미 랜딩했다.

## 미검증으로 남긴 것

- **codex `luna`** — 이 머신의 codex 쿼터 소진으로 실 기동 불가. 선택 로직만 실 신고 형태
  (`gpt-5.6-luna`)로 단위 확인했다.
