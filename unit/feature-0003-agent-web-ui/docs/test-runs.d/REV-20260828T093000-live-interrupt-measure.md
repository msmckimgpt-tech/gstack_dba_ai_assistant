---
run_at: 2026-08-28T09:30:00+09:00
session: ai/claude/feature-0043-bridge-cancel-notify-fix
scope: 브리지 인터럽트·맥락 전환·진행 스트리밍의 **라이브 실측** + 그 과정에서 발견한 결함 4건 수정
verdict: T1·T2·T4·T5(부분) PASS · **P1 포함 결함 4건 발견·수정** · 재실측은 배포 후
---

# Run — 라이브 실측 (실 Windows 브라우저 + 실 러너)

Environment: **Windows-browser** (실 Windows Chrome/151.0.7922.170 · CDP relay) ·
라이브 `https://mysql-ai.company.local` · 배포본 `e8465ccb` ·
계정 `bootstrap_admin`(사용자 제공 자격증명) · 전용 새 대화 `20260827145207-94205524`

**LLM 비용 0**: 러너의 `--cmd` 를 25초 지연 후 고정 문자열을 내는 셸 스크립트로 두어
실제 LLM 을 한 번도 호출하지 않았다. 검증 대상은 브리지 배선이지 답변 품질이 아니다.

## 결과

| ID | 항목 | 결과 |
|---|---|---|
| T1 | 질문 전송 → 대기 말풍선 + **중단 버튼 노출** | **PASS** — `dataset.mode="stop"` · `aria-label="중단"` · 말풍선에 `data-bridge-task` 앵커 |
| T2 | 중단 클릭 → 취소 안내로 변경 | **PASS** — "요청을 취소했습니다…" · 버튼 `send` 복귀 · 앵커 제거 |
| T2b | 새로고침(deep-link) 후 유지 | **PASS** — `?conversation=…` 재진입 후에도 취소 안내 유지 · `placeholder` 각인 false |
| T4 | 처리 중 새 질문 → supersede | **PASS** — 이전 말풍선이 "새 질문을 보내셔서 이 요청은 대체되었습니다" |
| T5 | phase 전환 · 답변 렌더 | **PASS(부분)** — `working` 전환이 **3초 내** 반영, 답변이 **같은 말풍선을 덮어씀** |
| — | `wait_for_request` 롱폴 | **PASS** — 57초 블로킹 후 `timed_out: true`(2회 연속 실측) |
| — | 병렬 워커 | **PASS** — 러너 로그에 Q1 처리 중 Q2 동시 점유 확인 |
| — | 취소 하차 | **PASS** — "사용자가 취소했다 — 중단(제출 안 함)" |
| T5b | 진행 **단계** 표시 | **미검증** — 가짜 AI 가 도구를 호출하지 않아 `tool_call_usage` 가 비었다. 단계 0 은 정상 동작이며, 실제 조사를 하는 AI 로만 확인 가능 |
| T3 | 취소 후 제출 409 | **미검증** — 러너가 제출 전에 하차해 409 경로에 도달하지 않았다(설계대로다) |

## 실측이 드러낸 결함 4건

전부 **소스를 읽어서는 안 보이는 시간축 성질**이었다. 앞 cycle 의 구조 테스트는 이 4건이
살아 있는 채로 전부 green 이었다.

### [P1] 취소 무한 재통보 → tight loop → 러너 사망 → **다른 질문의 답변 유실**

러너 로그가 그대로 보여준다:

```
[bridge] t_Y1Mwn-Za-o8cEwQz: 내 AI(custom)에게 전달
[bridge] 취소 통보: t_Y1Mwn-Za-o8cEwQz — 진행 중이면 중단합니다.     ← supersede 정상
[bridge] t_mp8QMCWjp2_nu9q4: 내 AI(custom)에게 전달                  ← 병렬 워커 정상
[bridge] t_Y1Mwn-Za-o8cEwQz: 사용자가 취소했다 — 중단(제출 안 함)      ← 하차 정상
[bridge] 취소 통보: t_Y1Mwn-Za-o8cEwQz — 진행 중이면 중단합니다.     ← ❌ 같은 취소를 또
[bridge] FATAL: … 20회 연속 하나도 처리하지 못했습니다              ← 러너 사망
```

`wait_for_request` 가 `Status='canceled' AND ClaimedBy=me` 를 매 호출 다시 집어
`timed_out = not canceled` 가 영원히 False → 즉시 반환 → 간격 없는 재호출.
**P0-J 가 없애려던 tight loop 가 우리 서버를 향해 생겼다.**

그리고 러너가 죽으면서 진행 중이던 **Q2 의 답변이 통째로 유실**됐다(화면은 36초 넘게
"조사·작성 중" 에 멈춰 있었다). 조용한 낭비가 아니라 사용자 대면 손실이다.

→ 알린 **직후 점유를 놓는다**(`ClaimedBy=NULL`). `Status='canceled'` 는 유지(409 집행·화면 국면).

### [P2] 러너가 "처리할 것이 없는데" stall 로 셌다

`timed_out` 이 아니기만 하면 셌는데, `timed_out` 은 취소 통보로도 False 가 되고 그때
`task_ids` 는 비어 있다. → `res.get("task_ids")` 가 있을 때만 센다.

> 내 spin 가드가 **조용한 무한 루프를 큰 실패로 바꿔 준 것은 설계대로**다. 다만 그 가드가
> 없었다면 이 P1 은 "가끔 답변이 안 온다" 로만 나타나 원인 추적이 훨씬 어려웠을 것이다.

### [P2] `_http: 0`(연결 실패)을 성공으로 읽었다 — `--check` 가 "연결 정상" 거짓보고

사설 CA 를 지정하지 않은 상태에서 `--check` 가 **"연결 정상."** 을 출력했다. `Api.call` 이
연결 실패에 `{"_http": 0}` 을 돌려주는데 **0 이 falsy** 라 `not probe.get("_http")` 와
`if code:` 가 모두 성공으로 읽는다.

더 나빴던 것은 **주석과 코드의 어긋남**이다 — 백오프 블록 주석이 "`_http == 0` 을 다룬다" 고
적어 두었는데 조건이 `if code:` 라 정작 0 을 건너뛴다. 주석만 읽으면 고쳐진 것으로 보인다.

→ `{"_failed": True}` 명시 플래그 + 두 판정부 교체 + `--ca` 힌트.

### [P3] 답변 도착 후 중단 버튼이 '중단' 에 박제

`pendingStore` 는 정상적으로 비었는데(`{}`) 버튼은 `stop` 이었고, **글자를 넣어도 풀리지
않았다**. 입력 핸들러의 재렌더가 `_bridgePendingHere()` 로 게이트돼 있는데 대기를 지우는
순간 그 술어가 false 가 된다 — 화면을 고쳐 줄 트리거가 정확히 그 시점에 꺼진다.

취소 경로(`cancelCurrentRun`)는 `renderComposer()` 를 부르고 있었다. **그 비대칭이 결함이었다.**

→ 대기를 지우는 자리가 렌더를 책임진다 + 입력 핸들러에 `mode === "stop"` backstop.

## 회귀

신규 9건(`test_bridge_cancel_notify_loop.py`) + **뮤테이션 역검증** — 점유 해제를 제거하면
3건이 KILL 되고 복원하면 green. feature-0043 전체 green.

## 잔여

- **배포 후 재실측**: 같은 시나리오(Q1 처리 중 Q2 전송)로 러너 생존 · Q2 답변 도달 확인
- T3(409) · T5b(진행 단계): 도구를 실제 호출하는 AI 로만 검증 가능
- codex 외부 리뷰(한도 회복 후)
