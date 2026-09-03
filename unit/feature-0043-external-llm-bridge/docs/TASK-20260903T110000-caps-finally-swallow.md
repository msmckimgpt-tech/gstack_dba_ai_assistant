---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260903T110000-caps-finally-swallow
status: done
edit_policy: append-only
---

# TASK-20260903T110000 — `finally` 안의 `return` 이 협상 실패 사유를 삼켰다

## 1. 계기 (사용자 콘솔, 2026-09-03)

사용자가 연결 검토를 요청하며 붙인 셋업 출력에 **경고가 그대로 찍혀 있었다**:

```
C:\Users\mckim\.mysql-ai-bridge\bridge_agent.py:2988: SyntaxWarning:
    'return' in a 'finally' block
```

사용자 화면에 노출된 경고이므로 「무해한 lint」가 아니다 — 그리고 그 자리가 하필 **사용자가
지금 겪고 있는 협상 실패가 나는 함수**였다.

## 2. 무엇이 깨져 있었나

`detect_runtimes._probe_and_report` 의 구조:

```python
try:
    _probe(nm)
finally:
    if on_settled is None:
        return          # ← 진행 중인 예외를 **버린다**
    ...
```

`finally` 안의 `return` 은 `try` 에서 발생한 예외를 **조용히 삼킨다**. 그래서 `_probe` 가
터지면 그 런타임이 `probed` 에 없다는 사실만 남고 **사유가 사라진다** — 사용자는 협상
데드라인(수 분)을 기다린 끝에 「답을 받지 못했습니다」만 본다.

이 저장소가 반복해서 고쳐 온 **「실패를 삼켜 다른 실패로 위장」** 부류다
(`TASK-20260902T160000` 의 `pump_exc` 와 같은 축). 직전 cycle 이 `_ask_json` 의 **반환 기반**
실패는 `reason_out` 으로 살렸지만, **예외 기반** 실패는 이 자리에서 여전히 버려지고 있었다.

## 3. 조치

- `_probe` 의 예외를 **전용 `except` 로 잡아** `reasons` 에 남기고 `caps.probe_crashed`
  (ERROR)로 원장에 싣는다. 요약 루프가 `  <런타임>: 사유 — …` 로 사용자에게 낸다.
- `finally` 에서 **`return` 하지 않는다** — 조건을 뒤집어(`if on_settled is not None:`)
  빠져나가지 않고 감싼다. 경고도 함께 사라진다.
- 예외를 잡되 **전파하지 않는다**: 스레드가 죽으면 협상이 「조용히 안 끝나는」 상태가 되고,
  한 플랫폼 사고가 나머지 플랫폼의 협상까지 죽인다.

## 4. 완료 조건

- [x] 빌드 산출물이 `SyntaxWarning` 없이 컴파일 (사용자 콘솔에 찍힌 그 경고 해소)
- [x] `finally` 안 `return` 0건 — **AST 로** 단정(주석·문자열에 속지 않는다)
- [x] 질의 예외 사유가 **요약 줄**(`<런타임>: 사유 —`)에 도달
- [x] 한 런타임이 터져도 다른 런타임 신고는 계속된다
- [x] 원장에 `caps.probe_crashed` 전용 사건 코드
- [x] 신규 5건 + 적대 뮤테이션 **3종 전건 KILL**
      (⚠ F2「사유 기록 제거」가 **1차에서 생존** — `caps.probe_crashed` 의 `exc=` 가 예외를
      이미 싣고 있어 「출력 어딘가에 있는가」 단정이 헛통과했다. 요약 줄만 골라 보도록
      단정을 좁혀 KILL)
- [x] 컨테이너 feature-0043 — `main` 기준선과 FAILED 집합 **동일**(신규 실패 0)

## 5. 이 cycle 이 고치지 않는 것 — 사용자 머신 `claude` 인증

같은 조사에서 **답변이 오지 않는 실제 원인**을 확정했고, 그것은 우리 코드가 아니다:

| 관측 | 값 |
|---|---|
| `claude.exe --version` | **0.1초 exit=0** (`2.1.70`) — 바이너리 정상 |
| `claude.exe -p …` (argv/stdin × 플래그 유무 4조합) | **전부 무응답** |
| 같은 호출 300초 여유 | **TIMEOUT · 출력 0바이트** (무한 hang) |
| `~/.claude/debug/*.txt` | **전 세션** `oauth/token status=400`(세션당 최대 26회 재시도) + `401` + `429` |
| `~/.claude/.credentials.json` | 2026-09-01 16:26 이후 미갱신 |
| `.claude.json` | `hasCompletedOnboarding` 키 **부재** |

즉 그 머신의 Claude Code 가 **갱신 불가한 OAuth 상태**로 토큰 재발급을 반복 시도하다 멈춘다.
`claude` 재인증(로그인)이 유일한 해소 경로이며, 브리지 쪽에서 할 수 있는 것은 없다.

부수 관측(차단 원인 아님): `claude`/`claude.exe` 가 **PATH 에 없다**. 러너는 표준 설치 위치
폴백(`%USERPROFILE%\.local\bin`)으로 찾으므로 영향받지 않는다(`test_win_ai_detection.py` 가
잠근 축). 사용자가 콘솔에서 직접 `claude` 를 못 부르는 것은 그 PATH 때문이다.
