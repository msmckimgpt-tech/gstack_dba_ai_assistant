---
run_at: 2026-09-01T05:30:00+09:00
session: ai/claude-corp/feature-0003-connect-modal-transition
scope: "static/app/connect-modal.js — 판정 축 교체(직전 관측 × 쓸 수 있는 상태)"
verdict: PASS
---

# Run — TASK-20260901T0530-connect-modal-transition

- **Environment**: 순수 node 행위 테스트 + 라이브 배포본 대비. **Windows-browser** POST-DEPLOY 는
  배포 후 별도 fragment.

## 1. 제보 두 경로를 배포본으로 재현했다

같은 테스트를 **현재 라이브 배포본**(`main` 의 `connect-modal.js`)에 태우면 **6건 FAIL** 한다:

```
FAIL  I1c 명령으로 다시 이어지면 닫힌다
FAIL  I1d «연결» 을 말한다
FAIL  I2c 갱신되면 닫힌다
FAIL  I2d «갱신» 을 말한다 (연결이 아니라)
FAIL  I3b 같은 말을 쓴다
FAIL  I4 낡은 러너로 이어진 것은 성공이 아니다
결과: 29 passed, 6 failed
```

사용자가 말한 두 상황이 코드로 확인된다. 수정본은 **39/0 PASS**.

## 2. 두 요청은 같은 뿌리였다

종전 판정 = «창을 열 때 **고정한** 기준선 대비 `listening` 의 false→true 전이».

| 요청 | 왜 안 닫혔나 |
|---|---|
| 명령 경로로 재연결 | 기준선을 **고정**하므로, 열 때 «대기 중» 이면 그 뒤 끊겼다 다시 이어져도 전이가 아니다 |
| «업데이트 필요» 갱신 | 갱신 중 `listening` 은 줄곧 참이고 `runner_stale` 만 풀린다 — `listening` 만 보는 축이 통째로 놓친다 |

바꾼 것: 기준을 **직전 관측**으로, 축을 **«쓸 수 있는 상태»**(`listening && !stale`)로.

## 3. 뮤테이션 역검증

| 뮤턴트 | 죽는 단언 |
|---|---|
| 자동 경로에서 `stale` 무시 | I2c · I2d · I4 |
| 실행 경로에서 `stale` 무시 | **H5** |
| 문구 분기 제거(자동) | I2d · I3b |
| **epoch 검증 전 `_lastObs` 갱신**(codex P1 되돌림) | **J1** |

### 미잠금 (정직 표기)

- **실행 경로의 문구 분기**와 **`_lastObserved.ok` 의 stale 검사**는 뮤턴트가 **생존한다** —
  자동 관측 경로가 거의 항상 먼저 판정을 끝내 그 분기에 도달하지 않기 때문이다(방어적 중복,
  낡은-응답 경합에서만 쓰인다). 커버리지 구멍임을 숨기지 않는다.
- 「기준선 고정」 자체를 되돌리는 뮤턴트는 만들지 않았다 — **라이브 배포본 대비(I1c)** 가 그
  결함을 직접 실증하므로 별도 뮤턴트가 더할 것이 없다.

## 4. codex 적대 리뷰

첫 라운드에서 **P1 1건**: 「`_paintConn()` 이 `epoch` 검증 전에 `_lastObs` 를 갱신한다 — 이전
모달의 늦은 응답이 현재 모달의 직전 관측으로 오염되면 `!ok → ok` 로 오판해 현재 모달을 즉시
닫고 명령을 잃는다.」

**판정을 «직전 관측» 기준으로 바꾸면 그 값 자체가 자산이 된다** — 남의 창 응답이 거기 섞이면
일어나지 않은 전이가 만들어진다. 창 세대가 다르면 **기록조차 하지 않도록** 고쳤고, 그 경합을
겨누는 **J1** 을 신설했다(되돌린 뮤턴트에서 J1 이 죽는다).

## 5. POST-DEPLOY

배포 후 PB-0008 로 재실측 — `TASK-20260901T0530-connect-modal-transition-postdeploy.md`.
